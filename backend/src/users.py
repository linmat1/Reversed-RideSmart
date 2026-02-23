"""
User Configuration File
Loads user credentials from environment variables (.env file).

Each user needs:
- name: Display name for the frontend
- auth_token: The authentication token from the RideSmart app
- user_id: The user ID (found in the auth token or API responses)
- password or password_hash: For login (admin-provided). Set USER_X_PASSWORD=plaintext
  or USER_X_PASSWORD_HASH=scrypt:... (generate with: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your_password'))")

Environment variables format:
USER_MATTHEW_NAME=Matthew
USER_MATTHEW_AUTH_TOKEN=your_token_here
USER_MATTHEW_USER_ID=3922267
USER_MATTHEW_PASSWORD=admin_set_password

etc.
"""

import os
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

# Load environment variables from .env file
# Look for .env in the backend directory
backend_dir = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(backend_dir, '.env')

# Try to load .env file
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    print(f"Warning: .env file not found at {env_path}")
    print("Please create .env file from .env.example template")

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
    password_key = f'USER_{user_key.upper()}_PASSWORD'
    password_hash_key = f'USER_{user_key.upper()}_PASSWORD_HASH'

    name = os.getenv(name_key)
    auth_token = os.getenv(token_key)
    user_id_str = os.getenv(id_key)
    plain_password = os.getenv(password_key)
    stored_hash = os.getenv(password_hash_key)

    if name and auth_token and user_id_str:
        try:
            user_id = int(user_id_str)
            entry = {
                "name": name,
                "auth_token": auth_token,
                "user_id": user_id
            }
            # Login password: prefer PASSWORD_HASH; else hash PASSWORD on load
            if stored_hash:
                entry["password_hash"] = stored_hash
            elif plain_password:
                entry["password_hash"] = generate_password_hash(plain_password)
            USERS[user_key] = entry
        except ValueError:
            print(f"Warning: Invalid user_id for user {user_key}: {user_id_str}")
    else:
        # Warn about missing fields
        missing = []
        if not name:
            missing.append('NAME')
        if not auth_token:
            missing.append('AUTH_TOKEN')
        if not user_id_str:
            missing.append('USER_ID')
        if missing:
            print(f"Warning: User {user_key} is missing: {', '.join(missing)}")

# Warn if no users were loaded
if not USERS:
    print("ERROR: No users loaded from environment variables!")
    print("Please check your .env file and ensure it follows the format:")
    print("  USER_USERNAME_NAME=Display Name")
    print("  USER_USERNAME_AUTH_TOKEN=your_token")
    print("  USER_USERNAME_USER_ID=1234567")

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
    """List all available users for the frontend (for login dropdown)."""
    return [
        {"id": key, "name": user["name"]}
        for key, user in USERS.items()
    ]


def verify_password(user_key, password):
    """
    Verify that the given password matches the admin-set password for this user.
    Returns True if the user exists, has a password set, and the password matches.
    """
    user = USERS.get(user_key)
    if not user:
        return False
    stored_hash = user.get("password_hash")
    if not stored_hash:
        return False
    return check_password_hash(stored_hash, password)


def user_has_password(user_key):
    """Return True if this user has a login password configured."""
    user = USERS.get(user_key)
    return bool(user and user.get("password_hash"))
