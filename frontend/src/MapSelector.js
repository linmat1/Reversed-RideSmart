import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, useMapEvents, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './MapSelector.css';

// Fix for default marker icons in react-leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// Custom icon for origin (green)
const originIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  tooltipAnchor: [16, -28],
  shadowSize: [41, 41]
});

// Custom icon for destination (red)
const destinationIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  tooltipAnchor: [16, -28],
  shadowSize: [41, 41]
});

// Component to handle map clicks
function MapClickHandler({ onMapClick, selectMode }) {
  useMapEvents({
    click(e) {
      if (selectMode === 'origin' || selectMode === 'destination') {
        onMapClick(e.latlng, selectMode);
      }
    },
  });
  return null;
}

// Component to center map on a specific location (only used when explicitly needed)
function MapCenter({ center, zoom, shouldCenter }) {
  const map = useMap();
  useEffect(() => {
    if (shouldCenter && center) {
      map.setView(center, zoom || map.getZoom());
    }
  }, [shouldCenter, center, zoom, map]);
  return null;
}

function MapSelector({ origin, destination, onOriginSelect, onDestinationSelect, selectMode, centerOnOrigin }) {
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    setMapReady(true);
  }, []);

  const handleMapClick = (latlng, mode) => {
    const coords = {
      lat: latlng.lat,
      lng: latlng.lng
    };

    if (mode === 'origin') {
      onOriginSelect(coords);
    } else if (mode === 'destination') {
      onDestinationSelect(coords);
    }
  };

  // Default center (University of Chicago area)
  const defaultCenter = [41.788064, -87.601145];
  const defaultZoom = 13;

  if (!mapReady) {
    return <div className="map-loading">Loading map...</div>;
  }

  return (
    <div className="map-selector-container">
      <MapContainer
        center={defaultCenter}
        zoom={defaultZoom}
        style={{ height: '400px', width: '100%', borderRadius: '12px' }}
        className="map-container"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {centerOnOrigin && origin && (
          <MapCenter center={[origin.lat, origin.lng]} zoom={15} shouldCenter={centerOnOrigin} />
        )}
        <MapClickHandler onMapClick={handleMapClick} selectMode={selectMode} />
        {origin && (
          <Marker position={[origin.lat, origin.lng]} icon={originIcon}>
          </Marker>
        )}
        {destination && (
          <Marker position={[destination.lat, destination.lng]} icon={destinationIcon}>
          </Marker>
        )}
      </MapContainer>
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

export default MapSelector;

