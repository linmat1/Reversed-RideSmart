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
  { name: "I-House",              lat: 41.7878692,        lng: -87.5908127,        address: "1414 E 59th St, Chicago, IL 60637 ッ" },
  { name: "Cathey/RGGC",         lat: 41.78502283175025, lng: -87.60087796606041, address: "6017 S Ellis Ave, Chicago, IL 60637 ッ" },
  { name: "North/Baker",         lat: 41.79470772214912, lng: -87.59838456342511, address: "5500 S University Ave, Chicago, IL 60637 ッ" },
  { name: "Regenstein",          lat: 41.792022232216496, lng: -87.59972263872557, address: "1100 E 57th St, Chicago, IL 60637 ッ" },
  { name: "Woodlawn",            lat: 41.78512450866148,  lng: -87.59656658839626, address: "1156 E 61st St, Chicago, IL 60637 ッ" },
  { name: "Trader Joe's",        lat: 41.796424212644666, lng: -87.58835063681816, address: "1528 E 55th St, Chicago, IL 60615 ッ" },
  { name: "String's Ramen",      lat: 41.7994019817428,   lng: -87.589733805299,   address: "1453 E 53rd St, Chicago, IL 60615 ッ" },
  { name: "Max P Central",       lat: 41.79312581304385,  lng: -87.59967843343847, address: "1101 E 56th St, Chicago, IL 60637 ッ" },
  { name: "Harper",              lat: 41.787921894310315, lng: -87.59962260588838, address: "1116 E 59th St, Chicago, IL 60637 ッ" },
  { name: "Whole Foods",         lat: 41.80189679900715,  lng: -87.58797328827974, address: "5118 S Lake Park Ave, Chicago, IL 60615 ッ" },
  { name: "Logan",               lat: 41.785737510139455, lng: -87.60375791059381, address: "915 E 60th St, Chicago, IL 60637 ッ" },
  { name: "Target",              lat: 41.79961876437076,  lng: -87.5932695164637,  address: "1346 E 53rd St, Chicago, IL 60615 ッ" },
  { name: "Bookstore",           lat: 41.78966183926045,  lng: -87.60149498145064, address: "970 E 58th St, Chicago, IL 60637 ッ" },
  { name: "Booth",               lat: 41.78930581173118,  lng: -87.59613743124996, address: "5807 S Woodlawn Ave, Chicago, IL 60637 ッ" },
  { name: "Garfield (Red Line)", lat: 41.794603881293966, lng: -87.63111730088698, address: "220 W. Garfield Blvd., Chicago, IL 60609 ッ" },
  { name: "Zeta",               lat: 41.797086000127834, lng: -87.59645997666371, address: "5431 S Woodlawn Ave, Chicago, IL 60615 ッ" },
];

export default PRESET_LOCATIONS;
