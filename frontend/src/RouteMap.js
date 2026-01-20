import React, { useEffect, useState, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './RouteMap.css';

// Fix for default marker icons in react-leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// Custom icon for pickup (green)
const pickupIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

// Custom icon for dropoff (red)
const dropoffIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

// Custom icon for intermediate stops (orange)
const stopIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [20, 33],
  iconAnchor: [10, 33],
  popupAnchor: [1, -28],
  shadowSize: [33, 33]
});

// Component to fit map bounds to route
function FitBounds({ routePoints }) {
  const map = useMap();
  
  useEffect(() => {
    if (routePoints && routePoints.length > 0) {
      const bounds = L.latLngBounds(routePoints);
      map.fitBounds(bounds, { padding: [30, 30] });
    }
  }, [map, routePoints]);
  
  return null;
}

function RouteMap({ routeData, bookingData }) {
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    setMapReady(true);
  }, []);

  // Extract route points for the polyline (if available)
  const routePoints = useMemo(() => {
    if (!routeData || !routeData.route) return [];
    return routeData.route.map(point => [point.latlng.lat, point.latlng.lng]);
  }, [routeData]);

  // Extract stops from the route data (if available)
  const stops = useMemo(() => {
    if (!routeData || !routeData.stops) return [];
    return routeData.stops.map(stop => ({
      position: [stop.stop_location.latlng.lat, stop.stop_location.latlng.lng],
      isPickup: stop.pickups && stop.pickups.length > 0,
      isDropoff: stop.dropoffs && stop.dropoffs.length > 0,
      stopPointId: stop.stop_point_id
    }));
  }, [routeData]);

  // Extract pickup/dropoff from booking data as fallback
  const bookingLocations = useMemo(() => {
    if (!bookingData) return null;
    
    const ride = bookingData.prescheduled_recurring_series_rides?.[0];
    if (!ride) return null;
    
    const details = ride.prescheduled_recurring_series_ride_details;
    if (!details) return null;
    
    return {
      pickup: details.pickup?.location ? 
        [details.pickup.location.lat, details.pickup.location.lng] : null,
      pickupName: details.pickup?.location?.description || 'Pickup',
      dropoff: details.dropoff?.location ? 
        [details.dropoff.location.lat, details.dropoff.location.lng] : null,
      dropoffName: details.dropoff?.location?.description || 'Dropoff',
      pickupTime: details.pickup_ts,
      dropoffStartTime: details.dropoff_start_ts,
      dropoffEndTime: details.dropoff_end_ts
    };
  }, [bookingData]);

  // Default center (University of Chicago area)
  const defaultCenter = [41.788064, -87.601145];
  const defaultZoom = 14;

  if (!mapReady) {
    return <div className="route-map-loading">Loading map...</div>;
  }

  // Check if we have any data to display
  const hasRouteData = routeData && routeData.route && routeData.route.length > 0;
  const hasBookingLocations = bookingLocations && (bookingLocations.pickup || bookingLocations.dropoff);

  if (!hasRouteData && !hasBookingLocations) {
    return (
      <div className="route-map-error">
        <p>No route data available</p>
      </div>
    );
  }

  // Calculate points to fit bounds
  const allPoints = [];
  if (hasRouteData) {
    allPoints.push(...routePoints);
  } else if (hasBookingLocations) {
    if (bookingLocations.pickup) allPoints.push(bookingLocations.pickup);
    if (bookingLocations.dropoff) allPoints.push(bookingLocations.dropoff);
  }

  // Helper to format timestamp
  const formatTime = (ts) => {
    if (!ts) return '';
    const date = new Date(ts * 1000);
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  return (
    <div className="route-map-container">
      <h3>🗺️ Your Trip</h3>
      
      {/* Trip details from booking */}
      {hasBookingLocations && (
        <div className="trip-details">
          <div className="trip-location">
            <span className="trip-icon pickup">●</span>
            <div>
              <strong>Pickup:</strong> {bookingLocations.pickupName}
              {bookingLocations.pickupTime && (
                <span className="trip-time"> at {formatTime(bookingLocations.pickupTime)}</span>
              )}
            </div>
          </div>
          <div className="trip-location">
            <span className="trip-icon dropoff">●</span>
            <div>
              <strong>Dropoff:</strong> {bookingLocations.dropoffName}
              {bookingLocations.dropoffStartTime && (
                <span className="trip-time"> ~{formatTime(bookingLocations.dropoffStartTime)}</span>
              )}
            </div>
          </div>
        </div>
      )}

      <MapContainer
        center={defaultCenter}
        zoom={defaultZoom}
        style={{ height: '300px', width: '100%', borderRadius: '12px' }}
        className="route-map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        {/* Fit map to show all points */}
        <FitBounds routePoints={allPoints} />
        
        {/* Draw the route polyline if available */}
        {hasRouteData && (
          <Polyline 
            positions={routePoints} 
            color="#8B0000" 
            weight={4}
            opacity={0.8}
          />
        )}
        
        {/* Draw dashed line between pickup/dropoff if no route data */}
        {!hasRouteData && hasBookingLocations && bookingLocations.pickup && bookingLocations.dropoff && (
          <Polyline 
            positions={[bookingLocations.pickup, bookingLocations.dropoff]} 
            color="#4ecdc4" 
            weight={3}
            opacity={0.7}
            dashArray="10, 10"
          />
        )}
        
        {/* Show stops from route data */}
        {hasRouteData && stops.map((stop, index) => {
          let icon = stopIcon;
          let label = 'Stop';
          
          if (stop.isPickup) {
            icon = pickupIcon;
            label = 'Pickup';
          } else if (stop.isDropoff) {
            icon = dropoffIcon;
            label = 'Dropoff';
          }
          
          return (
            <Marker 
              key={`stop-${index}`} 
              position={stop.position} 
              icon={icon}
            >
              <Popup>
                <strong>{label}</strong>
                {stop.isPickup && <p>Your pickup point</p>}
                {stop.isDropoff && <p>Your dropoff point</p>}
              </Popup>
            </Marker>
          );
        })}

        {/* Show booking locations as markers if no route data */}
        {!hasRouteData && hasBookingLocations && (
          <>
            {bookingLocations.pickup && (
              <Marker position={bookingLocations.pickup} icon={pickupIcon}>
                <Popup>
                  <strong>Pickup</strong>
                  <p>{bookingLocations.pickupName}</p>
                  {bookingLocations.pickupTime && (
                    <p>ETA: {formatTime(bookingLocations.pickupTime)}</p>
                  )}
                </Popup>
              </Marker>
            )}
            {bookingLocations.dropoff && (
              <Marker position={bookingLocations.dropoff} icon={dropoffIcon}>
                <Popup>
                  <strong>Dropoff</strong>
                  <p>{bookingLocations.dropoffName}</p>
                </Popup>
              </Marker>
            )}
          </>
        )}
      </MapContainer>
      
      <div className="route-map-legend">
        <div className="legend-item">
          <span className="legend-marker pickup"></span>
          <span>Pickup</span>
        </div>
        <div className="legend-item">
          <span className="legend-marker dropoff"></span>
          <span>Dropoff</span>
        </div>
        {hasRouteData && (
          <div className="legend-item">
            <span className="legend-line"></span>
            <span>Route</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default RouteMap;
