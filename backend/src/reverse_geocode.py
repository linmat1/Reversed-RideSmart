import os
import requests
import time

_MAP_PROVIDER = os.environ.get("MAP_PROVIDER", "osm").lower()
_GOOGLE_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# --- Nominatim (OSM) -----------------------------------------------------------

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "RideSmart/1.0"
_last_request_time = 0.0


def _nominatim_reverse(lat: float, lng: float) -> dict | None:
    global _last_request_time

    elapsed = time.time() - _last_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    params = {
        "lat": lat,
        "lon": lng,
        "format": "jsonv2",
        "addressdetails": 1,
    }
    headers = {"User-Agent": _USER_AGENT}

    try:
        _last_request_time = time.time()
        resp = requests.get(_NOMINATIM_URL, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        full_address = data.get("display_name", "")
        short_address = _build_short_address_nominatim(data)

        return {
            "full_address": full_address,
            "short_address": short_address,
            "raw": data,
        }

    except requests.exceptions.RequestException as e:
        print(f"Reverse geocoding (Nominatim) failed: {e}")
        return None


def _build_short_address_nominatim(data: dict) -> str:
    name = data.get("name", "")
    addr = data.get("address", {})

    house = addr.get("house_number", "")
    road = addr.get("road", "")

    if name and name != road:
        return name
    parts = [p for p in (house, road) if p]
    return " ".join(parts) if parts else data.get("display_name", "Unknown")


# --- Google Geocoding -----------------------------------------------------------

_GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def _google_reverse(lat: float, lng: float) -> dict | None:
    if not _GOOGLE_API_KEY:
        print("GOOGLE_MAPS_API_KEY not set, falling back to Nominatim")
        return _nominatim_reverse(lat, lng)

    params = {
        "latlng": f"{lat},{lng}",
        "key": _GOOGLE_API_KEY,
    }

    try:
        resp = requests.get(_GOOGLE_GEOCODE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "OK" or not data.get("results"):
            print(f"Google reverse geocode status: {data.get('status')}")
            return None

        result = data["results"][0]
        full_address = result.get("formatted_address", "")
        short_address = _build_short_address_google(result)

        raw_compat = {
            "display_name": full_address,
            "address": _google_components_to_nominatim(result),
            "_google_raw": result,
        }

        return {
            "full_address": full_address,
            "short_address": short_address,
            "raw": raw_compat,
        }

    except requests.exceptions.RequestException as e:
        print(f"Reverse geocoding (Google) failed: {e}")
        return None


def _build_short_address_google(result: dict) -> str:
    components = {c["types"][0]: c["short_name"] for c in result.get("address_components", []) if c.get("types")}
    street_number = components.get("street_number", "")
    route = components.get("route", "")
    premise = components.get("premise", "")
    if premise:
        return premise
    parts = [p for p in (street_number, route) if p]
    return " ".join(parts) if parts else result.get("formatted_address", "Unknown")


def _google_components_to_nominatim(result: dict) -> dict:
    """Map Google address_components to a Nominatim-like address dict for backend compat."""
    components = {}
    for c in result.get("address_components", []):
        for t in c.get("types", []):
            components[t] = c.get("long_name", "")

    return {
        "house_number": components.get("street_number", ""),
        "road": components.get("route", ""),
        "city": components.get("locality", ""),
        "state": components.get("administrative_area_level_1", ""),
        "postcode": components.get("postal_code", ""),
        "country": components.get("country", ""),
    }


# --- Public API (delegates based on MAP_PROVIDER) ------------------------------

def reverse_geocode(lat: float, lng: float) -> dict | None:
    """
    Convert lat/lng to a human-readable address.
    Delegates to Google or Nominatim depending on MAP_PROVIDER env var.

    Returns dict with keys: full_address, short_address, raw  —  or None on failure.
    """
    if _MAP_PROVIDER == "google":
        return _google_reverse(lat, lng)
    return _nominatim_reverse(lat, lng)


def get_street_address(lat: float, lng: float) -> str | None:
    """Return just the street address for given coordinates."""
    result = reverse_geocode(lat, lng)
    if result is None:
        return None

    addr = result["raw"].get("address", {})
    house = addr.get("house_number", "")
    road = addr.get("road", "")

    parts = [p for p in (house, road) if p]
    return " ".join(parts) if parts else None

