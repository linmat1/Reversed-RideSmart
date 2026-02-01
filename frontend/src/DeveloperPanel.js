import React, { useEffect, useRef, useState } from 'react';
import './DeveloperPanel.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function DeveloperPanel({ onClose }) {
  const [activeTab, setActiveTab] = useState('rides');
  const [snapshot, setSnapshot] = useState({ ride_log: [], access_log: [] });
  const [connected, setConnected] = useState(false);
  const [cancellingRideIds, setCancellingRideIds] = useState(() => new Set());
  const [error, setError] = useState(null);
  const eventSourceRef = useRef(null);

  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/developer/stream`);
    eventSourceRef.current = es;

    es.onopen = () => {
      setConnected(true);
      setError(null);
    };

    es.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data);
        if (payload?.type === 'snapshot' && payload?.data) {
          setSnapshot(payload.data);
        }
      } catch {
        // ignore
      }
    };

    es.onerror = () => {
      setConnected(false);
      try {
        es.close();
      } catch {}
    };

    return () => {
      if (eventSourceRef.current) {
        try {
          eventSourceRef.current.close();
        } catch {}
        eventSourceRef.current = null;
      }
    };
  }, []);

  const cancelRide = async (userKey, rideId) => {
    const key = `${userKey}-${rideId}`;
    setCancellingRideIds((prev) => new Set(prev).add(key));
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/lyft/cancel-booking`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userKey, ride_id: rideId }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data?.message || `Cancel failed (HTTP ${res.status})`);
      }
    } catch (e) {
      setError(e?.message || 'Cancel failed');
    } finally {
      setCancellingRideIds((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const rideLog = snapshot.ride_log || [];
  const accessLog = snapshot.access_log || [];

  const formatTs = (ts) => {
    if (!ts) return '—';
    try {
      const d = new Date(ts * 1000);
      return d.toLocaleString();
    } catch {
      return String(ts);
    }
  };

  return (
    <div className="developer-panel-overlay">
      <div className="developer-panel">
        <div className="developer-panel-header">
          <h1>Developer</h1>
          <span className={`developer-panel-live ${connected ? 'connected' : ''}`}>
            {connected ? 'live' : 'reconnecting…'}
          </span>
          <button type="button" className="developer-panel-close" onClick={onClose}>
            Close
          </button>
        </div>

        {error && (
          <div className="developer-panel-error">{error}</div>
        )}

        <div className="developer-panel-tabs">
          <button
            type="button"
            className={`developer-tab ${activeTab === 'rides' ? 'active' : ''}`}
            onClick={() => setActiveTab('rides')}
          >
            Individual ride status log
          </button>
          <button
            type="button"
            className={`developer-tab ${activeTab === 'users' ? 'active' : ''}`}
            onClick={() => setActiveTab('users')}
          >
            User log
          </button>
        </div>

        <div className="developer-panel-body">
          {activeTab === 'rides' && (
            <div className="developer-ride-log">
              <p className="developer-ride-log-desc">
                All rides booked (filler and Lyft). Cancel button only for rides still active. &quot;Cancelled&quot; appears only after the external server confirms the cancellation.
              </p>
              {rideLog.length === 0 ? (
                <div className="developer-empty">No rides in log yet.</div>
              ) : (
                <ul className="developer-ride-list">
                  {rideLog.map((entry) => {
                    const rideId = entry.ride_id ?? entry.prescheduled_ride_id;
                    const canCancel = !entry.cancelled && (entry.ride_id ?? entry.prescheduled_ride_id);
                    const cancelKey = `${entry.user_key}-${rideId}`;
                    const isCancelling = cancellingRideIds.has(cancelKey);

                    return (
                      <li key={entry.id} className="developer-ride-entry">
                        <div className="developer-ride-row">
                          <span className="developer-ride-type">{entry.ride_type}</span>
                          <span className="developer-ride-source">
                            {entry.source === 'orchestrator' ? 'Lyft booker' : 'Individual booking'}
                          </span>
                          {entry.cancelled && (
                            <span className="developer-ride-cancelled">Cancelled</span>
                          )}
                          {canCancel && (
                            <button
                              type="button"
                              className="developer-cancel-btn"
                              onClick={() => cancelRide(entry.user_key, rideId)}
                              disabled={isCancelling}
                            >
                              {isCancelling ? 'Cancelling…' : 'Cancel'}
                            </button>
                          )}
                        </div>
                        <div className="developer-ride-meta">
                          <span>User: {entry.user_name} ({entry.user_key})</span>
                          <span>Ride ID: {String(rideId ?? '—')}</span>
                          <span>Created: {formatTs(entry.created_at)}</span>
                          {entry.cancelled_at != null && (
                            <span>Cancelled: {formatTs(entry.cancelled_at)}</span>
                          )}
                        </div>
                        {entry.source === 'orchestrator' && entry.lyft_for_user_key && (
                          <div className="developer-ride-lyft-for">
                            Lyft for: {entry.lyft_for_user_name ?? entry.lyft_for_user_key}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}

          {activeTab === 'users' && (
            <div className="developer-user-log">
              <p className="developer-user-log-desc">
                IP address and time (and other details) when the website was accessed.
              </p>
              {accessLog.length === 0 ? (
                <div className="developer-empty">No access log entries yet.</div>
              ) : (
                <ul className="developer-access-list">
                  {accessLog.map((entry) => (
                    <li key={entry.id} className="developer-access-entry">
                      <span className="developer-access-ip">{entry.ip}</span>
                      <span className="developer-access-time">{formatTs(entry.created_at)}</span>
                      <span className="developer-access-ua" title={entry.user_agent}>
                        {entry.user_agent || '—'}
                      </span>
                      {entry.path && entry.path !== '/' && (
                        <span className="developer-access-path">{entry.path}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default DeveloperPanel;
