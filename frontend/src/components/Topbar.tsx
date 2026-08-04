import React from 'react';

interface TopbarProps {
  title: string;
  username: string;
}

export const Topbar: React.FC<TopbarProps> = ({ title, username }) => {
  return (
    <header className="topbar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>{title}</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(0,212,170,0.1)', padding: '0.25rem 0.75rem', borderRadius: '999px', fontSize: '0.8rem' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-primary)', animation: 'pulse 2s infinite' }}></span>
          <span style={{ color: 'var(--accent-primary)', fontWeight: 500 }}>System Online</span>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--accent-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, color: '#fff' }}>
            {username.charAt(0).toUpperCase()}
          </div>
          <span style={{ fontWeight: 500 }}>{username}</span>
        </div>
      </div>
    </header>
  );
};
