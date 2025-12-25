import React, { useState, useEffect } from 'react';
import './App.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5000';

function App() {
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

  useEffect(() => {
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
  }, []);

  const searchRides = async () => {
    if (!selectedRoute) {
      setError('Please select a route');
      return;
    }

    setLoading(true);
    setError(null);
    setProposals([]);
    setSelectedProposal(null);
    setBookedRide(null);

    try {
      const response = await fetch(`${API_BASE}/api/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          route_id: selectedRoute,
        }),
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
    if (!selectedRoute) {
      setError('Please select a route');
      return;
    }

    setSelectedProposal(proposal);
    setBooking(true);
    setError(null);

    try {
      const currentRoute = routes.find(r => r.id === selectedRoute);
      const response = await fetch(`${API_BASE}/api/book`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prescheduled_ride_id: proposal.prescheduled_ride_id,
          proposal_uuid: proposal.proposal_uuid,
          origin: currentRoute?.origin.data,
          destination: currentRoute?.destination.data,
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
    } catch (err) {
      setError(err.message || 'Error booking ride');
    } finally {
      setBooking(false);
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
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Cancellation failed');
      }

      const data = await response.json();
      setBookedRide(null);
      setSelectedProposal(null);
      alert('Ride cancelled successfully!');
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

  const formatCost = (cost) => {
    if (!cost || cost === 0) return 'Free';
    return `$${cost.toFixed(2)}`;
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>RideSmart</h1>
        <p>Search, Book, and Cancel Rides</p>
      </header>

      <main className="App-main">
        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {!proposals.length && !loading && !bookedRide && (
          <div className="search-section">
            {loadingRoutes ? (
              <div className="loading">
                <p>Loading routes...</p>
              </div>
            ) : (
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
                <button 
                  onClick={searchRides} 
                  className="search-button"
                  disabled={!selectedRoute}
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
              {selectedRoute && routes.find(r => r.id === selectedRoute) && (
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
                const dropoff = rideInfo.dropoff || {};
                const pickupLoc = pickup.location || {};
                const dropoffLoc = dropoff.location || {};

                const pickupDesc = pickupLoc.short_description || pickupLoc.description || 'Unknown';
                const dropoffDesc = dropoffLoc.short_description || dropoffLoc.description || 'Unknown';
                const walkingDist = pickup.walking_distance_description || '';
                const eta = formatTime(pickup.eta_ts);
                const cost = formatCost(rideInfo.ride_cost);

                return (
                  <div key={index} className="ride-card" style={{ animationDelay: `${index * 0.1}s` }}>
                    <div className="ride-number">Ride #{index + 1}</div>
                    <div className="ride-details">
                      <div className="ride-field">
                        <strong>Pickup:</strong> {pickupDesc} {walkingDist && `(${walkingDist} walk)`}
                      </div>
                      <div className="ride-field">
                        <strong>Dropoff:</strong> {dropoffDesc}
                      </div>
                      <div className="ride-field">
                        <strong>ETA:</strong> {eta}
                      </div>
                      <div className="ride-field">
                        <strong>Cost:</strong> {cost}
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
              <button onClick={searchRides} className="search-again-button">
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
              </div>
            </div>
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

