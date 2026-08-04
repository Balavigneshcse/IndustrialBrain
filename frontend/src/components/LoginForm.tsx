import React, { useState } from 'react';
import { api } from '../api';

interface LoginFormProps {
  onLogin: (token: string, username: string) => void;
}

export const LoginForm: React.FC<LoginFormProps> = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await api.login({ username, password });
      onLogin(res.token, res.displayName || res.username);
    } catch (err) {
      setError('Invalid credentials or system offline.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="card glass animate-slide-up" style={{ width: '400px', padding: '3rem 2rem', textAlign: 'center' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--accent-primary)' }}>
          ✦ IndusMind
        </h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>Industrial Intelligence Core</p>
        
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {error && <div style={{ color: 'var(--accent-danger)', fontSize: '0.9rem', padding: '0.5rem', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '6px' }}>{error}</div>}
          
          <div style={{ textAlign: 'left' }}>
            <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Username</label>
            <input type="text" className="input" value={username} onChange={e => setUsername(e.target.value)} required />
          </div>
          
          <div style={{ textAlign: 'left', marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Password</label>
            <input type="password" className="input" value={password} onChange={e => setPassword(e.target.value)} required />
          </div>
          
          <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '0.75rem', fontSize: '1rem' }} disabled={loading}>
            {loading ? <div className="spinner" style={{ margin: '0 auto' }}></div> : 'Authenticate'}
          </button>
        </form>
      </div>
    </div>
  );
};
