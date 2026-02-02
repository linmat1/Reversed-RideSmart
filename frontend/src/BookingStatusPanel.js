import React, { useEffect, useMemo, useRef, useState } from 'react';
import './BookingStatusPanel.css';
import { getApiBase } from './config';

function formatStatus(status) {
  if (!status) return 'idle';
  return String(status);
}

function BookingStatusPanel() {
  const API_BASE = getApiBase();
  const [snapshot, setSnapshot] = useState(null);
  const [connected, setConnected] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem('bookingStatusCollapsed') !== 'false';
    } catch {
      return true;
    }
  });
  const [error, setError] = useState(null);
  const [cancellingRideIds, setCancellingRideIds] = useState(() => new Set());

  const pollingRef = useRef(null);
  const eventSourceRef = useRef(null);

  const users = useMemo(() => snapshot?.users || [], [snapshot]);

  const fetchSnapshot = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`, { credentials: 'include' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSnapshot(data);
      setError(null);
    } catch (e) {
      setError(e?.message || 'failed to load status');
    }
  };

  const startPolling = () => {
    if (pollingRef.current) return;
    pollingRef.current = setInterval(() => {
      fetchSnapshot();
    }, 3000);
  };

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  useEffect(() => {
    // Always fetch an initial snapshot.
    fetchSnapshot();

    // Prefer SSE for real-time sync across all clients.
    try {
      const es = new EventSource(`${API_BASE}/api/status/stream`);
      eventSourceRef.current = es;

      es.onopen = () => {
        setConnected(true);
        setError(null);
        stopPolling();
      };

      es.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          if (payload?.type === 'snapshot') {
            setSnapshot(payload.data);
          }
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        setConnected(false);
        // Fall back to polling. Mobile networks can be flaky; polling keeps UI in sync.
        startPolling();
        try {
          es.close();
        } catch {
          // ignore
        }
      };
    } catch (e) {
      setConnected(false);
      startPolling();
    }

    return () => {
      stopPolling();
      if (eventSourceRef.current) {
        try {
          eventSourceRef.current.close();
        } catch {
          // ignore
        }
        eventSourceRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem('bookingStatusCollapsed', String(collapsed));
    } catch {
      // ignore
    }
  }, [collapsed]);

  const cancelRide = async (userKey, rideId) => {
    setCancellingRideIds(prev => {
      const next = new Set(prev);
      next.add(rideId);
      return next;
    });

    try {
      const res = await fetch(`${API_BASE}/api/lyft/cancel-booking`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ user_id: userKey, ride_id: rideId })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data?.message || `cancel failed (HTTP ${res.status})`);
      }
      // Snapshot should update via SSE/polling; also do a quick refresh.
      fetchSnapshot();
    } catch (e) {
      setError(e?.message || 'cancel failed');
    } finally {
      setCancellingRideIds(prev => {
        const next = new Set(prev);
        next.delete(rideId);
        return next;
      });
    }
  };

  return (
    <div className={`booking-status-panel ${collapsed ? 'collapsed' : ''}`} aria-label="Booking status panel">
      <div
        className="booking-status-header"
        onClick={() => setCollapsed(c => !c)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') setCollapsed(c => !c);
        }}
      >
        <div className="booking-status-title">
          <span>Bookings</span>
          <span className="booking-status-conn">
            <span className={`booking-dot ${connected ? 'connected' : ''}`} />
            <span className="booking-status-conn-text">{connected ? 'live' : 'polling'}</span>
          </span>
        </div>
        <div className="booking-status-actions" onClick={(e) => e.stopPropagation()}>
          <button className="booking-status-btn" onClick={fetchSnapshot} type="button">
            Refresh
          </button>
          <button className="booking-status-btn" onClick={() => setCollapsed(c => !c)} type="button">
            {collapsed ? 'Open' : 'Hide'}
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="booking-status-body">
          {error && (
            <div className="booking-empty">
              <strong>Error:</strong> {error}
            </div>
          )}

          {users.length === 0 && (
            <div className="booking-empty">
              No users loaded (check backend `.env` user variables).
            </div>
          )}

          {users.map((u) => {
            const rides = u.active_rides || [];
            const status = formatStatus(u.status);
            return (
              <div className="booking-user" key={u.user_key}>
                <div className="booking-user-top">
                  <div className="booking-user-name">{u.user_name}</div>
                  <div className="booking-user-status">{status}</div>
                </div>
                {u.message ? <div className="booking-user-message">{u.message}</div> : null}

                {rides.length === 0 ? (
                  <div className="booking-empty">{u.user_name}: none in progress</div>
                ) : (
                  <div className="booking-rides">
                    {rides.map((r) => (
                      <div className="booking-ride" key={`${u.user_key}-${r.ride_id}`}>
                        <div className="booking-ride-left">
                          <div className="booking-ride-type">
                            {r.ride_type || 'Ride'} booked
                          </div>
                          <div className="booking-ride-id">id: {r.ride_id}</div>
                        </div>
                        <button
                          className="booking-cancel-btn"
                          type="button"
                          onClick={() => cancelRide(u.user_key, r.ride_id)}
                          disabled={cancellingRideIds.has(r.ride_id)}
                        >
                          {cancellingRideIds.has(r.ride_id) ? 'Cancelling…' : 'Cancel'}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default BookingStatusPanel;

