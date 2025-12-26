"""
Destination Configuration File
Easily manage multiple origin/destination pairs for ride searches.

To use a different location pair:
1. Set ACTIVE_LOCATION to the name of the location pair you want to use
2. Or add a new location pair to LOCATIONS and set ACTIVE_LOCATION to its name
"""

# Set this to the name of the location pair you want to use as default
ACTIVE_LOCATION = "i_house_to_cathey"

# Dictionary of all available location pairs
LOCATIONS = {
    "i_house_to_cathey": {
        "origin": {
            "latlng": {
                "lng": -87.5908127,
                "lat": 41.7878692
            },
            "full_geocoded_addr": "I-House.",
            "geocoded_addr": "I-House."
        },
        "destination": {
            "latlng": {
                "lng": -87.6011258,
                "lat": 41.7851539
            },
            "full_geocoded_addr": "Cathey Dining Commons.",
            "geocoded_addr": "Cathey Dining Commons."
        }
    },
    
    "both_out_of_bounds": {
        "origin": {
            "latlng": {
                "lng": -87.584570,
                "lat": 41.773292
            },
            "full_geocoded_addr": "",
            "geocoded_addr": ""
        },
        "destination": {
            "latlng": {
                "lng": -87.595388,
                "lat": 41.809724
            },
            "full_geocoded_addr": "<full address>",
            "geocoded_addr": "<short address>"
        }
    },
    
    "notnamed_to_ihouse": {
        "origin": {
            "latlng": {
                "lng": -87.601145,
                "lat": 41.788064
            },
            "full_geocoded_addr": "NA",
            "geocoded_addr": "NA"
        },
        "destination": {
            "latlng": {
                "lng": -87.5908127,
                "lat": 41.7878692
            },
            "full_geocoded_addr": "NA",
            "geocoded_addr": "NA"
        }
    }
}

def get_active_origin():
    """Get the origin for the currently active location pair."""
    if ACTIVE_LOCATION not in LOCATIONS:
        raise ValueError(f"Active location '{ACTIVE_LOCATION}' not found in LOCATIONS. "
                        f"Available locations: {list(LOCATIONS.keys())}")
    return LOCATIONS[ACTIVE_LOCATION]["origin"]

def get_active_destination():
    """Get the destination for the currently active location pair."""
    if ACTIVE_LOCATION not in LOCATIONS:
        raise ValueError(f"Active location '{ACTIVE_LOCATION}' not found in LOCATIONS. "
                        f"Available locations: {list(LOCATIONS.keys())}")
    return LOCATIONS[ACTIVE_LOCATION]["destination"]

def get_location_pair(location_name=None):
    """
    Get origin and destination for a specific location pair.
    
    Args:
        location_name: str, name of the location pair. If None, uses ACTIVE_LOCATION.
    
    Returns:
        tuple: (origin, destination) dictionaries
    """
    if location_name is None:
        location_name = ACTIVE_LOCATION
    
    if location_name not in LOCATIONS:
        raise ValueError(f"Location '{location_name}' not found. "
                        f"Available locations: {list(LOCATIONS.keys())}")
    
    loc = LOCATIONS[location_name]
    return loc["origin"], loc["destination"]

def list_available_locations():
    """List all available location pair names."""
    return list(LOCATIONS.keys())

