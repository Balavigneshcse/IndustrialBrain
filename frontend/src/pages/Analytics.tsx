import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { AnalyticsData } from '../types';
import { StatCard } from '../components/StatCard';
import { BarChart } from '../components/BarChart';

export const Analytics: React.FC = () => {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.getAnalytics().then(setData).catch(err => setError(err instanceof Error ? err.message : 'Failed to load analytics.'));
  }, []);

  if (error) return <div className="page-container"><div className="card" style={{ color: 'var(--accent-danger)' }}>{error}</div></div>;
  if (!data) return <div className="page-container"><div className="spinner"></div></div>;

  const failureBars = data.topFailureModes.map(d => ({ label: d.failure, value: d.count }));
  const actionBars = data.topActions.map(d => ({ label: d.action, value: d.count }));
  const maxFailure = Math.max(...failureBars.map(d => d.value), 1);
  const maxAction = Math.max(...actionBars.map(d => d.value), 1);
  const maxAssetEvents = Math.max(...data.assetsRankedByRisk.map(a => a.failureEvents), 1);

  return (
    <div className="page-container animate-fade-in">
      <div className="hero-section">
        <h1 className="hero-title text-gradient">Global Analytics</h1>
        <p className="hero-subtitle">Insights aggregated across all parsed documents and assets.</p>
      </div>

      <div className="grid-half" style={{ marginBottom: '2rem' }}>
        <StatCard title="Total Knowledge Chunks" value={data.totalChunks} icon="▤" variant="blue" />
        <StatCard title="Total Assets Tracked" value={data.totalAssets} icon="◎" variant="teal" />
      </div>

      <div className="grid-half" style={{ marginBottom: '2rem' }}>
        <div className="card">
          <h2 className="section-title">Top Failure Modes</h2>
          {failureBars.length ? <BarChart data={failureBars} max={maxFailure} /> : <p className="text-muted text-sm">No failure terms found yet.</p>}
        </div>
        <div className="card">
          <h2 className="section-title">Top Maintenance Actions</h2>
          {actionBars.length ? <BarChart data={actionBars} max={maxAction} /> : <p className="text-muted text-sm">No maintenance actions found yet.</p>}
        </div>
      </div>

      <div className="card">
        <h2 className="section-title">Assets by Failure Mentions</h2>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Asset Tag</th>
                <th>Failure mentions</th>
                <th>Most frequent failure</th>
                <th>Documents</th>
              </tr>
            </thead>
            <tbody>
              {data.assetsRankedByRisk.map(asset => (
                <tr key={asset.assetTag}>
                  <td style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>{asset.assetTag}</td>
                  <td>
                    <div className="risk-bar-container">
                      <div className="risk-bar-track">
                        <div className="risk-bar-fill" style={{ width: `${(asset.failureEvents / maxAssetEvents) * 100}%`, background: 'var(--accent-warning)' }}></div>
                      </div>
                      <span className="risk-bar-label">{asset.failureEvents}</span>
                    </div>
                  </td>
                  <td>{asset.topFailure ?? '—'}</td>
                  <td>{asset.documentCount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted" style={{ marginTop: '0.75rem' }}>
          Counts are failure-term mentions across indexed text chunks, not distinct failure events.
        </p>
      </div>
    </div>
  );
};
