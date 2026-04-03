import React, { useEffect, useRef, useCallback } from 'react';
import { GoogleMap, useJsApiLoader, Marker, PolygonF } from '@react-google-maps/api';
import './MapSelector.css';
import {
  viaServiceAreaEastern,
  viaServiceAreaWestern,
  uchicagoMainCampus,
  viaZoneStyle,
} from './viaServiceZone';

// Convert [lat, lng] arrays to {lat, lng} objects for Google Maps
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

const defaultCenter = { lat: 41.788064, lng: -87.601145 };
const defaultZoom = 13;

function GoogleMapSelector({ origin, destination, onOriginSelect, onDestinationSelect, selectMode, centerOnOrigin }) {
  const apiKey = process.env.REACT_APP_GOOGLE_MAPS_API_KEY || '';
  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: apiKey,
  });

  const mapRef = useRef(null);

  const onLoad = useCallback((map) => {
    mapRef.current = map;
  }, []);

  // Fit bounds when both markers are set
  useEffect(() => {
    if (!mapRef.current || !origin || !destination) return;
    const bounds = new window.google.maps.LatLngBounds();
    bounds.extend({ lat: origin.lat, lng: origin.lng });
    bounds.extend({ lat: destination.lat, lng: destination.lng });
    mapRef.current.fitBounds(bounds, 50);
  }, [origin, destination]);

  // Center on origin when requested (e.g. current location)
  useEffect(() => {
    if (!mapRef.current || !centerOnOrigin || !origin) return;
    mapRef.current.panTo({ lat: origin.lat, lng: origin.lng });
    mapRef.current.setZoom(15);
  }, [centerOnOrigin, origin]);

  const handleMapClick = useCallback((e) => {
    const coords = { lat: e.latLng.lat(), lng: e.latLng.lng() };
    if (selectMode === 'origin') {
      onOriginSelect(coords);
    } else if (selectMode === 'destination') {
      onDestinationSelect(coords);
    }
  }, [selectMode, onOriginSelect, onDestinationSelect]);

  if (loadError) {
    return (
      <div className="map-selector-container">
        <div className="map-loading">Failed to load Google Maps. Check your API key.</div>
      </div>
    );
  }

  if (!isLoaded) {
    return (
      <div className="map-selector-container">
        <div className="map-loading">Loading map...</div>
      </div>
    );
  }

  const cursor = selectMode === 'origin' || selectMode === 'destination' ? 'crosshair' : 'grab';

  return (
    <div className="map-selector-container">
      <GoogleMap
        mapContainerStyle={{ width: '100%', borderRadius: '12px' }}
        mapContainerClassName="map-container"
        center={defaultCenter}
        zoom={defaultZoom}
        onLoad={onLoad}
        onClick={handleMapClick}
        options={{
          cursor,
          disableDefaultUI: false,
          zoomControl: true,
          mapTypeId: 'satellite',
          styles: [
            { featureType: 'poi', stylers: [{ visibility: 'off' }] },
            { featureType: 'transit', stylers: [{ visibility: 'off' }] },
          ],
        }}
      >
        <PolygonF paths={toGooglePath(viaServiceAreaEastern)} options={serviceAreaOptions} />
        <PolygonF paths={toGooglePath(viaServiceAreaWestern)} options={serviceAreaOptions} />
        <PolygonF paths={toGooglePath(uchicagoMainCampus)} options={campusOptions} />

        {origin && (
          <Marker
            position={{ lat: origin.lat, lng: origin.lng }}
            label={{ text: 'A', color: '#fff', fontWeight: 'bold' }}
            title="Origin"
          />
        )}
        {destination && (
          <Marker
            position={{ lat: destination.lat, lng: destination.lng }}
            label={{ text: 'B', color: '#fff', fontWeight: 'bold' }}
            title="Destination"
          />
        )}
      </GoogleMap>

      <div className="map-instructions">
        {selectMode === 'origin' && (
          <p>Click on the map to set the <strong>origin</strong> (A)</p>
        )}
        {selectMode === 'destination' && (
          <p>Click on the map to set the <strong>destination</strong> (B)</p>
        )}
        {selectMode === 'none' && origin && destination && (
          <p>Both locations selected. Click "Search for Rides" to continue.</p>
        )}
      </div>
    </div>
  );
}

export default GoogleMapSelector;
