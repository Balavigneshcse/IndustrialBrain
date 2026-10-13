import React, { useState } from 'react';
import { api } from '../api';
import { AssetData } from '../types';
import { StatCard } from '../components/StatCard';

export const Asset360: React.FC = () => {
  const [tag, setTag] = useState('');
  const [asset, setAsset] = useState<AssetData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSearch = async () => {
    if (!tag.trim()) return;
    setLoading(true);
    setError('');
    try {
      const data = await api.getAsset(tag.trim());
      setAsset(data);
    } catch (err) {
      setAsset(null);
      setError(err instanceof Error ? err.message : 'Asset not found or error loading data.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container animate-fade-in">
      <div className="hero-section">
        <h1 className="hero-title text-gradient">Asset 360</h1>
        <p className="hero-subtitle">Comprehensive view of equipment health and history.</p>
      </div>

      <div className="card" style={{ marginBottom: '2rem', display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          type="text"
          className="input"
          placeholder="Enter Asset Tag (e.g., P-101)"
          value={tag}
          onChange={e => setTag(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          style={{ maxWidth: '300px' }}
        />
        <button className="btn btn-primary" onClick={handleSearch} disabled={loading}>
          {loading ? 'Searching...' : 'Analyze Asset'}
        </button>
        {error && <span className="text-sm" style={{ color: 'var(--accent-danger)' }}>{error}</span>}
      </div>

      {asset && (
        <div className="animate-slide-up">
          <div className="grid-stats">
            <StatCard title="Knowledge Sources" value={asset.sources.length} icon="▤" variant="blue" />
            <StatCard title="Failure Modes Mentioned" value={asset.failures.length} icon="⚠" variant="amber" />
            <StatCard title="Maintenance Actions" value={asset.maintenanceActions.length} icon="⚙" variant="purple" />
            <StatCard title="Evidence Chunks" value={asset.evidenceChunks} icon="✦" variant="teal" />
          </div>

          <div className="grid-2col">
            <div className="card">
              <h3 className="section-title">Evidence Timeline</h3>
              {asset.timeline.length ? (
                <div className="timeline">
                  {asset.timeline.map((evt, i) => (
                    <div key={i} className="timeline-item">
                      <div className="timeline-date">{evt.date} · {evt.source}</div>
                      <div className="timeline-event">{evt.summary}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted text-sm">No dated evidence found for this asset.</p>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div className="card">
                <h3 className="section-title">Failure Modes Mentioned</h3>
                <ul className="rca-list" style={{ color: 'var(--accent-warning)' }}>
                  {asset.failures.map(f => <li key={f}>{f}</li>)}
                </ul>
              </div>
              <div className="card">
                <h3 className="section-title">Maintenance Actions</h3>
                <ul className="rca-list">
                  {asset.maintenanceActions.map(a => <li key={a}>{a}</li>)}
                </ul>
              </div>
              <div className="card">
                <h3 className="section-title">Measurements in Evidence</h3>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                  {asset.measurements.map(m => <span key={m} className="asset-tag">{m}</span>)}
                </div>
              </div>
              <div className="card">
                <h3 className="section-title">Sources</h3>
                {asset.sources.map(s => (
                  <div key={s} className="measurement-row"><span className="measurement-key">{s}</span></div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
