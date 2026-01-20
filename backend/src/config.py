import random
import time
from src.destination_config import get_active_origin, get_active_destination
from src.users import get_auth_token, get_user_id, DEFAULT_USER

# Global configuration variables
charging = False
battery_level = random.randint(80, 85)

# Default auth token (for backward compatibility)
auth_token = get_auth_token(DEFAULT_USER)
user_id = get_user_id(DEFAULT_USER)

# Default origin and destination for search_ride
# These are loaded from destination_config.py based on ACTIVE_LOCATION
default_origin = get_active_origin()
default_destination = get_active_destination()

# Passenger configuration - always book for 2 people (self + extra rider)
n_passengers = 2  # Total number of passengers
include_extra_rider = True  # Whether to include an extra rider

# Function to get current timestamp (for "now" timestamps)
def get_current_timestamp():
    return time.time()