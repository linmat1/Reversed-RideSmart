import random
import time
from src.destination_config import get_active_origin, get_active_destination

# Global configuration variables
charging = False
battery_level = random.randint(80, 85)
auth_token = "2|1:0|10:1766628685|4:user|16:MDo6MzkyMjI2Nw==|4963019708d112f67c6becd48c16172837faf99dff1bc5d1ffe87c44a20e42ab"

# Default origin and destination for search_ride
# These are loaded from destination_config.py based on ACTIVE_LOCATION
default_origin = get_active_origin()
default_destination = get_active_destination()

# Function to get current timestamp (for "now" timestamps)
def get_current_timestamp():
    return time.time()