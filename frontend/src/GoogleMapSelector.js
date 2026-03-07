import React, { useEffect, useState, useCallback, useRef } from 'react';
import { GoogleMap, useJsApiLoader, Marker, Polygon } from '@react-google-maps/api';
import { GOOGLE_MAPS_API_KEY } from './mapConfig';
import './MapSelector.css';
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

const containerStyle = { width: '100%', borderRadius: '12px', height: 'clamp(260px, 50vh, 420px)' };
const defaultCenter = { lat: 41.788064, lng: -87.601145 };

const cleanStyles = [
  { featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit', elementType: 'labels.icon', stylers: [{ visibility: 'off' }] },
];

function GoogleMapSelector({ origin, destination, onOriginSelect, onDestinationSelect, selectMode, centerOnOrigin }) {
  const { isLoaded } = useJsApiLoader({ id: 'google-map-script', googleMapsApiKey: GOOGLE_MAPS_API_KEY });
  const [mapReady, setMapReady] = useState(false);
  const mapRef = useRef(null);

  useEffect(() => { setMapReady(true); }, []);

  const onLoad = useCallback((map) => { mapRef.current = map; }, []);
  const onUnmount = useCallback(() => { mapRef.current = null; }, []);

  useEffect(() => {
    if (centerOnOrigin && origin && mapRef.current) {
      mapRef.current.panTo({ lat: origin.lat, lng: origin.lng });
      mapRef.current.setZoom(15);
    }
  }, [centerOnOrigin, origin]);

  useEffect(() => {
    if (origin && destination && mapRef.current) {
      const bounds = new window.google.maps.LatLngBounds();
      bounds.extend({ lat: origin.lat, lng: origin.lng });
      bounds.extend({ lat: destination.lat, lng: destination.lng });
      mapRef.current.fitBounds(bounds, 50);
    }
  }, [origin, destination]);

  const handleClick = useCallback((e) => {
    const coords = { lat: e.latLng.lat(), lng: e.latLng.lng() };
    if (selectMode === 'origin') onOriginSelect(coords);
    else if (selectMode === 'destination') onDestinationSelect(coords);
  }, [selectMode, onOriginSelect, onDestinationSelect]);

  if (!mapReady || !isLoaded) {
    return <div className="map-loading">Loading map...</div>;
  }

  return (
    <div className="map-selector-container">
      <GoogleMap
        mapContainerStyle={containerStyle}
        mapContainerClassName="map-container"
        center={defaultCenter}
        zoom={13}
        onLoad={onLoad}
        onUnmount={onUnmount}
        onClick={handleClick}
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
        }}
      >
        <Polygon paths={toGooglePath(viaServiceAreaEastern)} options={viaZoneStyleGoogle.serviceArea} />
        <Polygon paths={toGooglePath(viaServiceAreaWestern)} options={viaZoneStyleGoogle.serviceArea} />
        <Polygon paths={toGooglePath(uchicagoMainCampus)} options={viaZoneStyleGoogle.campus} />

        {origin && (
          <Marker position={{ lat: origin.lat, lng: origin.lng }} icon={GREEN_MARKER} />
        )}
        {destination && (
          <Marker position={{ lat: destination.lat, lng: destination.lng }} icon={RED_MARKER} />
        )}
      </GoogleMap>
      <div className="map-instructions">
        {selectMode === 'origin' && (
          <p>Click on the map to set the <strong>origin</strong> (green marker)</p>
        )}
        {selectMode === 'destination' && (
          <p>Click on the map to set the <strong>destination</strong> (red marker)</p>
        )}
        {selectMode === 'none' && origin && destination && (
          <p>Both locations selected. Click "Search for Rides" to continue.</p>
        )}
      </div>
    </div>
  );
}

export default GoogleMapSelector;
