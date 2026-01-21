"""
User Configuration File
Loads user credentials from environment variables (.env file).

Each user needs:
- name: Display name for the frontend
- auth_token: The authentication token from the RideSmart app
- user_id: The user ID (found in the auth token or API responses)

Environment variables format:
USER_MATTHEW_NAME=Matthew
USER_MATTHEW_AUTH_TOKEN=your_token_here
USER_MATTHEW_USER_ID=3922267

USER_TOMASLV_NAME=Tomas
USER_TOMASLV_AUTH_TOKEN=your_token_here
USER_TOMASLV_USER_ID=14435

etc.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
# Look for .env in the backend directory
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)

# Dictionary of all available users (loaded from environment variables)
USERS = {}

# Load users from environment variables
# Look for variables matching pattern: USER_{USERNAME}_{FIELD}
env_vars = os.environ
user_keys = set()

# Find all user keys from environment variables
for key in env_vars.keys():
    if key.startswith('USER_') and key.endswith('_NAME'):
        # Extract username from key like USER_MATTHEW_NAME -> matthew
        user_key = key.replace('USER_', '').replace('_NAME', '').lower()
        user_keys.add(user_key)

# Build USERS dictionary from environment variables
for user_key in user_keys:
    name_key = f'USER_{user_key.upper()}_NAME'
    token_key = f'USER_{user_key.upper()}_AUTH_TOKEN'
    id_key = f'USER_{user_key.upper()}_USER_ID'
    
    name = os.getenv(name_key)
    auth_token = os.getenv(token_key)
    user_id_str = os.getenv(id_key)
    
    if name and auth_token and user_id_str:
        try:
            user_id = int(user_id_str)
            USERS[user_key] = {
                "name": name,
                "auth_token": auth_token,
                "user_id": user_id
            }
        except ValueError:
            print(f"Warning: Invalid user_id for user {user_key}: {user_id_str}")

# Default user (used if no user is specified)
# Can be overridden with DEFAULT_USER environment variable
DEFAULT_USER = os.getenv('DEFAULT_USER', 'matthew')


def get_user(user_key=None):
    """
    Get user configuration by key.
    
    Args:
        user_key: str, the key of the user in USERS dict. If None, uses DEFAULT_USER.
    
    Returns:
        dict with user configuration, or None if not found
    """
    if user_key is None:
        user_key = DEFAULT_USER
    
    return USERS.get(user_key)


def get_auth_token(user_key=None):
    """Get auth token for a specific user."""
    user = get_user(user_key)
    if user:
        return user.get("auth_token")
    return None


def get_user_id(user_key=None):
    """Get user ID for a specific user."""
    user = get_user(user_key)
    if user:
        return user.get("user_id")
    return None


def list_users():
    """List all available users for the frontend."""
    return [
        {"id": key, "name": user["name"]}
        for key, user in USERS.items()
    ]
