import React from 'react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: string;
  variant?: 'blue' | 'purple' | 'amber' | 'teal';
}

export const StatCard: React.FC<StatCardProps> = ({ title, value, icon, variant = 'teal' }) => {
  return (
    <div className={`card stat-card ${variant}`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
        <h3 style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', fontWeight: 500 }}>{title}</h3>
        <span style={{ fontSize: '1.5rem', opacity: 0.8 }}>{icon}</span>
      </div>
      <div style={{ fontSize: '2rem', fontWeight: 700, display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
        {value}
      </div>
    </div>
  );
};
