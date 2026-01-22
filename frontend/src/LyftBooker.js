import React, { useState, useEffect, useRef } from 'react';
import './LyftBooker.css';
import MapSelector from './MapSelector';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5001';

function LyftBooker({ onBack }) {
  const [users, setUsers] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [originalUser, setOriginalUser] = useState('');
  const [selectedRoute, setSelectedRoute] = useState('');
  const [searchMode, setSearchMode] = useState('map'); // 'route' or 'map' - default to 'map'
  const [mapOrigin, setMapOrigin] = useState(null);
  const [mapDestination, setMapDestination] = useState(null);
  const [mapSelectMode, setMapSelectMode] = useState('origin'); // 'origin', 'destination', or 'none'
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [log, setLog] = useState([]);
  const [activeBookings, setActiveBookings] = useState([]); // Track active bookings for manual cancellation
  const [cancellingBooking, setCancellingBooking] = useState(null);
  const [gettingLocation, setGettingLocation] = useState(false);
  const [centerOnOrigin, setCenterOnOrigin] = useState(false); // Only center when using current location
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
          // Don't set default user - user must select
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
    // Validate based on search mode
    if (!originalUser) {
      alert('Please select an original person (who wants the lyft sent to)');
      return;
    }

    if (searchMode === 'route' && !selectedRoute) {
      alert('Please select a route');
      return;
    }

    if (searchMode === 'map' && (!mapOrigin || !mapDestination)) {
      alert('Please select both origin and destination on the map');
      return;
    }

    setRunning(true);
    setResult(null);
    setLog(['Starting Lyft Orchestrator...']);

    try {
      let requestBody = {
        original_user: originalUser
      };

      if (searchMode === 'route') {
        requestBody.route_id = selectedRoute;
      } else {
        // Map mode - send custom coordinates
        requestBody.origin = {
          latlng: {
            lat: mapOrigin.lat,
            lng: mapOrigin.lng
          },
          full_geocoded_addr: `Custom Location (${mapOrigin.lat.toFixed(6)}, ${mapOrigin.lng.toFixed(6)})`,
          geocoded_addr: `(${mapOrigin.lat.toFixed(6)}, ${mapOrigin.lng.toFixed(6)})`
        };
        requestBody.destination = {
          latlng: {
            lat: mapDestination.lat,
            lng: mapDestination.lng
          },
          full_geocoded_addr: `Custom Location (${mapDestination.lat.toFixed(6)}, ${mapDestination.lng.toFixed(6)})`,
          geocoded_addr: `(${mapDestination.lat.toFixed(6)}, ${mapDestination.lng.toFixed(6)})`
        };
      }

      // Use fetch with ReadableStream for Server-Sent Events (live streaming)
      const response = await fetch(`${API_BASE}/api/lyft/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Response body is not available');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      let streamClosed = false;
      
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          streamClosed = true;
          // Process any remaining buffer
          if (buffer.trim()) {
            const lines = buffer.split('\n');
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.type === 'result') {
                    setResult({
                      success: data.data.success,
                      message: data.data.message,
                      booking: data.data.lyft_booking
                    });
                    setRunning(false);
                  } else if (data.type === 'error') {
                    setResult({
                      success: false,
                      message: `Error: ${data.message}`
                    });
                    setLog(prev => [...prev, `ERROR: ${data.message}`]);
                    setRunning(false);
                  }
                } catch (e) {
                  console.error('Error parsing final SSE data:', e);
                }
              }
            }
          }
          // If stream closed without result, treat as error
          // Check if we already have a result set
          const hasResult = result !== null;
          if (!hasResult) {
            setResult({
              success: false,
              message: 'Connection closed unexpectedly. All rides have been cancelled on the server.'
            });
            setLog(prev => [...prev, 'ERROR: Connection closed unexpectedly']);
            setRunning(false);
          }
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.trim() && line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'log') {
                setLog(prev => [...prev, data.message]);
                
                // Extract booking information from logs to track active bookings
                // Look for patterns like "✓ {name} booked RideSmart (ride ID: {id})" or "Confirmed Ride ID: {id}"
                const bookingMatch = data.message.match(/✓\s+([A-Za-z\s]+?)\s+booked\s+(RideSmart|Lyft)[\s!]*(?:\(ride\s+ID:\s+(\d+)\)|Confirmed Ride ID:\s+(\d+))?/i);
                if (bookingMatch) {
                  const [, userName, rideType, rideId1, rideId2] = bookingMatch;
                  const rideId = rideId1 || rideId2;
                  if (rideId) {
                    setActiveBookings(prev => {
                      // Avoid duplicates
                      const exists = prev.some(b => b.ride_id === parseInt(rideId));
                      if (!exists) {
                        return [...prev, {
                          user_name: userName.trim(),
                          ride_id: parseInt(rideId),
                          ride_type: rideType
                        }];
                      }
                      return prev;
                    });
                  }
                }
                
                // Remove cancelled bookings from active list
                const cancelMatch = data.message.match(/✓\s+Cancelled\s+([A-Za-z\s]+?)'s\s+(?:booking|Lyft booking)/i);
                if (cancelMatch) {
                  const userName = cancelMatch[1].trim();
                  setActiveBookings(prev => prev.filter(b => b.user_name !== userName));
                }
              } else if (data.type === 'result') {
                setResult({
                  success: data.data.success,
                  message: data.data.message,
                  booking: data.data.lyft_booking
                });
                
                // Extract final booking info if successful
                if (data.data.success && data.data.lyft_booking) {
                  const rides = data.data.lyft_booking.prescheduled_recurring_series_rides;
                  if (rides && rides.length > 0) {
                    const originalUserName = users.find(u => u.id === originalUser)?.name;
                    setActiveBookings(prev => [...prev, {
                      user_name: originalUserName,
                      ride_id: rides[0].id,
                      ride_type: 'Lyft'
                    }]);
                  }
                }
                
                setRunning(false);
                return;
              } else if (data.type === 'error') {
                setResult({
                  success: false,
                  message: `Error: ${data.message}`
                });
                setLog(prev => [...prev, `ERROR: ${data.message}`]);
                setRunning(false);
                return;
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e, 'Line:', line);
            }
          }
        }
      }
      
      // setRunning(false) is already handled in the result/error handlers above
    } catch (err) {
      // Network error or other exception
      setResult({
        success: false,
        message: `Connection error: ${err.message}. The server will cancel all rides automatically.`
      });
      setLog(prev => [...prev, `ERROR: ${err.message}`]);
      setRunning(false);
    }
  };

  const getFillerAccounts = () => {
    return users.filter(u => u.id !== originalUser).map(u => u.name);
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
      <div className="lyft-header">
        <h1>🚗 Lyft Booker</h1>
        <p>Get free Lyft rides by filling RideSmart capacity</p>
      </div>

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
            <label>📍 Route Selection:</label>
            <div className="search-mode-toggle">
              <button
                className={`mode-toggle-btn ${searchMode === 'map' ? 'active' : ''}`}
                onClick={() => {
                  setSearchMode('map');
                  setMapOrigin(null);
                  setMapDestination(null);
                  setMapSelectMode('origin');
                }}
              >
                Use Map
              </button>
              <button
                className={`mode-toggle-btn ${searchMode === 'route' ? 'active' : ''}`}
                onClick={() => {
                  setSearchMode('route');
                  setMapOrigin(null);
                  setMapDestination(null);
                  setMapSelectMode('origin');
                }}
              >
                Use Route
              </button>
            </div>
          </div>

          {searchMode === 'route' ? (
            <div className="setup-section">
              <label>📍 Select Route:</label>
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
          ) : (
            <>
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
                        <span>Use current</span>
                        <span>location</span>
                      </span>
                    </button>
                    <button
                      className={`map-select-btn ${mapSelectMode === 'origin' ? 'active' : ''}`}
                      onClick={() => setMapSelectMode('origin')}
                      disabled={!mapOrigin && mapSelectMode !== 'origin'}
                    >
                      {mapOrigin ? (
                        <>
                          <span>✓ Origin</span>
                          <span>Set</span>
                        </>
                      ) : (
                        <>
                          <span>Set</span>
                          <span>Origin</span>
                        </>
                      )}
                    </button>
                    <button
                      className={`map-select-btn ${mapSelectMode === 'destination' ? 'active' : ''}`}
                      onClick={() => setMapSelectMode('destination')}
                      disabled={!mapDestination && mapSelectMode !== 'destination'}
                    >
                      {mapDestination ? (
                        <>
                          <span>✓ Destination</span>
                          <span>Set</span>
                        </>
                      ) : (
                        <>
                          <span>Set</span>
                          <span>Destination</span>
                        </>
                      )}
                    </button>
                    <button
                      className="map-clear-btn"
                      onClick={() => {
                        setMapOrigin(null);
                        setMapDestination(null);
                        setMapSelectMode('origin');
                      }}
                      disabled={!mapOrigin && !mapDestination}
                      title="Clear all selected locations"
                    >
                      Clear All
                    </button>
                  </div>
                </div>
              </div>
              <div className="setup-section">
                <MapSelector
                  origin={mapOrigin}
                  destination={mapDestination}
                  onOriginSelect={(coords) => {
                    setMapOrigin(coords);
                    setMapSelectMode('destination');
                    setCenterOnOrigin(false); // Don't center when manually clicking
                  }}
                  onDestinationSelect={(coords) => {
                    setMapDestination(coords);
                    setMapSelectMode('none');
                  }}
                  selectMode={mapSelectMode}
                  centerOnOrigin={centerOnOrigin}
                />
              </div>
            </>
          )}

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
              (searchMode === 'route' && !selectedRoute) ||
              (searchMode === 'map' && (!mapOrigin || !mapDestination))
            }
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
