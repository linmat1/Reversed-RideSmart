import React, { useState, useEffect } from 'react';
import './LoginPage.css';
import { getApiBase } from './config';

function LoginPage({ onLogin }) {
  const API_BASE = getApiBase();
  const [users, setUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(true);

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/users`, { credentials: 'include' });
        if (response.ok) {
          const data = await response.json();
          const list = data.users || [];
          setUsers(list);
          if (list.length > 0 && !selectedUserId) {
            setSelectedUserId(list[0].id);
          }
        }
      } catch (err) {
        console.error('Error fetching users:', err);
        setError('Could not load users.');
      } finally {
        setLoadingUsers(false);
      }
    };
    fetchUsers();
  }, [API_BASE]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!selectedUserId || !password.trim()) {
      setError('Please select a user and enter the password provided by your admin.');
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ user_id: selectedUserId, password: password.trim() }),
      });
      const data = await response.json().catch(() => ({}));
      if (response.ok) {
        onLogin(data.user || { id: selectedUserId, name: users.find(u => u.id === selectedUserId)?.name || selectedUserId });
      } else {
        setError(data.error || 'Login failed. Check the password provided by your admin.');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="LoginPage">
      <div className="LoginPage-card">
        <h1 className="LoginPage-title">RideSmarter</h1>
        <p className="LoginPage-subtitle">Sign in with the password your admin gave you</p>

        {loadingUsers ? (
          <p className="LoginPage-loading">Loading users...</p>
        ) : (
          <form onSubmit={handleSubmit} className="LoginPage-form">
            {users.length === 0 ? (
              <p className="LoginPage-error">No users configured. Contact your admin.</p>
            ) : (
              <>
                <div className="LoginPage-field">
                  <label htmlFor="login-user">User</label>
                  <select
                    id="login-user"
                    value={selectedUserId}
                    onChange={(e) => setSelectedUserId(e.target.value)}
                    className="LoginPage-select"
                    autoComplete="username"
                  >
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>{u.name}</option>
                    ))}
                  </select>
                </div>
                <div className="LoginPage-field">
                  <label htmlFor="login-password">Password</label>
                  <input
                    id="login-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="LoginPage-input"
                    placeholder="Password from admin"
                    autoComplete="current-password"
                    autoFocus
                  />
                </div>
                {error && <p className="LoginPage-error">{error}</p>}
                <button type="submit" className="LoginPage-submit" disabled={loading}>
                  {loading ? 'Signing in...' : 'Sign in'}
                </button>
              </>
            )}
          </form>
        )}
      </div>
    </div>
  );
}

export default LoginPage;
