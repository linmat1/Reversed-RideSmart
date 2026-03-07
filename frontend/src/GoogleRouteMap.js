import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { GoogleMap, useJsApiLoader, Marker, Polyline, Polygon, InfoWindow } from '@react-google-maps/api';
import { GOOGLE_MAPS_API_KEY } from './mapConfig';
import './RouteMap.css';
import {
  viaServiceAreaEastern,
  viaServiceAreaWestern,
  uchicagoMainCampus,
  viaZoneStyleGoogle,
} from './viaServiceZone';

const toGooglePath = (leafletCoords) =>
  leafletCoords.map(([lat, lng]) => ({ lat, lng }));

const GREEN_MARKER = 'https://maps.google.com/mapfiles/ms/icons/green-dot.png';
const RED_MARKER = 'https://maps.google.com/mapfiles/ms/icons/red-dot.png';
const ORANGE_MARKER = 'https://maps.google.com/mapfiles/ms/icons/orange-dot.png';

const containerStyle = { height: 'clamp(220px, 40vh, 350px)', width: '100%', borderRadius: '12px' };
const defaultCenter = { lat: 41.788064, lng: -87.601145 };

const cleanStyles = [
  { featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit', elementType: 'labels.icon', stylers: [{ visibility: 'off' }] },
];

function GoogleRouteMap({ routeData, bookingData }) {
  const { isLoaded } = useJsApiLoader({ id: 'google-map-script', googleMapsApiKey: GOOGLE_MAPS_API_KEY });
  const [mapReady, setMapReady] = useState(false);
  const [activeInfo, setActiveInfo] = useState(null);
  const mapRef = useRef(null);

  useEffect(() => { setMapReady(true); }, []);

  const routePoints = useMemo(() => {
    if (!routeData || !routeData.route) return [];
    return routeData.route.map(point => ({ lat: point.latlng.lat, lng: point.latlng.lng }));
  }, [routeData]);

  const stops = useMemo(() => {
    if (!routeData || !routeData.stops) return [];
    return routeData.stops.map(stop => ({
      position: { lat: stop.stop_location.latlng.lat, lng: stop.stop_location.latlng.lng },
      isPickup: stop.pickups && stop.pickups.length > 0,
      isDropoff: stop.dropoffs && stop.dropoffs.length > 0,
      stopPointId: stop.stop_point_id
    }));
  }, [routeData]);

  const bookingLocations = useMemo(() => {
    if (!bookingData) return null;
    const ride = bookingData.prescheduled_recurring_series_rides?.[0];
    if (!ride) return null;
    const details = ride.prescheduled_recurring_series_ride_details;
    if (!details) return null;
    return {
      pickup: details.pickup?.location ? { lat: details.pickup.location.lat, lng: details.pickup.location.lng } : null,
      pickupName: details.pickup?.location?.description || 'Pickup',
      dropoff: details.dropoff?.location ? { lat: details.dropoff.location.lat, lng: details.dropoff.location.lng } : null,
      dropoffName: details.dropoff?.location?.description || 'Dropoff',
      pickupTime: details.pickup_ts,
      dropoffStartTime: details.dropoff_start_ts,
      dropoffEndTime: details.dropoff_end_ts
    };
  }, [bookingData]);

  const hasRouteData = routeData && routeData.route && routeData.route.length > 0;
  const hasBookingLocations = bookingLocations && (bookingLocations.pickup || bookingLocations.dropoff);

  const onLoad = useCallback((map) => {
    mapRef.current = map;
  }, []);

  useEffect(() => {
    if (!mapRef.current || !isLoaded) return;
    const bounds = new window.google.maps.LatLngBounds();
    let hasPoints = false;

    if (hasRouteData) {
      routePoints.forEach(p => { bounds.extend(p); hasPoints = true; });
    } else if (hasBookingLocations) {
      if (bookingLocations.pickup) { bounds.extend(bookingLocations.pickup); hasPoints = true; }
      if (bookingLocations.dropoff) { bounds.extend(bookingLocations.dropoff); hasPoints = true; }
    }

    if (hasPoints) mapRef.current.fitBounds(bounds, 30);
  }, [routePoints, bookingLocations, hasRouteData, hasBookingLocations, isLoaded]);

  const formatTime = (ts) => {
    if (!ts) return '';
    const date = new Date(ts * 1000);
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  if (!mapReady || !isLoaded) {
    return <div className="route-map-loading">Loading map...</div>;
  }

  if (!hasRouteData && !hasBookingLocations) {
    return (
      <div className="route-map-error">
        <p>No route data available</p>
      </div>
    );
  }

  return (
    <div className="route-map-container">
      <h3>🗺️ Your Trip</h3>

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

      <GoogleMap
        mapContainerStyle={containerStyle}
        mapContainerClassName="route-map"
        center={defaultCenter}
        zoom={14}
        onLoad={onLoad}
        mapTypeId="hybrid"
        options={{
          streetViewControl: false,
          mapTypeControl: true,
          mapTypeControlOptions: {
            mapTypeIds: ['roadmap', 'hybrid'],
          },
          fullscreenControl: false,
          gestureHandling: 'greedy',
          styles: cleanStyles,
          clickableIcons: false,
          tilt: 0,
          rotateControl: false,
        }}
      >
        <Polygon paths={toGooglePath(viaServiceAreaEastern)} options={viaZoneStyleGoogle.serviceArea} />
        <Polygon paths={toGooglePath(viaServiceAreaWestern)} options={viaZoneStyleGoogle.serviceArea} />
        <Polygon paths={toGooglePath(uchicagoMainCampus)} options={viaZoneStyleGoogle.campus} />

        {hasRouteData && (
          <Polyline path={routePoints} options={{ strokeColor: '#8B0000', strokeWeight: 4, strokeOpacity: 0.8 }} />
        )}

        {!hasRouteData && hasBookingLocations && bookingLocations.pickup && bookingLocations.dropoff && (
          <Polyline
            path={[bookingLocations.pickup, bookingLocations.dropoff]}
            options={{ strokeColor: '#4ecdc4', strokeWeight: 3, strokeOpacity: 0.7, strokeDashArray: '10, 10' }}
          />
        )}

        {hasRouteData && stops.map((stop, index) => {
          let icon = ORANGE_MARKER;
          let label = 'Stop';
          if (stop.isPickup) { icon = GREEN_MARKER; label = 'Pickup'; }
          else if (stop.isDropoff) { icon = RED_MARKER; label = 'Dropoff'; }

          return (
            <Marker
              key={`stop-${index}`}
              position={stop.position}
              icon={icon}
              onClick={() => setActiveInfo({ index, position: stop.position, label, isPickup: stop.isPickup, isDropoff: stop.isDropoff })}
            />
          );
        })}

        {activeInfo && (
          <InfoWindow position={activeInfo.position} onCloseClick={() => setActiveInfo(null)}>
            <div>
              <strong>{activeInfo.label}</strong>
              {activeInfo.isPickup && <p>Your pickup point</p>}
              {activeInfo.isDropoff && <p>Your dropoff point</p>}
            </div>
          </InfoWindow>
        )}

        {!hasRouteData && hasBookingLocations && (
          <>
            {bookingLocations.pickup && (
              <Marker
                position={bookingLocations.pickup}
                icon={GREEN_MARKER}
                onClick={() => setActiveInfo({
                  position: bookingLocations.pickup,
                  label: 'Pickup',
                  detail: bookingLocations.pickupName,
                  time: bookingLocations.pickupTime ? `ETA: ${formatTime(bookingLocations.pickupTime)}` : null,
                  isPickup: true,
                })}
              />
            )}
            {bookingLocations.dropoff && (
              <Marker
                position={bookingLocations.dropoff}
                icon={RED_MARKER}
                onClick={() => setActiveInfo({
                  position: bookingLocations.dropoff,
                  label: 'Dropoff',
                  detail: bookingLocations.dropoffName,
                  isDropoff: true,
                })}
              />
            )}
          </>
        )}
      </GoogleMap>

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

export default GoogleRouteMap;
