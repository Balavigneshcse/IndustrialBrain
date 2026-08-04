import React from 'react';

interface SidebarProps {
  currentView: string;
  onChangeView: (view: string) => void;
  onLogout: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentView, onChangeView, onLogout }) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '⌂' },
    { id: 'knowledge', label: 'Knowledge Base', icon: '▤' },
    { id: 'copilot', label: 'AI Copilot', icon: '✦' },
    { id: 'asset360', label: 'Asset 360', icon: '◎' },
    { id: 'rca', label: 'RCA Intelligence', icon: '⌁' },
    { id: 'analytics', label: 'Analytics', icon: '▲' }
  ];

  return (
    <nav className="sidebar">
      <div style={{ padding: '0 2rem', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--accent-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>✦</span> IndusMind
        </h1>
      </div>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.5rem', padding: '0 1rem' }}>
        {navItems.map(item => {
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onChangeView(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '1rem',
                padding: '0.75rem 1rem',
                border: 'none',
                background: isActive ? 'rgba(0, 212, 170, 0.1)' : 'transparent',
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                cursor: 'pointer',
                borderRadius: '6px',
                borderLeft: isActive ? '3px solid var(--accent-primary)' : '3px solid transparent',
                textAlign: 'left',
                fontSize: '1rem',
                transition: 'all 0.2s',
                boxShadow: isActive ? '0 0 10px rgba(0, 212, 170, 0.2)' : 'none'
              }}
            >
              <span style={{ fontSize: '1.2rem', color: isActive ? 'var(--accent-primary)' : 'inherit' }}>{item.icon}</span>
              {item.label}
            </button>
          );
        })}
      </div>
      <div style={{ padding: '2rem 1rem', borderTop: '1px solid var(--border-color)' }}>
        <button className="btn btn-ghost" style={{ width: '100%', justifyContent: 'flex-start' }} onClick={onLogout}>
          <span style={{ fontSize: '1.2rem' }}>○</span> Logout
        </button>
      </div>
    </nav>
  );
};
