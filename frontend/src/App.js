import React, { useState, useEffect } from 'react';
import './App.css';
import MapSelector from './MapSelector';
import RouteMap from './RouteMap';
import LyftBooker from './LyftBooker';
import MaintenancePage from './MaintenancePage';
import BookingStatusPanel from './BookingStatusPanel';
import DeveloperPanel from './DeveloperPanel';
import { getApiBase, isApiMissing } from './config';

function App() {
  const API_BASE = getApiBase();
  const [appMode, setAppMode] = useState('lyft'); // 'normal' or 'lyft' - default to 'lyft'
  const [showIndividualBooking, setShowIndividualBooking] = useState(false); // Track if individual booking is shown
  const [proposals, setProposals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedProposal, setSelectedProposal] = useState(null);
  const [bookedRide, setBookedRide] = useState(null);
  const [booking, setBooking] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [routes, setRoutes] = useState([]);
  const [selectedRoute, setSelectedRoute] = useState(null);
  const [loadingRoutes, setLoadingRoutes] = useState(true);
  const [searchMode, setSearchMode] = useState('map'); // 'route' or 'map' - default to 'map'
  const [mapOrigin, setMapOrigin] = useState(null);
  const [mapDestination, setMapDestination] = useState(null);
  const [mapSelectMode, setMapSelectMode] = useState('origin'); // 'origin', 'destination', or 'none'
  const [cancelledMessage, setCancelledMessage] = useState(null);
  const [routeData, setRouteData] = useState(null);
  const [loadingRoute, setLoadingRoute] = useState(false);
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [gettingLocation, setGettingLocation] = useState(false);
  const [centerOnOrigin, setCenterOnOrigin] = useState(false); // Only center when using current location
  const [developerClickCount, setDeveloperClickCount] = useState(0);
  const [showDeveloperPanel, setShowDeveloperPanel] = useState(false);

  const handleDeveloperClick = () => {
    const next = developerClickCount + 1;
    if (next >= 5) {
      setShowDeveloperPanel(true);
      setDeveloperClickCount(0);
    } else {
      setDeveloperClickCount(next);
    }
  };

  useEffect(() => {
    // Record website access for developer user log (IP, time, user-agent)
    fetch(`${API_BASE}/api/developer/access`, { method: 'POST' }).catch(() => {});

    // Fetch available users on component mount
    const fetchUsers = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/users`);
        if (response.ok) {
          const data = await response.json();
          setUsers(data.users || []);
          if (data.users && data.users.length > 0) {
            setSelectedUser(data.users[0].id);
          }
        }
      } catch (err) {
        console.error('Error fetching users:', err);
      }
    };
    fetchUsers();

    // Fetch available routes on component mount
    const fetchRoutes = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/routes`);
        if (response.ok) {
          const data = await response.json();
          setRoutes(data.routes || []);
          if (data.routes && data.routes.length > 0) {
            setSelectedRoute(data.routes[0].id);
          }
        }
      } catch (err) {
        console.error('Error fetching routes:', err);
      } finally {
        setLoadingRoutes(false);
      }
    };
    fetchRoutes();
  }, [API_BASE]);

  const searchRides = async () => {
    // Validate based on search mode
    if (searchMode === 'route' && !selectedRoute) {
      setError('Please select a route');
      return;
    }
    
    if (searchMode === 'map' && (!mapOrigin || !mapDestination)) {
      setError('Please select both origin and destination on the map');
      return;
    }

    setLoading(true);
    setError(null);
    setProposals([]);
    setSelectedProposal(null);
    setBookedRide(null);
    setCancelledMessage(null);

    try {
      let requestBody = { user_id: selectedUser };
      
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

      const response = await fetch(`${API_BASE}/api/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error('Search failed');
      }

      const data = await response.json();
      const proposalsList = data.proposals || [];

      if (proposalsList.length === 0) {
        setError('No ride proposals available.');
      } else {
        setProposals(proposalsList);
      }
    } catch (err) {
      setError(err.message || 'Error searching for rides');
    } finally {
      setLoading(false);
    }
  };

  const bookRide = async (proposal) => {
    setSelectedProposal(proposal);
    setBooking(true);
    setError(null);

    try {
      let origin, destination;
      
      if (searchMode === 'route') {
        const currentRoute = routes.find(r => r.id === selectedRoute);
        origin = currentRoute?.origin.data;
        destination = currentRoute?.destination.data;
      } else {
        // Map mode - use map coordinates
        origin = {
          latlng: {
            lat: mapOrigin.lat,
            lng: mapOrigin.lng
          },
          full_geocoded_addr: `Custom Location (${mapOrigin.lat.toFixed(6)}, ${mapOrigin.lng.toFixed(6)})`,
          geocoded_addr: `(${mapOrigin.lat.toFixed(6)}, ${mapOrigin.lng.toFixed(6)})`
        };
        destination = {
          latlng: {
            lat: mapDestination.lat,
            lng: mapDestination.lng
          },
          full_geocoded_addr: `Custom Location (${mapDestination.lat.toFixed(6)}, ${mapDestination.lng.toFixed(6)})`,
          geocoded_addr: `(${mapDestination.lat.toFixed(6)}, ${mapDestination.lng.toFixed(6)})`
        };
      }

      // Determine ride type for better server-side status tracking
      const proposalStr = JSON.stringify(proposal).toLowerCase();
      const rideType = proposalStr.includes('lyft') ? 'Lyft' : 'RideSmart';

      const response = await fetch(`${API_BASE}/api/book`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prescheduled_ride_id: proposal.prescheduled_ride_id,
          proposal_uuid: proposal.proposal_uuid,
          origin: origin,
          destination: destination,
          user_id: selectedUser,
          ride_type: rideType,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Booking failed');
      }

      const data = await response.json();
      setBookedRide({
        ...proposal,
        bookingResponse: data,
      });
      
      // Fetch the route if route_identifier is available
      if (data.route_identifier) {
        fetchRoute(data.route_identifier);
      }
    } catch (err) {
      setError(err.message || 'Error booking ride');
    } finally {
      setBooking(false);
    }
  };

  const fetchRoute = async (routeIdentifier) => {
    setLoadingRoute(true);
    try {
      const response = await fetch(`${API_BASE}/api/route/get`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          route_identifier: routeIdentifier,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setRouteData(data);
      }
    } catch (err) {
      console.error('Error fetching route:', err);
    } finally {
      setLoadingRoute(false);
    }
  };

  const cancelRide = async (rideId) => {
    setCancelling(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/cancel`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ride_id: rideId,
          user_id: selectedUser,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Cancellation failed');
      }

      await response.json(); // Response is not used, but we need to consume it
      setBookedRide(null);
      setSelectedProposal(null);
      setRouteData(null);
      setProposals([]);  // Clear proposals to go back to home screen
      setCancelledMessage('Ride cancelled successfully!');
    } catch (err) {
      setError(err.message || 'Error cancelling ride');
    } finally {
      setCancelling(false);
    }
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A';
    try {
      const date = new Date(timestamp * 1000);
      return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    } catch {
      return 'N/A';
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

  // Backend URL not set in production (avoids "scan for local devices" prompt)
  if (isApiMissing()) {
    return (
      <div className="App" style={{ padding: '2rem', textAlign: 'center', maxWidth: '480px', margin: '0 auto' }}>
        <h1>RideSmart</h1>
        <p style={{ color: '#f87171', marginTop: '1rem' }}>
          Backend URL not configured. Set <strong>REACT_APP_API_URL</strong> in your frontend project settings (e.g. Vercel Environment Variables) to your backend URL, then redeploy.
        </p>
      </div>
    );
  }

  // Developer panel (5 clicks on "Developer")
  if (showDeveloperPanel) {
    return (
      <DeveloperPanel onClose={() => setShowDeveloperPanel(false)} />
    );
  }

  // Check for maintenance mode
  const maintenanceMode = process.env.REACT_APP_MAINTENANCE_MODE === 'true';
  
  if (maintenanceMode) {
    return (
      <>
        <BookingStatusPanel />
        <MaintenancePage />
      </>
    );
  }

  // If in Lyft Booker mode, show that component
  if (appMode === 'lyft') {
    return (
      <div className="App">
        <BookingStatusPanel />
        <header className="App-header">
          <div className="header-content">
            <div className="header-title">
              <h1>RideSmarter</h1>
              <p>Get Free Lyft Rides</p>
            </div>
            <button className="developer-toggle" onClick={handleDeveloperClick} type="button">
              Developer
            </button>
          </div>
        </header>

        <div className="info-section">
          <div className="info-card">
            <div className="info-content">
              <div className="info-item">
                <span className="info-label">Service Hours:</span>
                <span className="info-value">5:00 PM – 4:00 AM</span>
              </div>
              <div className="info-item">
                <span className="info-label">Boundaries:</span>
                <span className="info-value">You must book within RideSmart boundaries, or this app will show errors</span>
              </div>
              <div className="info-item">
                <span className="info-label">IMPORTANT:</span>
                <span className="info-value">Do not leave or refresh site while booking in progress</span>
              </div>
              <div className="info-item">
                <span className="info-label">CONTACT:</span>
                <span className="info-value">+447754666843 on WhatsApp</span>
              </div>
            </div>
          </div>
        </div>

        <div className="mode-switch-section">
          <button 
            className="individual-booking-button"
            onClick={() => {
              setAppMode('normal');
              setShowIndividualBooking(true);
            }}
          >
            📱 Individual Booking
          </button>
          <p className="individual-booking-subtext">
            Book normal RideSmart rides to your phone (no Lyft)
          </p>
        </div>

        <LyftBooker onBack={() => setAppMode('normal')} />
      </div>
    );
  }

  return (
    <div className="App">
      <BookingStatusPanel />
      <header className="App-header">
        <div className="header-content">
          <div className="header-title">
            <h1>RideSmart</h1>
            <p>Search, Book, and Cancel Rides</p>
            <button 
              className="lyft-mode-button"
              onClick={() => {
                setAppMode('lyft');
                setShowIndividualBooking(false);
              }}
            >
              🚗 Lyft Booker Mode
            </button>
          </div>
          <button className="developer-toggle" onClick={handleDeveloperClick} type="button">
            Developer
          </button>
        </div>
      </header>

      <div className="info-section">
        <div className="info-card">
          <div className="info-content">
            <div className="info-item">
              <span className="info-label">Service Hours:</span>
              <span className="info-value">5:00 PM – 4:00 AM on weekdays</span>
            </div>
            <div className="info-item">
              <span className="info-label">Boundaries:</span>
              <span className="info-value">You must book within RideSmart boundaries, or this app will show errors</span>
            </div>
            <div className="info-item">
              <span className="info-label">IMPORTANT:</span>
              <span className="info-value">Do not leave or refresh site while booking in progress</span>
            </div>
            <div className="info-item">
              <span className="info-label">CONTACT:</span>
              <span className="info-value">+447754666843 on WhatsApp</span>
            </div>
          </div>
        </div>
      </div>

      <main className="App-main">
        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {cancelledMessage && (
          <div className="success-message cancelled-message">
            <h2>✓ {cancelledMessage}</h2>
            <button 
              className="new-search-button"
              onClick={() => {
                setCancelledMessage(null);
                setShowIndividualBooking(false);
              }}
            >
              Start New Search
            </button>
          </div>
        )}

        {!proposals.length && !loading && !bookedRide && !cancelledMessage && !showIndividualBooking && (
          <div className="search-section">
            <div className="individual-booking-prompt">
              <h2>Individual Ride Booking</h2>
              <p>Book a single ride using RideSmart or Lyft</p>
              <button 
                className="start-individual-booking-button"
                onClick={() => setShowIndividualBooking(true)}
              >
                Start Individual Booking
              </button>
            </div>
          </div>
        )}

        {!proposals.length && !loading && !bookedRide && !cancelledMessage && showIndividualBooking && (
          <div className="search-section">
            {loadingRoutes ? (
              <div className="loading">
                <p>Loading routes...</p>
              </div>
            ) : (
              <>
                {/* User Selector */}
                {users.length > 0 && (
                  <div className="user-selector">
                    <label htmlFor="user-select" className="user-label">
                      👤 Booking as:
                    </label>
                    <select
                      id="user-select"
                      value={selectedUser || ''}
                      onChange={(e) => setSelectedUser(e.target.value)}
                      className="user-select"
                    >
                      {users.map((user) => (
                        <option key={user.id} value={user.id}>
                          {user.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

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

                {searchMode === 'route' ? (
                  <>
                    <div className="route-selector">
                      <label htmlFor="route-select" className="route-label">
                        Select Route:
                      </label>
                      <select
                        id="route-select"
                        value={selectedRoute || ''}
                        onChange={(e) => setSelectedRoute(e.target.value)}
                        className="route-select"
                      >
                        {routes.map((route) => (
                          <option key={route.id} value={route.id}>
                            {route.origin.name} → {route.destination.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </>
                ) : (
                  <>
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
                  </>
                )}

                <button 
                  onClick={searchRides} 
                  className="search-button"
                  disabled={
                    (searchMode === 'route' && !selectedRoute) ||
                    (searchMode === 'map' && (!mapOrigin || !mapDestination))
                  }
                >
                  Search for Rides
                </button>
              </>
            )}
          </div>
        )}

        {loading && (
          <div className="loading">
            <p>Searching for rides...</p>
          </div>
        )}

        {proposals.length > 0 && !bookedRide && (
          <div className="rides-section">
            <div className="rides-header">
              <h2>Available Rides</h2>
              {searchMode === 'route' && selectedRoute && routes.find(r => r.id === selectedRoute) && (
                <div className="current-route">
                  <span className="route-indicator">
                    {routes.find(r => r.id === selectedRoute).origin.name} → {routes.find(r => r.id === selectedRoute).destination.name}
                  </span>
                </div>
              )}
            </div>
            <div className="rides-list">
              {proposals.map((proposal, index) => {
                const rideInfo = proposal.ride_info || {};
                const pickup = rideInfo.pickup || {};
                const eta = formatTime(pickup.eta_ts);
                
                // Determine if it's RideSmart or Lyft
                // Simple approach: scan the entire proposal for "lyft" anywhere
                const proposalStr = JSON.stringify(proposal).toLowerCase();
                const isLyft = proposalStr.includes('lyft');
                const vehicleType = isLyft ? '🚗 Lyft' : '🚐 RideSmart';

                return (
                  <div key={index} className="ride-card" style={{ animationDelay: `${index * 0.1}s` }}>
                    <div className="ride-number">Ride #{index + 1}</div>
                    <div className="ride-badge" style={{ 
                      background: isLyft ? '#FF00BF' : '#4ecdc4',
                      color: '#fff',
                      padding: '4px 10px',
                      borderRadius: '12px',
                      fontSize: '0.85rem',
                      marginBottom: '10px',
                      display: 'inline-block'
                    }}>
                      {vehicleType}
                    </div>
                    <div className="ride-details">
                      <div className="ride-field">
                        <strong>ETA:</strong> {eta}
                      </div>
                      <div className="ride-field small">
                        <strong>Proposal ID:</strong> {proposal.proposal_id || 'N/A'}
                      </div>
                      <div className="ride-field small">
                        <strong>Ride ID:</strong> {proposal.prescheduled_ride_id || 'N/A'}
                      </div>
                    </div>
                    <button
                      onClick={() => bookRide(proposal)}
                      className="book-button"
                      disabled={booking}
                    >
                      {booking && selectedProposal?.proposal_uuid === proposal.proposal_uuid
                        ? 'Booking...'
                        : 'Book This Ride'}
                    </button>
                  </div>
                );
              })}
            </div>
            <div className="search-again-section">
              {searchMode === 'route' && (
                <div className="route-selector">
                  <label htmlFor="route-select-again" className="route-label">
                    Change Route:
                  </label>
                  <select
                    id="route-select-again"
                    value={selectedRoute || ''}
                    onChange={(e) => setSelectedRoute(e.target.value)}
                    className="route-select"
                  >
                    {routes.map((route) => (
                      <option key={route.id} value={route.id}>
                        {route.origin.name} → {route.destination.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <button 
                onClick={() => {
                  searchRides();
                }} 
                className="search-again-button"
              >
                Search Again
              </button>
            </div>
          </div>
        )}

        {booking && (
          <div className="loading">
            <p>Booking ride...</p>
          </div>
        )}

        {bookedRide && (
          <div className="booked-section">
            <div className="success-message">
              <h2>✓ Ride Booked Successfully!</h2>
              <div className="booked-details">
                <p><strong>Ride ID:</strong> {bookedRide.prescheduled_ride_id}</p>
                <p><strong>Proposal UUID:</strong> {bookedRide.proposal_uuid}</p>
                <p><strong>📱 Check your phone</strong> - the ride details will be sent there</p>
              </div>
            </div>
            
            {/* Route Map Display */}
            {loadingRoute && (
              <div className="loading">
                <p>Loading route...</p>
              </div>
            )}
            <RouteMap 
              routeData={routeData} 
              bookingData={bookedRide?.bookingResponse} 
            />
            
            <div className="cancel-section">
              <button
                onClick={() => cancelRide(bookedRide.prescheduled_ride_id)}
                className="cancel-button"
                disabled={cancelling}
              >
                {cancelling ? 'Cancelling...' : 'Cancel This Ride'}
              </button>
              <button
                onClick={() => {
                  setBookedRide(null);
                  setSelectedProposal(null);
                  setProposals([]);
                  setRouteData(null);
                  setShowIndividualBooking(false);
                }}
                className="new-search-button"
              >
                New Search
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;

