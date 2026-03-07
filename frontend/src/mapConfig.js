const MAP_PROVIDER = (process.env.REACT_APP_MAP_PROVIDER || 'osm').toLowerCase();

export const useGoogleMaps = MAP_PROVIDER === 'google';
export const GOOGLE_MAPS_API_KEY = process.env.REACT_APP_GOOGLE_MAPS_API_KEY || '';
