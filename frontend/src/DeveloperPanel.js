import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, Marker } from 'react-leaflet';
import L from 'leaflet';
import './DeveloperPanel.css';
import { getApiBase } from './config';

const reqOriginIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [20, 33],
  iconAnchor: [10, 33],
  shadowSize: [33, 33],
});

const reqDestIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [20, 33],
  iconAnchor: [10, 33],
  shadowSize: [33, 33],
});

/** Never replace a non-empty log with an empty one (avoids log disappearing when backend returns partial data). */
function mergeSnapshot(prev, next) {
  if (!next || typeof next !== 'object') return prev;
  const prevRides = prev?.ride_log ?? [];
  const prevAccess = prev?.access_log ?? [];
  const prevRequests = prev?.request_log ?? [];
  const nextRides = Array.isArray(next.ride_log) ? next.ride_log : [];
  const nextAccess = Array.isArray(next.access_log) ? next.access_log : [];
  const nextRequests = Array.isArray(next.request_log) ? next.request_log : [];
  return {
    ...next,
    ride_log: nextRides.length > 0 ? nextRides : prevRides.length > 0 ? prevRides : nextRides,
    access_log: nextAccess.length > 0 ? nextAccess : prevAccess.length > 0 ? prevAccess : nextAccess,
    request_log: nextRequests.length > 0 ? nextRequests : prevRequests.length > 0 ? prevRequests : nextRequests,
  };
}

function RequestMiniMap({ entry }) {
  const mapRef = useRef(null);
  const hasCoords = entry.origin_lat != null && entry.dest_lat != null;
  if (!hasCoords) return null;

  const origin = [entry.origin_lat, entry.origin_lng];
  const dest = [entry.dest_lat, entry.dest_lng];
  const center = [(origin[0] + dest[0]) / 2, (origin[1] + dest[1]) / 2];

  return (
    <MapContainer
      center={center}
      zoom={13}
      style={{ width: '100%', height: '160px', borderRadius: '8px' }}
      scrollWheelZoom={false}
      dragging={false}
      zoomControl={false}
      attributionControl={false}
      ref={mapRef}
      whenReady={() => {
        if (mapRef.current) {
          const bounds = L.latLngBounds(origin, dest);
          mapRef.current.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
        }
      }}
    >
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <Marker position={origin} icon={reqOriginIcon} />
      <Marker position={dest} icon={reqDestIcon} />
    </MapContainer>
  );
}

function DeveloperPanel() {
  const navigate = useNavigate();
  const API_BASE = getApiBase();
  const [activeTab, setActiveTab] = useState('requests');
  const [snapshot, setSnapshot] = useState({ ride_log: [], access_log: [], request_log: [] });
  const [expandedRequest, setExpandedRequest] = useState(null);
  const [connected, setConnected] = useState(false);
  const [cancellingRideIds, setCancellingRideIds] = useState(() => new Set());
  const [error, setError] = useState(null);
  const [storageInfo, setStorageInfo] = useState(null);
  const eventSourceRef = useRef(null);

  // Show which DB backend uses (postgres = persists; sqlite on Vercel does not)
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/developer/storage`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data) setStorageInfo(data);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [API_BASE]);

  // SSE for live updates (when this tab hits the same instance that got the write)
  useEffect(() => {
    let cancelled = false;
    let reconnectTimer = null;

    function connect() {
      if (cancelled) return;
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
            const next = payload.data;
            setSnapshot((prev) => mergeSnapshot(prev, next));
          }
        } catch {
          // ignore
        }
      };

      es.onerror = () => {
        setConnected(false);
        try { es.close(); } catch {}
        eventSourceRef.current = null;
        // Auto-reconnect after 3s
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (eventSourceRef.current) {
        try { eventSourceRef.current.close(); } catch {}
        eventSourceRef.current = null;
      }
    };
  }, [API_BASE]);

  // Poll snapshot every 5s so all tabs/incognito see same data (backend reads from DB when Postgres is set)
  useEffect(() => {
    const fetchSnapshot = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/developer/snapshot`);
        if (res.ok) {
          const data = await res.json();
          setSnapshot((prev) => mergeSnapshot(prev, data));
        }
      } catch {
        // ignore
      }
    };
    fetchSnapshot();
    const interval = setInterval(fetchSnapshot, 5000);
    return () => clearInterval(interval);
  }, [API_BASE]);

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
  const requestLog = snapshot.request_log || [];

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
          {storageInfo && (
            <span className="developer-panel-storage" title={storageInfo.note || ''}>
              Storage: {storageInfo.storage === 'postgres' ? 'Postgres (persists)' : `SQLite${storageInfo.path ? ` — not persisting on serverless` : ''}`}
            </span>
          )}
          <button type="button" className="developer-individual-btn" onClick={() => navigate('/?mode=individual')}>
            Individual Booking
          </button>
          <button type="button" className="developer-panel-close" onClick={() => navigate('/')}>
            Close
          </button>
        </div>

        {error && (
          <div className="developer-panel-error">{error}</div>
        )}

        <div className="developer-panel-tabs">
          <button
            type="button"
            className={`developer-tab ${activeTab === 'requests' ? 'active' : ''}`}
            onClick={() => setActiveTab('requests')}
          >
            Request log
          </button>
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

          {activeTab === 'requests' && (
            <div className="developer-request-log">
              <p className="developer-request-log-desc">
                Logs for each time the Lyft orchestrator runs. Click an entry to expand its live log.
              </p>
              {requestLog.length === 0 ? (
                <div className="developer-empty">No request log entries yet.</div>
              ) : (
                <ul className="developer-request-list">
                  {requestLog.map((entry) => {
                    const isExpanded = expandedRequest === entry.id;
                    const statusClass =
                      entry.status === 'success' ? 'success' :
                      entry.status === 'failed' ? 'failed' : 'running';
                    return (
                      <li key={entry.id} className="developer-request-entry">
                        <button
                          type="button"
                          className="developer-request-summary"
                          onClick={() => setExpandedRequest(isExpanded ? null : entry.id)}
                        >
                          <span className={`developer-request-status ${statusClass}`}>
                            {entry.status === 'success' ? '✓' : entry.status === 'failed' ? '✗' : '⏳'}
                          </span>
                          <span className="developer-request-user">{entry.user_name}</span>
                          <span className="developer-request-route">
                            {entry.origin_addr || '?'} → {entry.dest_addr || '?'}
                          </span>
                          <span className="developer-request-time">{formatTs(entry.created_at)}</span>
                          <span className="developer-request-chevron">{isExpanded ? '▾' : '▸'}</span>
                        </button>
                        {isExpanded && (
                          <div className="developer-request-detail">
                            <RequestMiniMap entry={entry} />
                            <div className="developer-request-meta">
                              <span>User: {entry.user_name} ({entry.user_key})</span>
                              <span>Status: {entry.status}</span>
                              <span>Started: {formatTs(entry.created_at)}</span>
                              {entry.finished_at && <span>Finished: {formatTs(entry.finished_at)}</span>}
                            </div>
                            {entry.log_text ? (
                              <pre className="developer-request-logtext">{entry.log_text}</pre>
                            ) : (
                              <div className="developer-empty">No log output yet.</div>
                            )}
                          </div>
                        )}
                      </li>
                    );
                  })}
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
