"""
Postgres persistence for developer logs (ride log + user access log).
Used when POSTGRES_URL or DATABASE_URL is set (e.g. Vercel + Neon/Postgres).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None


def _get_url() -> str:
    url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("POSTGRES_URL or DATABASE_URL not set")
    return url


def _conn():
    if psycopg2 is None:
        raise RuntimeError("psycopg2-binary is required for Postgres. Install with: pip install psycopg2-binary")
    return psycopg2.connect(_get_url())


def init_schema() -> None:
    """Create tables if they do not exist."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
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
                    cancelled SMALLINT NOT NULL DEFAULT 0,
                    created_at DOUBLE PRECISION NOT NULL,
                    cancelled_at DOUBLE PRECISION
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS access_log (
                    id TEXT PRIMARY KEY,
                    ip TEXT NOT NULL,
                    user_agent TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL
                )
            """)
        conn.commit()


def insert_ride(entry: Dict[str, Any]) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ride_log (
                    id, user_key, user_name, ride_id, prescheduled_ride_id,
                    ride_type, source, lyft_for_user_key, lyft_for_user_name,
                    cancelled, created_at, cancelled_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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


def update_ride_cancelled(ride_id: int, cancelled_at: float) -> bool:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ride_log
                SET cancelled = 1, cancelled_at = %s
                WHERE (ride_id = %s OR prescheduled_ride_id = %s) AND cancelled = 0
                """,
                (cancelled_at, ride_id, ride_id),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0


def insert_access(entry: Dict[str, Any]) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO access_log (id, ip, user_agent, path, created_at)
                VALUES (%s, %s, %s, %s, %s)
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


def load_ride_entries() -> List[Dict[str, Any]]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM ride_log ORDER BY created_at ASC")
            rows = cur.fetchall()
    return [_row_to_ride(r) for r in rows]


def load_access_entries() -> List[Dict[str, Any]]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM access_log ORDER BY created_at ASC")
            rows = cur.fetchall()
    return [_row_to_access(r) for r in rows]


def _row_to_ride(row: Dict[str, Any]) -> Dict[str, Any]:
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
        "created_at": float(row["created_at"]),
        "cancelled_at": float(row["cancelled_at"]) if row["cancelled_at"] is not None else None,
    }


def _row_to_access(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "ip": row["ip"],
        "user_agent": row["user_agent"],
        "path": row["path"],
        "created_at": float(row["created_at"]),
    }
