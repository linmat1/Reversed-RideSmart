import React, { useState, useEffect, useRef } from 'react';
import './LyftBooker.css';
import MapSelector from './MapSelector';
import { getApiBase } from './config';
import PRESET_LOCATIONS from './presetLocations';

function LyftBooker({ onBack }) {
  const API_BASE = getApiBase();
  const [users, setUsers] = useState([]);
  const [originalUser, setOriginalUser] = useState('');
  const [mapOrigin, setMapOrigin] = useState(null);
  const [mapDestination, setMapDestination] = useState(null);
  const [mapSelectMode, setMapSelectMode] = useState('origin'); // 'origin', 'destination', or 'none'
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [log, setLog] = useState([]);
  const [activeBookings, setActiveBookings] = useState([]); // Track active bookings for manual cancellation
  const [cancellingBooking, setCancellingBooking] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const abortControllerRef = useRef(null);
  const [gettingLocation, setGettingLocation] = useState(false);
  const [centerOnOrigin, setCenterOnOrigin] = useState(false); // Only center when using current location
  const [originAddr, setOriginAddr] = useState(null);
  const [destAddr, setDestAddr] = useState(null);
  const skipOriginGeocode = useRef(false);
  const skipDestGeocode = useRef(false);
  const logEndRef = useRef(null);
  const logContainerRef = useRef(null);
  const receivedLogCount = useRef(0); // SSE log lines received (used for reconnect offset)

  // Auto-scroll log to bottom only if already near the bottom
  useEffect(() => {
    const container = logContainerRef.current;
    if (!container) return;
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
    if (isNearBottom) {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [log]);

  const fetchAddress = async (lat, lng) => {
    try {
      const res = await fetch(`${API_BASE}/api/reverse-geocode?lat=${lat}&lng=${lng}`);
      if (res.ok) return await res.json();
    } catch (err) {
      console.error('Reverse geocode error:', err);
    }
    return null;
  };

  useEffect(() => {
    if (!mapOrigin) { setOriginAddr(null); return; }
    if (skipOriginGeocode.current) { skipOriginGeocode.current = false; return; }
    let cancelled = false;
    fetchAddress(mapOrigin.lat, mapOrigin.lng).then(addr => { if (!cancelled) setOriginAddr(addr); });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapOrigin]);

  useEffect(() => {
    if (!mapDestination) { setDestAddr(null); return; }
    if (skipDestGeocode.current) { skipDestGeocode.current = false; return; }
    let cancelled = false;
    fetchAddress(mapDestination.lat, mapDestination.lng).then(addr => { if (!cancelled) setDestAddr(addr); });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapDestination]);

  // Fetch users and routes on mount
  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/users`);
        if (res.ok) {
          const data = await res.json();
          setUsers(data.users || []);
        }
      } catch (err) {
        console.error('Error fetching users:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchUsers();
  }, [API_BASE]);

  const runOrchestrator = async () => {
    if (!originalUser) {
      alert('Please select an original person (who wants the lyft sent to)');
      return;
    }

    if (!mapOrigin || !mapDestination) {
      alert('Please select both origin and destination on the map');
      return;
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;
    receivedLogCount.current = 0;
    setRunning(true);
    setCancelling(false);
    setResult(null);
    setLog(['Starting Lyft Orchestrator...']);

    // ── SSE reading helper ───────────────────────────────────────────────────
    // Reads a streamed response (either the initial POST or a reconnect GET),
    // updates state, and returns when the stream closes.
    const readStream = async (response) => {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let gotResult = false;

      const handleEvent = (data) => {
        if (data.type === 'log') {
          receivedLogCount.current += 1;
          setLog(prev => [...prev, data.message]);

          const bookingMatch = data.message.match(/✓\s+([A-Za-z\s]+?)\s+booked\s+(RideSmart|Lyft)[\s!]*(?:\(ride\s+ID:\s+(\d+)\)|Confirmed Ride ID:\s+(\d+))?/i);
          if (bookingMatch) {
            const [, userName, rideType, rideId1, rideId2] = bookingMatch;
            const rideId = rideId1 || rideId2;
            if (rideId) {
              setActiveBookings(prev => {
                const exists = prev.some(b => b.ride_id === parseInt(rideId));
                if (!exists) return [...prev, { user_name: userName.trim(), ride_id: parseInt(rideId), ride_type: rideType }];
                return prev;
              });
            }
          }

          const cancelMatch = data.message.match(/✓\s+Cancelled\s+([A-Za-z\s]+?)'s\s+(?:booking|Lyft booking)/i);
          if (cancelMatch) {
            const userName = cancelMatch[1].trim();
            setActiveBookings(prev => prev.filter(b => b.user_name !== userName));
          }
        } else if (data.type === 'result') {
          gotResult = true;
          setResult({ success: data.data.success, message: data.data.message, booking: data.data.lyft_booking });
          if (data.data.success && data.data.lyft_booking) {
            const rides = data.data.lyft_booking.prescheduled_recurring_series_rides;
            if (rides && rides.length > 0) {
              const originalUserName = users.find(u => u.id === originalUser)?.name;
              setActiveBookings(prev => [...prev, { user_name: originalUserName, ride_id: rides[0].id, ride_type: 'Lyft' }]);
            }
          }
          setRunning(false);
        } else if (data.type === 'error') {
          gotResult = true;
          setResult({ success: false, message: `Error: ${data.message}` });
          setLog(prev => [...prev, `ERROR: ${data.message}`]);
          setRunning(false);
        }
      };

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          if (buffer.trim()) {
            for (const line of buffer.split('\n')) {
              if (line.startsWith('data: ')) {
                try { handleEvent(JSON.parse(line.slice(6))); } catch (e) { /* ignore */ }
              }
            }
          }
          if (!gotResult) {
            setResult({ success: false, message: 'Connection closed unexpectedly. All rides have been cancelled on the server.' });
            setLog(prev => [...prev, 'ERROR: Connection closed unexpectedly']);
            setRunning(false);
          }
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.trim() && line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              handleEvent(data);
              if (data.type === 'result' || data.type === 'error') return;
            } catch (e) {
              console.error('Error parsing SSE data:', e, 'Line:', line);
            }
          }
        }
      }
    };
    // ── End SSE reading helper ───────────────────────────────────────────────

    const originFallback = `(${mapOrigin.lat.toFixed(6)}, ${mapOrigin.lng.toFixed(6)})`;
    const destFallback = `(${mapDestination.lat.toFixed(6)}, ${mapDestination.lng.toFixed(6)})`;
    const requestBody = {
      original_user: originalUser,
      origin: {
        latlng: { lat: mapOrigin.lat, lng: mapOrigin.lng },
        full_geocoded_addr: originAddr?.full_geocoded_addr || originFallback,
        geocoded_addr: originAddr?.geocoded_addr || originFallback,
      },
      destination: {
        latlng: { lat: mapDestination.lat, lng: mapDestination.lng },
        full_geocoded_addr: destAddr?.full_geocoded_addr || destFallback,
        geocoded_addr: destAddr?.geocoded_addr || destFallback,
      },
    };

    const attemptStream = async (url, options) => {
      const response = await fetch(url, { ...options, signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      if (!response.body) throw new Error('Response body is not available');
      await readStream(response);
    };

    try {
      await attemptStream(`${API_BASE}/api/lyft/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });
    } catch (err) {
      if (err.name === 'AbortError') {
        setCancelling(false);
        setRunning(false);
        return;
      }

      if (err.name === 'TypeError') {
        // iOS Safari / backgrounded page — try to reconnect to the running orchestrator
        const offset = receivedLogCount.current;
        setLog(prev => [...prev, '⚠️ Connection dropped — reconnecting...']);
        try {
          await attemptStream(`${API_BASE}/api/lyft/reconnect?offset=${offset}`, { method: 'GET' });
          // If reconnect also ends with TypeError, the outer catch below handles it
        } catch (reconErr) {
          if (reconErr.name === 'AbortError') {
            setCancelling(false);
            setRunning(false);
            return;
          }
          setResult({ success: false, message: 'Could not reconnect. The server is still running — please check back or open the app again.' });
          setLog(prev => [...prev, '⚠️ Reconnect failed. The server is still running in the background.']);
          setRunning(false);
        }
        return;
      }

      setResult({ success: false, message: `Connection error: ${err.message}. The server will cancel all rides automatically.` });
      setLog(prev => [...prev, `ERROR: ${err.message}`]);
      setRunning(false);
    }
  };

  const getFillerAccounts = () => {
    return users.filter(u => u.id !== originalUser).map(u => u.name);
  };

  const applyPresetLocation = (index) => {
    const loc = PRESET_LOCATIONS[index];
    if (!loc) return;
    const coords = { lat: loc.lat, lng: loc.lng };
    const addrLabel = loc.address || loc.name;
    const addrObj = { full_geocoded_addr: addrLabel, geocoded_addr: addrLabel };
    if (mapSelectMode === 'destination' || (mapSelectMode === 'none' && mapOrigin)) {
      skipDestGeocode.current = true;
      setMapDestination(coords);
      setDestAddr(addrObj);
      setMapSelectMode('none');
    } else {
      skipOriginGeocode.current = true;
      setMapOrigin(coords);
      setOriginAddr(addrObj);
      setMapSelectMode('destination');
      setCenterOnOrigin(true);
      setTimeout(() => setCenterOnOrigin(false), 100);
    }
  };

  const getCurrentLocation = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser');
      return;
    }

    setGettingLocation(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const coords = {
          lat: position.coords.latitude,
          lng: position.coords.longitude
        };
        setMapOrigin(coords);
        setMapSelectMode('destination');
        setCenterOnOrigin(true); // Trigger map centering only for current location
        setGettingLocation(false);
        // Reset centerOnOrigin after a brief moment so it can be triggered again if needed
        setTimeout(() => setCenterOnOrigin(false), 100);
      },
      (error) => {
        setGettingLocation(false);
        let errorMessage = 'Unable to get your location. ';
        switch (error.code) {
          case error.PERMISSION_DENIED:
            errorMessage += 'Please allow location access in your browser settings.';
            break;
          case error.POSITION_UNAVAILABLE:
            errorMessage += 'Location information is unavailable.';
            break;
          case error.TIMEOUT:
            errorMessage += 'Location request timed out.';
            break;
          default:
            errorMessage += 'An unknown error occurred.';
            break;
        }
        alert(errorMessage);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0
      }
    );
  };

  const cancelOrchestrator = async () => {
    setCancelling(true);
    setLog(prev => [...prev, '⏹ Stop requested. Waiting for server to cancel all bookings...']);
    try {
      await fetch(`${API_BASE}/api/lyft/stop`, { method: 'POST' });
    } catch (err) {
      console.error('Failed to send stop signal:', err);
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    }
  };

  const cancelIndividualBooking = async (booking) => {
    setCancellingBooking(booking.ride_id);
    
    try {
      // Find the user key for this booking
      const user = users.find(u => u.name === booking.user_name);
      if (!user) {
        alert(`User ${booking.user_name} not found`);
        return;
      }

      const response = await fetch(`${API_BASE}/api/lyft/cancel-booking`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id,
          ride_id: booking.ride_id
        })
      });

      const data = await response.json();
      
      if (data.success) {
        setActiveBookings(prev => prev.filter(b => b.ride_id !== booking.ride_id));
        setLog(prev => [...prev, `✓ ${data.message}`]);
        alert(`Successfully cancelled ${booking.user_name}'s ${booking.ride_type} booking`);
      } else {
        alert(`Failed to cancel booking: ${data.message || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`Error cancelling booking: ${err.message}`);
    } finally {
      setCancellingBooking(null);
    }
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
      {!running && !result && !log.length && (
        <div className="lyft-setup">
          <div className="setup-section">
            <label>👤 Original Person (who wants the lyft sent to):</label>
            <select 
              value={originalUser} 
              onChange={(e) => setOriginalUser(e.target.value)}
              className="lyft-select"
            >
              <option value="">-- Select a person --</option>
              {users.map(user => (
                <option key={user.id} value={user.id}>{user.name}</option>
              ))}
            </select>
          </div>

          <div className="setup-section">
            <div className="map-controls">
              <div className="map-buttons">
                <button
                  className="map-current-location-btn"
                  onClick={getCurrentLocation}
                  disabled={gettingLocation}
                  title="Use your current location as origin"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="8" cy="8" r="4" fill="currentColor"/>
                    <rect x="7" y="2" width="2" height="2" fill="currentColor"/>
                    <rect x="7" y="12" width="2" height="2" fill="currentColor"/>
                    <rect x="2" y="7" width="2" height="2" fill="currentColor"/>
                    <rect x="12" y="7" width="2" height="2" fill="currentColor"/>
                  </svg>
                  <span className="current-location-text">
                    <span>My</span>
                    <span>Location</span>
                  </span>
                </button>
                <button
                  className={`map-select-btn ${mapSelectMode === 'origin' ? 'active' : ''}`}
                  onClick={() => setMapSelectMode('origin')}
                  disabled={!mapOrigin && mapSelectMode !== 'origin'}
                >
                  {mapOrigin ? '✓ Origin' : 'Origin'}
                </button>
                <button
                  className={`map-select-btn ${mapSelectMode === 'destination' ? 'active' : ''}`}
                  onClick={() => setMapSelectMode('destination')}
                  disabled={!mapDestination && mapSelectMode !== 'destination'}
                >
                  {mapDestination ? '✓ Dest' : 'Destination'}
                </button>
                <button
                  className="map-clear-btn"
                  onClick={() => {
                    setMapOrigin(null);
                    setMapDestination(null);
                    setOriginAddr(null);
                    setDestAddr(null);
                    setMapSelectMode('origin');
                  }}
                  disabled={!mapOrigin && !mapDestination}
                  title="Clear all selected locations"
                >
                  Clear
                </button>
              </div>
              {PRESET_LOCATIONS.length > 0 && (
                <select
                  value=""
                  onChange={(e) => { if (e.target.value !== '') applyPresetLocation(Number(e.target.value)); }}
                  className="lyft-select preset-location-select"
                >
                  <option value="">
                    {mapSelectMode === 'destination' || (mapSelectMode === 'none' && mapOrigin)
                      ? '-- Pick destination --'
                      : '-- Pick origin --'}
                  </option>
                  {PRESET_LOCATIONS.map((loc, i) => (
                    <option key={i} value={i}>{loc.name}</option>
                  ))}
                </select>
              )}
            </div>
          </div>
          <div className="setup-section setup-section-map">
            <MapSelector
              origin={mapOrigin}
              destination={mapDestination}
              onOriginSelect={(coords) => {
                setMapOrigin(coords);
                setMapSelectMode('destination');
                setCenterOnOrigin(false);
              }}
              onDestinationSelect={(coords) => {
                setMapDestination(coords);
                setMapSelectMode('none');
              }}
              selectMode={mapSelectMode}
              centerOnOrigin={centerOnOrigin}
            />
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
            disabled={
              !originalUser ||
              users.length < 2 ||
              !mapOrigin || !mapDestination
            }
          >
            🚀 Start Lyft Orchestrator
          </button>
        </div>
      )}

      {(running || log.length > 0) && (
        <div className="lyft-log">
          <h3>📋 Log</h3>
          <div className="log-container" ref={logContainerRef}>
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
          {running && (
            <button
              className="cancel-orchestrator-btn"
              onClick={cancelOrchestrator}
              disabled={cancelling}
            >
              {cancelling ? '⏹ Stopping...' : '⏹ Stop Orchestrator'}
            </button>
          )}
        </div>
      )}

      {/* Active Bookings Section */}
      {activeBookings.length > 0 && (
        <div className="active-bookings-section">
          <h3>📋 Active Bookings</h3>
          <p className="bookings-subtitle">Manage individual bookings (filler bookings should be automatically cancelled on success)</p>
          <div className="bookings-list">
            {activeBookings.map((booking, index) => (
              <div key={index} className="booking-item">
                <div className="booking-info">
                  <strong>{booking.user_name}</strong>
                  <span className="booking-type">{booking.ride_type}</span>
                  <span className="booking-id">Ride ID: {booking.ride_id}</span>
                </div>
                <button
                  className="cancel-booking-btn"
                  onClick={() => cancelIndividualBooking(booking)}
                  disabled={cancellingBooking === booking.ride_id}
                >
                  {cancellingBooking === booking.ride_id ? 'Cancelling...' : 'Cancel'}
                </button>
              </div>
            ))}
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
              <p><strong>📱 Check your phone</strong> - the Lyft will be sent there</p>
            </div>
          )}

          <button className="reset-button" onClick={() => {
            setResult(null);
            setLog([]);
            setActiveBookings([]);
          }}>
            Try Again
          </button>
        </div>
      )}
    </div>
  );
}

export default LyftBooker;
