import React, { useState, useRef, useEffect } from 'react';
import { api } from '../api';
import { ConversationTurn, AnswerFormat } from '../types';

export const ChatPanel: React.FC = () => {
  const [history, setHistory] = useState<ConversationTurn[]>([]);
  const [input, setInput] = useState('');
  const [format, setFormat] = useState<AnswerFormat>('paragraph');
  const [assetTag, setAssetTag] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history, loading]);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const userMsg = input.trim();
    setInput('');
    const newHistory = [...history, { role: 'user' as const, content: userMsg }];
    setHistory(newHistory);
    setLoading(true);

    try {
      const res = await api.chatQuery({ question: userMsg, assetTag: assetTag || undefined, desiredFormat: format, history: newHistory });
      setHistory([...newHistory, { role: 'ai', content: res.answer, citations: res.citations, id: res.queryId }]);
    } catch (err) {
      setHistory([...newHistory, { role: 'ai', content: 'Error communicating with AI core.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (id: string, fb: 1 | -1) => {
    try {
      await api.chatFeedback(id, fb);
      // Show some toast here in a real app
    } catch (err) {}
  };

  const suggestions = ["What's the status of pump P-101?", "Summarize recent maintenance for V-200", "Identify risks for compressor C-300"];

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 200px)', gap: '1.5rem' }}>
      <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
        {/* Chat History */}
        <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
          {history.length === 0 && (
            <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✦</div>
              <h2>How can I assist your operations today?</h2>
            </div>
          )}
          {history.map((turn, i) => (
            <div key={i} className={`chat-message ${turn.role === 'user' ? 'chat-user' : 'chat-ai'}`}>
              <div style={{ marginBottom: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase' }}>
                {turn.role === 'user' ? 'You' : 'IndusMind'}
              </div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{turn.content}</div>
              {turn.role === 'ai' && turn.id && (
                <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                  <button className="btn btn-ghost" style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }} onClick={() => handleFeedback(turn.id!, 1)}>👍</button>
                  <button className="btn btn-ghost" style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }} onClick={() => handleFeedback(turn.id!, -1)}>👎</button>
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="chat-message chat-ai">
              <div className="typing-indicator"><span></span><span></span><span></span></div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div style={{ padding: '1.5rem', borderTop: '1px solid var(--border-color)', background: 'var(--bg-tertiary)' }}>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
            {suggestions.map(s => (
              <button key={s} className="btn btn-secondary" style={{ fontSize: '0.75rem', padding: '0.25rem 0.75rem' }} onClick={() => setInput(s)}>{s}</button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <input type="text" className="input" placeholder="Asset Tag (Optional)" value={assetTag} onChange={e => setAssetTag(e.target.value)} style={{ width: '150px' }} />
            <select className="input" value={format} onChange={e => setFormat(e.target.value as AnswerFormat)} style={{ width: '150px', appearance: 'none' }}>
              <option value="paragraph">Paragraph</option>
              <option value="bullet">Bullet Points</option>
              <option value="table">Table</option>
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
            <button className="btn btn-primary" onClick={handleSend} disabled={loading}>
              {loading ? <div className="spinner"></div> : 'Send'}
            </button>
          </div>
        </div>
      </div>

      {/* Citations Sidebar */}
      <div className="card" style={{ width: '300px', display: 'flex', flexDirection: 'column' }}>
        <h3 style={{ marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>Evidence Citations</h3>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {history[history.length - 1]?.role === 'ai' && history[history.length - 1].citations ? (
            history[history.length - 1].citations!.map((c, i) => (
              <div key={i} style={{ padding: '1rem', background: 'var(--bg-tertiary)', borderRadius: '8px', marginBottom: '0.75rem' }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--accent-primary)', marginBottom: '0.25rem', fontWeight: 600 }}>{c.filename} {c.page ? `(p. ${c.page})` : ''}</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>"{c.textSnippet}"</div>
              </div>
            ))
          ) : (
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'center', marginTop: '2rem' }}>No citations for current response.</div>
          )}
        </div>
      </div>
    </div>
  );
};
