import React, { useState, useEffect, useRef } from 'react';
import './LyftBooker.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function LyftBooker({ onBack }) {
  const [users, setUsers] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [originalUser, setOriginalUser] = useState('');
  const [selectedRoute, setSelectedRoute] = useState('');
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [log, setLog] = useState([]);
  const logEndRef = useRef(null);

  // Auto-scroll log to bottom
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [log]);

  // Fetch users and routes on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [usersRes, routesRes] = await Promise.all([
          fetch(`${API_BASE}/api/users`),
          fetch(`${API_BASE}/api/routes`)
        ]);

        if (usersRes.ok) {
          const usersData = await usersRes.json();
          setUsers(usersData.users || []);
          if (usersData.users?.length > 0) {
            setOriginalUser(usersData.users[0].id);
          }
        }

        if (routesRes.ok) {
          const routesData = await routesRes.json();
          setRoutes(routesData.routes || []);
          if (routesData.routes?.length > 0) {
            setSelectedRoute(routesData.routes[0].id);
          }
        }
      } catch (err) {
        console.error('Error fetching data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const runOrchestrator = async () => {
    if (!originalUser || !selectedRoute) {
      alert('Please select a user and route');
      return;
    }

    setRunning(true);
    setResult(null);
    setLog(['Starting Lyft Orchestrator...']);

    try {
      const response = await fetch(`${API_BASE}/api/lyft/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_user: originalUser,
          route_id: selectedRoute
        })
      });

      const data = await response.json();
      
      if (data.log) {
        setLog(data.log);
      }
      
      setResult({
        success: data.success,
        message: data.message,
        booking: data.lyft_booking
      });
    } catch (err) {
      setResult({
        success: false,
        message: `Error: ${err.message}`
      });
      setLog(prev => [...prev, `ERROR: ${err.message}`]);
    } finally {
      setRunning(false);
    }
  };

  const getFillerAccounts = () => {
    return users.filter(u => u.id !== originalUser).map(u => u.name);
  };

  if (loading) {
    return (
      <div className="lyft-booker">
        <div className="loading">Loading...</div>
      </div>
    );
  }

  return (
    <div className="lyft-booker">
      <div className="lyft-header">
        <button className="back-button" onClick={onBack}>← Back</button>
        <h1>🚗 Lyft Booker</h1>
        <p>Get free Lyft rides by filling RideSmart capacity</p>
      </div>

      {!running && !result && (
        <div className="lyft-setup">
          <div className="setup-section">
            <label>👤 Original Person (who wants the Lyft):</label>
            <select 
              value={originalUser} 
              onChange={(e) => setOriginalUser(e.target.value)}
              className="lyft-select"
            >
              {users.map(user => (
                <option key={user.id} value={user.id}>{user.name}</option>
              ))}
            </select>
          </div>

          <div className="setup-section">
            <label>📍 Route:</label>
            <select 
              value={selectedRoute} 
              onChange={(e) => setSelectedRoute(e.target.value)}
              className="lyft-select"
            >
              {routes.map(route => (
                <option key={route.id} value={route.id}>
                  {route.origin.name} → {route.destination.name}
                </option>
              ))}
            </select>
          </div>

          <div className="setup-info">
            <h3>Configuration</h3>
            <p><strong>Original User:</strong> {users.find(u => u.id === originalUser)?.name || 'None'}</p>
            <p><strong>Filler Accounts:</strong> {getFillerAccounts().join(', ') || 'None'}</p>
            <p><strong>Total Accounts:</strong> {users.length}</p>
          </div>

          {users.length < 2 && (
            <div className="warning-message">
              ⚠️ You need at least 2 accounts to use the Lyft Booker.
              Add more users in <code>backend/src/users.py</code>
            </div>
          )}

          <button 
            className="start-button"
            onClick={runOrchestrator}
            disabled={users.length < 2}
          >
            🚀 Start Lyft Orchestrator
          </button>
        </div>
      )}

      {(running || log.length > 0) && (
        <div className="lyft-log">
          <h3>📋 Log</h3>
          <div className="log-container">
            {log.map((entry, index) => (
              <div 
                key={index} 
                className={`log-entry ${
                  entry.includes('SUCCESS') ? 'success' : 
                  entry.includes('ERROR') || entry.includes('FAILED') || entry.includes('✗') ? 'error' :
                  entry.includes('✓') ? 'success' :
                  entry.includes('---') ? 'section' : ''
                }`}
              >
                {entry}
              </div>
            ))}
            {running && <div className="log-entry running">⏳ Running...</div>}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {result && (
        <div className={`lyft-result ${result.success ? 'success' : 'failed'}`}>
          <h2>{result.success ? '🎉 SUCCESS!' : '❌ FAILED'}</h2>
          <p>{result.message}</p>
          
          {result.success && result.booking && (
            <div className="booking-details">
              <h4>Booking Details</h4>
              <p>Your Lyft has been booked!</p>
            </div>
          )}

          <button className="reset-button" onClick={() => {
            setResult(null);
            setLog([]);
          }}>
            Try Again
          </button>
        </div>
      )}
    </div>
  );
}

export default LyftBooker;
