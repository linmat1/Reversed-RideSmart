import requests
import time

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "RideSmart/1.0"
_last_request_time = 0.0


def reverse_geocode(lat: float, lng: float) -> dict | None:
    """
    Convert latitude/longitude coordinates to a human-readable address
    using the OpenStreetMap Nominatim API (free, no key required).

    Args:
        lat: Latitude (e.g. 41.7878692)
        lng: Longitude (e.g. -87.5908127)

    Returns:
        dict with keys:
            - full_address: Complete formatted address string
            - short_address: Abbreviated version (name/house + street)
            - raw: Full Nominatim response for further inspection
        None if the request fails.
    """
    global _last_request_time

    # Nominatim requires max 1 request/sec
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
        short_address = _build_short_address(data)

        return {
            "full_address": full_address,
            "short_address": short_address,
            "raw": data,
        }

    except requests.exceptions.RequestException as e:
        print(f"Reverse geocoding failed: {e}")
        return None


def _build_short_address(data: dict) -> str:
    """Build a concise address from Nominatim response fields."""
    name = data.get("name", "")
    addr = data.get("address", {})

    house = addr.get("house_number", "")
    road = addr.get("road", "")

    if name and name != road:
        return name
    parts = [p for p in (house, road) if p]
    return " ".join(parts) if parts else data.get("display_name", "Unknown")


def get_street_address(lat: float, lng: float) -> str | None:
    """
    Return just the street address (e.g. "1414 E 59th Street") for given coordinates.

    Args:
        lat: Latitude
        lng: Longitude

    Returns:
        Street address string, or None if the request fails.
    """
    result = reverse_geocode(lat, lng)
    if result is None:
        return None

    addr = result["raw"].get("address", {})
    house = addr.get("house_number", "")
    road = addr.get("road", "")

    parts = [p for p in (house, road) if p]
    return " ".join(parts) if parts else None


if __name__ == "__main__":
    # I-House at UChicago
    result = reverse_geocode(41.7878692, -87.5908127)
    if result:
        print(f"Full:  {result['full_address']}")
        print(f"Short: {result['short_address']}")
    else:
        print("Geocoding failed.")

    print()
    street = get_street_address(41.787964, -87.590929)
    print(f"Street: {street}")
