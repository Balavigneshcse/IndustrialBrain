import React, { useState, useRef, useEffect } from 'react';
import { api } from '../api';
import { ConversationTurn, AnswerFormat, EvidenceStrength } from '../types';

const STRENGTH_BADGE: Record<EvidenceStrength, string> = { high: 'badge-success', medium: 'badge-warning', low: 'badge-danger' };
const STRENGTH_HINT = 'From the relevance of the cited evidence and the automatic checks on the answer (numbers and citations).';

function stageText(stage: string, position?: number): string {
  if (stage === 'queued') return `Waiting for the model: ${position} ${position === 1 ? 'question' : 'questions'} ahead`;
  if (stage === 'rewriting') return 'Understanding the follow-up…';
  if (stage === 'retrieving') return 'Searching the documents…';
  return 'Writing the answer…';
}

export const ChatPanel: React.FC = () => {
  const [history, setHistory] = useState<ConversationTurn[]>([]);
  const [input, setInput] = useState('');
  const [format, setFormat] = useState<AnswerFormat>('paragraph');
  const [assetTag, setAssetTag] = useState('');
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<{ name: string; position?: number }>({ name: '' });
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history, loading]);

  useEffect(() => () => abortRef.current?.abort(), []);

  // Updates the answer being streamed (always the last turn).
  const updateLast = (change: (turn: ConversationTurn) => ConversationTurn) =>
    setHistory(turns => [...turns.slice(0, -1), change(turns[turns.length - 1])]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMsg = input.trim();
    setInput('');
    const earlier = history.filter(t => !t.streaming);
    const newHistory = [...earlier, { role: 'user' as const, content: userMsg }];
    setHistory([...newHistory, { role: 'ai', content: '', streaming: true }]);
    setLoading(true);
    setStage({ name: 'retrieving' });
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await api.chatStream({
        question: userMsg,
        assetTag: assetTag || undefined,
        desiredFormat: format,
        history: newHistory.map(t => ({ role: t.role, content: t.content })),
      }, {
        onStatus: (name, position) => setStage({ name, position }),
        onSources: citations => updateLast(t => ({ ...t, citations })),
        onToken: text => updateLast(t => ({ ...t, content: t.content + text })),
      }, controller.signal);
      updateLast(() => ({
        role: 'ai', content: res.answer, citations: res.citations, id: res.queryId, mode: res.mode,
        strength: res.evidenceStrength, notice: res.notice, warnings: res.warnings,
      }));
    } catch (err) {
      if (controller.signal.aborted) {
        updateLast(t => ({ ...t, streaming: false, mode: 'stopped', content: (t.content ? t.content + '\n\n' : '') + '(Stopped.)' }));
      } else {
        const reason = err instanceof Error ? err.message : 'unknown error';
        updateLast(() => ({ role: 'ai', content: `Could not get an answer (${reason}).` }));
      }
    } finally {
      abortRef.current = null;
      setLoading(false);
      setStage({ name: '' });
    }
  };

  const handleStop = () => abortRef.current?.abort();

  const handleFeedback = async (id: number, fb: 1 | -1) => {
    try {
      await api.chatFeedback(id, fb);
    } catch {
      // Feedback is best-effort; the answer is already shown.
    }
  };

  const suggestions = [
    "Why did Pump P-101 fail repeatedly in 2025?",
    "What safety steps apply before pump maintenance?",
    "What did the lubricant sample show?",
  ];

  const last = history[history.length - 1];

  return (
    <div className="chat-container">
      <div className="chat-main">
        {/* Chat History */}
        <div ref={scrollRef} className="chat-history">
          {history.length === 0 && (
            <div className="chat-empty">
              <div className="chat-empty-icon">✦</div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                How can I assist your operations today?
              </h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.4rem' }}>
                Ask about equipment status, maintenance histories, or root cause analyses.
              </p>
            </div>
          )}
          {history.map((turn, i) => (
            <div key={i} className={`chat-message ${turn.role === 'user' ? 'chat-user' : 'chat-ai'}`}>
              <div className="chat-sender">
                {turn.role === 'user' ? 'You' : 'IndusMind AI'}
                {turn.role === 'ai' && turn.strength && (
                  <span className={`badge ${STRENGTH_BADGE[turn.strength]}`} style={{ marginLeft: '0.5rem' }} title={STRENGTH_HINT}>
                    Evidence: {turn.strength}
                  </span>
                )}
              </div>
              {turn.streaming && !turn.content ? (
                <div className="text-sm text-muted">
                  <div className="typing-indicator"><span></span><span></span><span></span></div>
                  {stageText(stage.name, stage.position)}
                </div>
              ) : (
                <div className="chat-content">{turn.content}</div>
              )}
              {turn.notice && (
                <div className="text-xs" style={{ marginTop: '0.4rem', color: 'var(--accent-warning)' }}>{turn.notice}</div>
              )}
              {turn.role === 'ai' && turn.mode === 'extractive' && !turn.notice && (
                <div className="text-xs text-muted" style={{ marginTop: '0.4rem' }}>
                  Extractive answer: assembled from the cited evidence (the language model is turned off).
                </div>
              )}
              {turn.warnings && turn.warnings.length > 0 && (
                <ul className="text-xs" style={{ marginTop: '0.4rem', color: 'var(--accent-warning)', paddingLeft: '1rem' }}>
                  {turn.warnings.map(w => <li key={w}>{w}</li>)}
                </ul>
              )}
              {turn.role === 'ai' && turn.id && (
                <div className="chat-feedback">
                  <button className="btn btn-ghost" onClick={() => handleFeedback(turn.id!, 1)} title="Helpful">👍</button>
                  <button className="btn btn-ghost" onClick={() => handleFeedback(turn.id!, -1)} title="Not helpful">👎</button>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Input Area */}
        <div className="chat-input-area">
          <div className="chat-suggestions">
            {suggestions.map(s => (
              <button key={s} className="btn btn-secondary" onClick={() => setInput(s)}>{s}</button>
            ))}
          </div>
          <div className="chat-input-row">
            <input
              type="text"
              className="input"
              placeholder="Tag (Optional)"
              value={assetTag}
              onChange={e => setAssetTag(e.target.value)}
              style={{ width: '130px', flexShrink: 0 }}
            />
            <select
              className="input"
              value={format}
              onChange={e => setFormat(e.target.value as AnswerFormat)}
              style={{ width: '145px', flexShrink: 0 }}
            >
              <option value="paragraph">Paragraph</option>
              <option value="bullet">Bullet Points</option>
              <option value="table">Table</option>
              <option value="report">Report</option>
              <option value="work_order">Work Order</option>
              <option value="checklist">Checklist</option>
            </select>
            <input
              type="text"
              className="input"
              placeholder="Ask anything about your assets..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              style={{ flex: 1 }}
            />
            {loading ? (
              <button className="btn btn-secondary" onClick={handleStop} title="Stop generating">Stop</button>
            ) : (
              <button className="btn btn-primary" onClick={handleSend}>Send</button>
            )}
          </div>
        </div>
      </div>

      {/* Citations Sidebar */}
      <aside className="chat-citations">
        <h3 className="chat-citations-title">Evidence Citations</h3>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {last?.role === 'ai' && last.citations && last.citations.length > 0 ? (
            last.citations.map((c, i) => {
              const uncited = c.cited === false && !last.streaming && last.mode !== 'stopped';
              return (
                <div key={i} className="citation-item" style={uncited ? { opacity: 0.55 } : undefined}>
                  <div className="citation-filename">
                    {c.label && <strong>[{c.label}] </strong>}
                    {c.filename} {c.page ? `(p. ${c.page})` : ''}
                    {uncited && <span className="text-xs text-muted"> · not cited</span>}
                  </div>
                  <div className="citation-text">"{c.textSnippet}"</div>
                </div>
              );
            })
          ) : (
            <div className="citation-empty">No citations for current response.</div>
          )}
        </div>
      </aside>
    </div>
  );
};
