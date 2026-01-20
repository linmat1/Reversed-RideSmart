"""
User Configuration File
Add new users here with their auth tokens.

Each user needs:
- name: Display name for the frontend
- auth_token: The authentication token from the RideSmart app
- user_id: The user ID (found in the auth token or API responses)
"""

# Dictionary of all available users
USERS = {
    "matthew": {
        "name": "Matthew",
        "auth_token": "2|1:0|10:1766628685|4:user|16:MDo6MzkyMjI2Nw==|4963019708d112f67c6becd48c16172837faf99dff1bc5d1ffe87c44a20e42ab",
        "user_id": 3922267
    },

    "tomaslv": {
        "name": "Tomas",
        "auth_token": "2|1:0|10:1755430822|4:user|12:MDo6MTQ0MzU=|56dcc3456c7e4df66ea6f718f3161351b3a786449b220007e2a5e6891c8936ac",
        "user_id": 14435
    },

    "joshuacheung": {
        "name": "Joshua Cheung",
        "auth_token": "2|1:0|10:1757091676|4:user|12:MDo6Tm9uZQ==|6eed2aa6bc04e31c5c5f6fa5648791137ba36b62860a4e5cd37e10b968af0dc4",
        "user_id": 3880693
    },

    
    # Add more users below following this format:
    # "username": {
    #     "name": "Display Name",
    #     "auth_token": "paste_auth_token_here",
    #     "user_id": 1234567
    # },
}

# Default user (used if no user is specified)
DEFAULT_USER = "matthew"


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
