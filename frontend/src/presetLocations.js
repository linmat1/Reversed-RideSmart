/**
 * Preset locations for quick selection on the map.
 * Add new locations here — they will appear in the dropdown.
 *
 * Format:
 *   { name: "Display Name", lat: 41.xxxx, lng: -87.xxxx, address: "optional street address" }
 *
 * If `address` is provided it is sent to the server as-is (no reverse geocode call).
 */
const PRESET_LOCATIONS = [
  { name: "I-House",               lat: 41.7878692,       lng: -87.5908127 },
  { name: "Cathey/RGGC", lat: 41.78502283175025, lng: -87.60087796606041 },
  { name: "North/Baker",          lat: 41.79470772214912, lng: -87.59838456342511 },
  { name: "Regenstein",            lat: 41.792022232216496, lng: -87.59972263872557, address: "1100 E 57th St, Chicago, IL 60637" },
  { name: "Woodlawn",              lat: 41.78512450866148, lng: -87.59656658839626 },
  { name: "Trader Joe's",          lat: 41.796424212644666, lng: -87.58835063681816 },
  { name: "String's Ramen",        lat: 41.7994019817428,  lng: -87.589733805299 },
  { name: "Max P Central",         lat: 41.79312581304385, lng: -87.59967843343847 },
  { name: "Harper",                lat: 41.787921894310315, lng: -87.59962260588838 },
  { name: "Whole Foods",           lat: 41.80189679900715, lng: -87.58797328827974 },
  { name: "Logan",                lat: 41.785737510139455, lng: -87.60375791059381 },
  { name: "Target",               lat: 41.79961876437076, lng: -87.5932695164637 },
  { name: "Bookstore",            lat: 41.78966183926045, lng: -87.60149498145064 },
  { name: "Booth",                lat: 41.78930581173118, lng: -87.59613743124996 },
];

export default PRESET_LOCATIONS;
