import React, { useState } from 'react';
import { api } from '../api';
import { RcaData } from '../types';

const ListBlock: React.FC<{ title: string; items: string[]; ordered?: boolean; color?: string }> = ({ title, items, ordered, color }) => {
  if (!items.length) return null;
  const List = ordered ? 'ol' : 'ul';
  return (
    <div className="rca-block">
      <h3 className="rca-block-title" style={color ? { color } : undefined}>{title}</h3>
      <List className="rca-list">
        {items.map((item, i) => <li key={i}>{item}</li>)}
      </List>
    </div>
  );
};

export const RCAIntelligence: React.FC = () => {
  const [tag, setTag] = useState('');
  const [rca, setRca] = useState<RcaData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleGenerate = async () => {
    if (!tag.trim()) return;
    setLoading(true);
    setError('');
    try {
      const data = await api.generateRca(tag.trim());
      setRca(data);
    } catch (err) {
      setRca(null);
      setError(err instanceof Error ? err.message : 'Failed to generate RCA.');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    if (rca) api.exportRca(rca.assetTag).catch(err => setError(err instanceof Error ? err.message : 'Export failed.'));
  };

  return (
    <div className="page-container animate-fade-in">
      <div className="hero-section">
        <h1 className="hero-title text-gradient">Automated RCA</h1>
        <p className="hero-subtitle">Evidence-linked root cause support brief built from the indexed records.</p>
      </div>

      <div className="card" style={{ marginBottom: '2rem', display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          type="text"
          className="input"
          placeholder="Enter Asset Tag (e.g., P-101)"
          value={tag}
          onChange={e => setTag(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleGenerate()}
          style={{ maxWidth: '300px' }}
        />
        <button className="btn btn-primary" onClick={handleGenerate} disabled={loading}>
          {loading ? 'Analyzing...' : 'Generate RCA Report'}
        </button>
        {error && <span className="text-sm" style={{ color: 'var(--accent-danger)' }}>{error}</span>}
      </div>

      {rca && (
        <div className="card animate-slide-up" style={{ padding: '2rem' }}>
          <div className="rca-header">
            <div>
              <h2 className="rca-title">RCA: {rca.assetTag}</h2>
              <span
                className={`badge ${rca.evidenceStrength === 'high' ? 'badge-success' : rca.evidenceStrength === 'medium' ? 'badge-warning' : 'badge-danger'}`}
                title="From the relevance of the cited evidence and the automatic checks on the brief (numbers and citations)"
              >
                Evidence: {rca.evidenceStrength ?? 'low'}
              </span>
              <span className="text-xs text-muted" style={{ marginLeft: '0.6rem' }}>
                {rca.mode === 'llm' ? `Drafted by ${rca.model}` : 'Extractive summary of the evidence'}
              </span>
              {rca.notice && <div className="text-xs" style={{ color: 'var(--accent-warning)', marginTop: '0.4rem' }}>{rca.notice}</div>}
              {rca.warnings && rca.warnings.length > 0 && (
                <ul className="text-xs" style={{ color: 'var(--accent-warning)', marginTop: '0.4rem', paddingLeft: '1rem' }}>
                  {rca.warnings.map(w => <li key={w}>{w}</li>)}
                </ul>
              )}
            </div>
            <button className="btn btn-secondary" onClick={handleExport}>
              Download DOCX
            </button>
          </div>

          <div className="rca-block">
            <h3 className="rca-block-title" style={{ color: 'var(--accent-danger)' }}>Observed Problem</h3>
            <p className="rca-root-cause">{rca.observedProblem}</p>
          </div>

          <div className="grid-half">
            <ListBlock title="Probable Causes" items={rca.probableCauses} color="var(--accent-warning)" />
            <ListBlock title="Recorded Corrective Actions" items={rca.recordedActions} />
          </div>

          {(rca.measurements.length > 0 || rca.eventDates.length > 0) && (
            <div className="grid-half">
              {rca.measurements.length > 0 && (
                <div className="rca-block">
                  <h3 className="rca-block-title">Relevant Measurements</h3>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {rca.measurements.map(m => <span key={m} className="asset-tag">{m}</span>)}
                  </div>
                </div>
              )}
              {rca.eventDates.length > 0 && (
                <div className="rca-block">
                  <h3 className="rca-block-title">Event Dates in Evidence</h3>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {rca.eventDates.map(d => <span key={d} className="asset-tag">{d}</span>)}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="grid-half">
            <ListBlock title="Recommended Investigation" items={rca.recommendedInvestigation} ordered color="var(--accent-primary)" />
            <ListBlock title="Preventive Actions" items={rca.preventiveActions} ordered />
          </div>

          {rca.citations.length > 0 && (
            <div className="rca-block">
              <h3 className="rca-block-title">Evidence</h3>
              {rca.citations.map((c, i) => (
                <div key={i} className="citation-item">
                  <div className="citation-filename">{c.label && <strong>[{c.label}] </strong>}{c.source} (p. {c.page})</div>
                  <div className="citation-text">"{c.excerpt}"</div>
                </div>
              ))}
            </div>
          )}

          <p className="text-sm text-muted" style={{ fontStyle: 'italic' }}>{rca.disclaimer}</p>
        </div>
      )}
    </div>
  );
};
