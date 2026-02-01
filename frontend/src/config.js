/**
 * API base URL for the backend.
 * - Uses REACT_APP_API_URL when set (e.g. in Vercel frontend env).
 * - In the browser, only falls back to localhost when the site is opened from localhost
 *   (development). Otherwise we use '' so we don't trigger "scan for local devices" / local
 *   network prompts. Set REACT_APP_API_URL in production so the app works.
 */
let _cached = null;
export function getApiBase() {
  if (_cached !== null) return _cached;
  const env = process.env.REACT_APP_API_URL;
  if (env && env.trim()) {
    _cached = env.trim().replace(/\/$/, '');
    return _cached;
  }
  if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
    _cached = 'http://localhost:5001';
    return _cached;
  }
  _cached = '';
  return _cached;
}

/** True when we're in production and the backend URL was not configured. */
export function isApiMissing() {
  return typeof window !== 'undefined' && window.location.hostname !== 'localhost' && !(process.env.REACT_APP_API_URL && process.env.REACT_APP_API_URL.trim());
}
