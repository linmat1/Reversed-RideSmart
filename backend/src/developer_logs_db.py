"""
SQLite persistence for developer logs (ride log + user access log).
Database file: backend/data/developer_logs.db
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

# Default DB path: backend/data/developer_logs.db
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _BACKEND_DIR / "data"
_DEFAULT_DB_PATH = _DATA_DIR / "developer_logs.db"

# Module-level connection is not thread-safe; use a lock or per-thread connection.
# SQLite allows one writer at a time; we use a single connection with a lock for simplicity.
_connection: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def _get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    global _connection
    path = db_path or os.environ.get("DEVELOPER_LOGS_DB") or str(_DEFAULT_DB_PATH)
    path = Path(path)
    with _lock:
        if _connection is None:
            path.parent.mkdir(parents=True, exist_ok=True)
            _connection = sqlite3.connect(str(path), check_same_thread=False)
            _connection.row_factory = sqlite3.Row
        return _connection


def init_schema(db_path: Optional[Path] = None) -> None:
    """Create tables if they do not exist."""
    conn = _get_connection(db_path)
    with _lock:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ride_log (
                id TEXT PRIMARY KEY,
                user_key TEXT NOT NULL,
                user_name TEXT NOT NULL,
                ride_id INTEGER,
                prescheduled_ride_id INTEGER,
                ride_type TEXT NOT NULL,
                source TEXT NOT NULL,
                lyft_for_user_key TEXT,
                lyft_for_user_name TEXT,
                cancelled INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                cancelled_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS access_log (
                id TEXT PRIMARY KEY,
                ip TEXT NOT NULL,
                user_agent TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.commit()


def insert_ride(entry: Dict[str, Any], db_path: Optional[Path] = None) -> None:
    """Insert a ride log entry."""
    conn = _get_connection(db_path)
    with _lock:
        conn.execute(
            """
            INSERT INTO ride_log (
                id, user_key, user_name, ride_id, prescheduled_ride_id,
                ride_type, source, lyft_for_user_key, lyft_for_user_name,
                cancelled, created_at, cancelled_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["id"],
                entry["user_key"],
                entry["user_name"],
                entry.get("ride_id"),
                entry.get("prescheduled_ride_id"),
                entry["ride_type"],
                entry["source"],
                entry.get("lyft_for_user_key"),
                entry.get("lyft_for_user_name"),
                1 if entry.get("cancelled") else 0,
                entry["created_at"],
                entry.get("cancelled_at"),
            ),
        )
        conn.commit()


def update_ride_cancelled(
    ride_id: int, cancelled_at: float, db_path: Optional[Path] = None
) -> bool:
    """Mark ride(s) with this ride_id or prescheduled_ride_id as cancelled. Returns True if any row was updated."""
    conn = _get_connection(db_path)
    with _lock:
        cur = conn.execute(
            """
            UPDATE ride_log
            SET cancelled = 1, cancelled_at = ?
            WHERE (ride_id = ? OR prescheduled_ride_id = ?) AND cancelled = 0
            """,
            (cancelled_at, ride_id, ride_id),
        )
        conn.commit()
        return cur.rowcount > 0


def insert_access(entry: Dict[str, Any], db_path: Optional[Path] = None) -> None:
    """Insert an access log entry."""
    conn = _get_connection(db_path)
    with _lock:
        conn.execute(
            """
            INSERT INTO access_log (id, ip, user_agent, path, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                entry["id"],
                entry["ip"],
                entry["user_agent"],
                entry["path"],
                entry["created_at"],
            ),
        )
        conn.commit()


def load_ride_entries(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load all ride log entries, oldest first (so reversed() in memory gives newest first)."""
    conn = _get_connection(db_path)
    with _lock:
        cur = conn.execute(
            "SELECT * FROM ride_log ORDER BY created_at ASC"
        )
        rows = cur.fetchall()
    return [_row_to_ride_entry(r) for r in rows]


def load_access_entries(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load all access log entries, oldest first."""
    conn = _get_connection(db_path)
    with _lock:
        cur = conn.execute(
            "SELECT * FROM access_log ORDER BY created_at ASC"
        )
        rows = cur.fetchall()
    return [_row_to_access_entry(r) for r in rows]


def _row_to_ride_entry(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_key": row["user_key"],
        "user_name": row["user_name"],
        "ride_id": row["ride_id"],
        "prescheduled_ride_id": row["prescheduled_ride_id"],
        "ride_type": row["ride_type"],
        "source": row["source"],
        "lyft_for_user_key": row["lyft_for_user_key"],
        "lyft_for_user_name": row["lyft_for_user_name"],
        "cancelled": bool(row["cancelled"]),
        "created_at": row["created_at"],
        "cancelled_at": row["cancelled_at"],
    }


def _row_to_access_entry(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "ip": row["ip"],
        "user_agent": row["user_agent"],
        "path": row["path"],
        "created_at": row["created_at"],
    }
