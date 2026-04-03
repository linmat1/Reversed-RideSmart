import React, { useEffect, useRef, useCallback, useMemo } from 'react';
import { GoogleMap, useJsApiLoader, Marker, Polyline, PolygonF } from '@react-google-maps/api';
import './RouteMap.css';
import {
  viaServiceAreaEastern,
  viaServiceAreaWestern,
  uchicagoMainCampus,
  viaZoneStyle,
} from './viaServiceZone';

const toGooglePath = (coords) => coords.map(([lat, lng]) => ({ lat, lng }));

const serviceAreaOptions = {
  fillColor: viaZoneStyle.serviceArea.fillColor || '#4ecdc4',
  fillOpacity: viaZoneStyle.serviceArea.fillOpacity ?? 0.1,
  strokeColor: viaZoneStyle.serviceArea.color || '#4ecdc4',
  strokeOpacity: viaZoneStyle.serviceArea.opacity ?? 0.6,
  strokeWeight: viaZoneStyle.serviceArea.weight || 2,
  clickable: false,
};

const campusOptions = {
  fillColor: viaZoneStyle.campus.fillColor || '#8B0000',
  fillOpacity: viaZoneStyle.campus.fillOpacity ?? 0.08,
  strokeColor: viaZoneStyle.campus.color || '#8B0000',
  strokeOpacity: viaZoneStyle.campus.opacity ?? 0.5,
  strokeWeight: viaZoneStyle.campus.weight || 1,
  clickable: false,
};

const routePolylineOptions = {
  strokeColor: '#8B0000',
  strokeOpacity: 0.8,
  strokeWeight: 4,
};

const dashedPolylineOptions = {
  strokeColor: '#4ecdc4',
  strokeOpacity: 0,
  strokeWeight: 3,
  icons: [{
    icon: { path: 'M 0,-1 0,1', strokeOpacity: 0.7, scale: 4 },
    offset: '0',
    repeat: '20px',
  }],
};

const defaultCenter = { lat: 41.788064, lng: -87.601145 };

function GoogleRouteMap({ routeData, bookingData }) {
  const apiKey = process.env.REACT_APP_GOOGLE_MAPS_API_KEY || '';
  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: apiKey,
  });

  const mapRef = useRef(null);
  const onLoad = useCallback((map) => { mapRef.current = map; }, []);

  const routePoints = useMemo(() => {
    if (!routeData?.route) return [];
    return routeData.route.map(p => ({ lat: p.latlng.lat, lng: p.latlng.lng }));
  }, [routeData]);

  const stops = useMemo(() => {
    if (!routeData?.stops) return [];
    return routeData.stops.map(stop => ({
      position: { lat: stop.stop_location.latlng.lat, lng: stop.stop_location.latlng.lng },
      isPickup: stop.pickups && stop.pickups.length > 0,
      isDropoff: stop.dropoffs && stop.dropoffs.length > 0,
    }));
  }, [routeData]);

  const bookingLocations = useMemo(() => {
    const ride = bookingData?.prescheduled_recurring_series_rides?.[0];
    const details = ride?.prescheduled_recurring_series_ride_details;
    if (!details) return null;
    return {
      pickup: details.pickup?.location ? { lat: details.pickup.location.lat, lng: details.pickup.location.lng } : null,
      pickupName: details.pickup?.location?.description || 'Pickup',
      dropoff: details.dropoff?.location ? { lat: details.dropoff.location.lat, lng: details.dropoff.location.lng } : null,
      dropoffName: details.dropoff?.location?.description || 'Dropoff',
      pickupTime: details.pickup_ts,
      dropoffStartTime: details.dropoff_start_ts,
    };
  }, [bookingData]);

  const hasRouteData = routePoints.length > 0;
  const hasBookingLocations = bookingLocations && (bookingLocations.pickup || bookingLocations.dropoff);

  // Fit bounds once data is loaded
  useEffect(() => {
    if (!mapRef.current || !isLoaded) return;
    const points = [];
    if (hasRouteData) points.push(...routePoints);
    else if (hasBookingLocations) {
      if (bookingLocations.pickup) points.push(bookingLocations.pickup);
      if (bookingLocations.dropoff) points.push(bookingLocations.dropoff);
    }
    if (points.length === 0) return;
    const bounds = new window.google.maps.LatLngBounds();
    points.forEach(p => bounds.extend(p));
    mapRef.current.fitBounds(bounds, 30);
  }, [isLoaded, hasRouteData, hasBookingLocations, routePoints, bookingLocations]);

  const formatTime = (ts) => {
    if (!ts) return '';
    return new Date(ts * 1000).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  if (loadError) {
    return <div className="route-map-error"><p>Failed to load Google Maps. Check your API key.</p></div>;
  }

  if (!isLoaded) {
    return <div className="route-map-loading">Loading map...</div>;
  }

  if (!hasRouteData && !hasBookingLocations) {
    return <div className="route-map-error"><p>No route data available</p></div>;
  }

  const makePinIcon = (fill, stroke) => ({
    url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" width="25" height="41"><path fill="${fill}" stroke="${stroke}" stroke-width="1.5" d="M12.5 0C5.6 0 0 5.6 0 12.5c0 9.9 12.5 28.5 12.5 28.5S25 22.4 25 12.5C25 5.6 19.4 0 12.5 0z"/><circle cx="12.5" cy="12.5" r="5.5" fill="white" opacity="0.85"/></svg>`
    )}`,
    scaledSize: new window.google.maps.Size(25, 41),
    anchor: new window.google.maps.Point(12, 41),
  });

  const pickupIcon = makePinIcon('#22c55e', '#15803d');
  const dropoffIcon = makePinIcon('#ef4444', '#b91c1c');
  const stopIcon    = makePinIcon('#f97316', '#c2410c');

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
        mapContainerStyle={{ height: 'clamp(220px, 40vh, 350px)', width: '100%', borderRadius: '12px' }}
        mapContainerClassName="route-map"
        center={defaultCenter}
        zoom={14}
        onLoad={onLoad}
        options={{
          disableDefaultUI: false,
          zoomControl: true,
          streetViewControl: false,
          rotateControl: false,
          fullscreenControl: false,
          tilt: 0,
          gestureHandling: 'greedy',
          clickableIcons: false,
          mapTypeId: 'hybrid',
          mapTypeControlOptions: { mapTypeIds: ['hybrid', 'roadmap'] },
          styles: [
            { featureType: 'poi', stylers: [{ visibility: 'off' }] },
            { featureType: 'transit', stylers: [{ visibility: 'off' }] },
          ],
        }}
      >
        <PolygonF paths={toGooglePath(viaServiceAreaEastern)} options={serviceAreaOptions} />
        <PolygonF paths={toGooglePath(viaServiceAreaWestern)} options={serviceAreaOptions} />
        <PolygonF paths={toGooglePath(uchicagoMainCampus)} options={campusOptions} />

        {hasRouteData && <Polyline path={routePoints} options={routePolylineOptions} />}

        {!hasRouteData && hasBookingLocations && bookingLocations.pickup && bookingLocations.dropoff && (
          <Polyline
            path={[bookingLocations.pickup, bookingLocations.dropoff]}
            options={dashedPolylineOptions}
          />
        )}

        {hasRouteData && stops.map((stop, i) => (
          <Marker
            key={`stop-${i}`}
            position={stop.position}
            icon={stop.isPickup ? pickupIcon : stop.isDropoff ? dropoffIcon : stopIcon}
            title={stop.isPickup ? 'Pickup' : stop.isDropoff ? 'Dropoff' : 'Stop'}
          />
        ))}

        {!hasRouteData && hasBookingLocations && (
          <>
            {bookingLocations.pickup && (
              <Marker
                position={bookingLocations.pickup}
                icon={pickupIcon}
                title={`Pickup: ${bookingLocations.pickupName}`}
              />
            )}
            {bookingLocations.dropoff && (
              <Marker
                position={bookingLocations.dropoff}
                icon={dropoffIcon}
                title={`Dropoff: ${bookingLocations.dropoffName}`}
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
