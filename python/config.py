import random
import time

# Global configuration variables
charging = False
battery_level = random.randint(80, 85)
auth_token = "2|1:0|10:1766628685|4:user|16:MDo6MzkyMjI2Nw==|4963019708d112f67c6becd48c16172837faf99dff1bc5d1ffe87c44a20e42ab"

# Default origin and destination for search_ride
default_origin = {
    "latlng": {
        "lng": -87.5908127,
        "lat": 41.7878692
    },
    "full_geocoded_addr": "I-House.",
    "geocoded_addr": "I-House."
}

default_destination = {
    "latlng": {
        "lng": -87.6011258,
        "lat": 41.7851539
    },
    "full_geocoded_addr": "Cathey Dining Commons.",
    "geocoded_addr": "Cathey Dining Commons."
}

# Function to get current timestamp (for "now" timestamps)
def get_current_timestamp():
    return time.time()