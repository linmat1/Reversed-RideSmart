"""
Logging module for RideSmart application.
Logs all booking actions, cancellations, and Lyft orchestrator activities.
"""

import os
import json
from datetime import datetime
from pathlib import Path

# Get the backend directory
BACKEND_DIR = Path(__file__).parent.parent
LOGS_DIR = BACKEND_DIR / 'logs'

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)

# Log file paths
BOOKING_LOG_FILE = LOGS_DIR / 'bookings.log'
LYFT_ORCHESTRATOR_LOG_FILE = LOGS_DIR / 'lyft_orchestrator.log'
ACTIONS_LOG_FILE = LOGS_DIR / 'actions.log'  # Combined log of all actions


def _get_timestamp():
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


def _write_log(log_file, log_entry):
    """
    Write a log entry to a file.
    
    Args:
        log_file: Path to the log file
        log_entry: dict with log data
    """
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"Error writing to log file {log_file}: {e}")


def log_booking(action, user_key, user_name=None, **kwargs):
    """
    Log a booking action (book or cancel).
    
    Args:
        action: str, 'book' or 'cancel'
        user_key: str, user key
        user_name: str, optional user name
        **kwargs: Additional data to log (ride_id, proposal_uuid, origin, destination, etc.)
    """
    log_entry = {
        'timestamp': _get_timestamp(),
        'action': action,
        'user_key': user_key,
        'user_name': user_name,
        **kwargs
    }
    
    _write_log(BOOKING_LOG_FILE, log_entry)
    _write_log(ACTIONS_LOG_FILE, log_entry)


def log_lyft_orchestrator(action, original_user_key, original_user_name=None, **kwargs):
    """
    Log Lyft orchestrator actions.
    
    Args:
        action: str, action type (e.g., 'start', 'search', 'book', 'cancel', 'success', 'failed')
        original_user_key: str, the user who wants the Lyft
        original_user_name: str, optional user name
        **kwargs: Additional data (filler_user, ride_id, route_info, etc.)
    """
    log_entry = {
        'timestamp': _get_timestamp(),
        'action': action,
        'original_user_key': original_user_key,
        'original_user_name': original_user_name,
        **kwargs
    }
    
    _write_log(LYFT_ORCHESTRATOR_LOG_FILE, log_entry)
    _write_log(ACTIONS_LOG_FILE, log_entry)


def log_search(user_key, user_name=None, route_id=None, origin=None, destination=None, proposal_count=0):
    """
    Log a search action.
    
    Args:
        user_key: str, user key
        user_name: str, optional user name
        route_id: str, optional route ID
        origin: dict, optional origin location
        destination: dict, optional destination location
        proposal_count: int, number of proposals found
    """
    log_entry = {
        'timestamp': _get_timestamp(),
        'action': 'search',
        'user_key': user_key,
        'user_name': user_name,
        'route_id': route_id,
        'origin': origin,
        'destination': destination,
        'proposal_count': proposal_count
    }
    
    _write_log(ACTIONS_LOG_FILE, log_entry)


def get_recent_logs(log_file=None, limit=100):
    """
    Get recent log entries.
    
    Args:
        log_file: Path to log file, or None for actions log
        limit: Maximum number of entries to return
    
    Returns:
        list of log entries (most recent first)
    """
    if log_file is None:
        log_file = ACTIONS_LOG_FILE
    
    if not os.path.exists(log_file):
        return []
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Get last N lines
        recent_lines = lines[-limit:] if len(lines) > limit else lines
        
        # Parse JSON and reverse to get most recent first
        logs = []
        for line in reversed(recent_lines):
            try:
                logs.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
        
        return logs
    except Exception as e:
        print(f"Error reading log file {log_file}: {e}")
        return []
