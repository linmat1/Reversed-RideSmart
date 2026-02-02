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

# Default DB path: backend/data/developer_logs.db (or /tmp on Vercel - read-only filesystem)
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _BACKEND_DIR / "data"
_DEFAULT_DB_PATH = _DATA_DIR / "developer_logs.db"

# On Vercel, deployment filesystem is read-only; use /tmp so the app doesn't crash.
def _resolve_db_path() -> Path:
    if os.environ.get("DEVELOPER_LOGS_DB"):
        return Path(os.environ["DEVELOPER_LOGS_DB"])
    if os.environ.get("VERCEL"):
        return Path("/tmp/developer_logs.db")
    return _DEFAULT_DB_PATH

# Module-level connection is not thread-safe; use a lock or per-thread connection.
# SQLite allows one writer at a time; we use a single connection with a lock for simplicity.
_connection: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def _get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    global _connection
    path = Path(db_path) if db_path is not None else _resolve_db_path()
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_log (
                run_started_at REAL NOT NULL,
                line_index INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (run_started_at, line_index)
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


def insert_orchestrator_line(
    run_started_at: float, line_index: int, message: str, db_path: Optional[Path] = None
) -> None:
    """Append one line to the orchestrator log for a run (persisted for reference)."""
    import time
    conn = _get_connection(db_path)
    with _lock:
        conn.execute(
            """
            INSERT INTO orchestrator_log (run_started_at, line_index, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (run_started_at, line_index, message, time.time()),
        )
        conn.commit()


def load_orchestrator_log_latest(db_path: Optional[Path] = None) -> List[str]:
    """Load the latest run's orchestrator log (messages in order). Returns [] if no runs."""
    conn = _get_connection(db_path)
    with _lock:
        cur = conn.execute(
            """
            SELECT message FROM orchestrator_log
            WHERE run_started_at = (SELECT MAX(run_started_at) FROM orchestrator_log)
            ORDER BY line_index ASC
            """
        )
        rows = cur.fetchall()
    return [r[0] for r in rows]


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


# --- Use Postgres when POSTGRES_URL or DATABASE_URL is set (e.g. Vercel + Neon/Supabase) ---
_postgres_url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
_storage = "sqlite"
_storage_path: Optional[Path] = _resolve_db_path()

if _postgres_url:
    try:
        from src.developer_logs_postgres import (
            init_schema as _pg_init_schema,
            insert_ride as _pg_insert_ride,
            update_ride_cancelled as _pg_update_ride_cancelled,
            insert_access as _pg_insert_access,
            load_ride_entries as _pg_load_ride_entries,
            load_access_entries as _pg_load_access_entries,
            insert_orchestrator_line as _pg_insert_orchestrator_line,
            load_orchestrator_log_latest as _pg_load_orchestrator_log_latest,
        )

        _storage = "postgres"
        _storage_path = None

        def init_schema(db_path: Optional[Path] = None) -> None:
            _pg_init_schema()

        def insert_ride(entry: Dict[str, Any], db_path: Optional[Path] = None) -> None:
            _pg_insert_ride(entry)

        def update_ride_cancelled(
            ride_id: int, cancelled_at: float, db_path: Optional[Path] = None
        ) -> bool:
            return _pg_update_ride_cancelled(ride_id, cancelled_at)

        def insert_access(entry: Dict[str, Any], db_path: Optional[Path] = None) -> None:
            _pg_insert_access(entry)

        def load_ride_entries(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
            return _pg_load_ride_entries()

        def load_access_entries(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
            return _pg_load_access_entries()

        def insert_orchestrator_line(
            run_started_at: float, line_index: int, message: str, db_path: Optional[Path] = None
        ) -> None:
            _pg_insert_orchestrator_line(run_started_at, line_index, message)

        def load_orchestrator_log_latest(db_path: Optional[Path] = None) -> List[str]:
            return _pg_load_orchestrator_log_latest()
    except Exception as e:
        print(f"Developer logs: Postgres not available ({e}), using SQLite")

# Log which storage is active so you can verify persistence (Supabase needs DATABASE_URL set).
def get_storage_info() -> Dict[str, Any]:
    out: Dict[str, Any] = {"storage": _storage}
    if _storage == "sqlite" and _storage_path:
        out["path"] = str(_storage_path)
        out["note"] = "On Vercel, SQLite uses /tmp and does not persist across invocations. Set DATABASE_URL for Supabase/Postgres."
    return out


if _storage == "postgres":
    print("Developer logs: using postgres (data persists)")
else:
    print(f"Developer logs: using sqlite at {_storage_path} (on Vercel this does not persist; set DATABASE_URL for Supabase)")
