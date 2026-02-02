"""
Developer logs: ride status log and user access log.
Persisted to SQLite (backend/data/developer_logs.db), broadcast in real time via SSE.
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
import traceback
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional

import os

from src.developer_logs_db import (
    init_schema,
    insert_ride,
    update_ride_cancelled,
    insert_access,
    load_ride_entries,
    load_access_entries,
    insert_orchestrator_line,
    load_orchestrator_log_latest,
)


def _use_postgres() -> bool:
    """True when Postgres is configured (all instances share same DB)."""
    return bool(os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL"))


def _now_ts() -> float:
    return time.time()


def _parse_counter_from_id(entry_id: str, prefix: str) -> int:
    """Extract numeric counter from id like ride_3_1234567890 or access_5_1234567890."""
    m = re.match(rf"^{re.escape(prefix)}_(\d+)_", entry_id)
    return int(m.group(1)) if m else 0


@dataclass
class RideLogEntry:
    """A single ride booking (individual, Lyft, or filler)."""
    id: str
    user_key: str
    user_name: str
    ride_id: Optional[int]  # confirmed id from booking response
    prescheduled_ride_id: Optional[int]  # from proposal, fallback for cancel
    ride_type: str  # "RideSmart" | "Lyft"
    source: str  # "individual" | "orchestrator"
    lyft_for_user_key: Optional[str] = None  # when filler: who the Lyft was for
    lyft_for_user_name: Optional[str] = None
    cancelled: bool = False
    cancelled_at: Optional[float] = None
    created_at: float = field(default_factory=_now_ts)


@dataclass
class UserAccessEntry:
    """A single website access (IP, time, etc.)."""
    id: str
    ip: str
    user_agent: str
    path: str
    created_at: float = field(default_factory=_now_ts)


class DeveloperLogStore:
    """Developer ride log and user access log: persisted to SQLite, broadcast via SSE."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ride_entries: List[RideLogEntry] = []
        self._access_entries: List[UserAccessEntry] = []
        self._orchestrator_log: List[str] = []  # User-facing Lyft orchestrator log (latest run)
        self._current_run_started_at: Optional[float] = None  # For persisting orchestrator log to DB
        self._ride_id_counter = 0
        self._access_id_counter = 0
        self._subscribers: List[queue.Queue[str]] = []
        self._load_from_db()

    def _load_from_db(self) -> None:
        """Load ride and access entries from DB and set id counters."""
        try:
            init_schema()
            ride_dicts = load_ride_entries()
            access_dicts = load_access_entries()
        except Exception as e:
            print(f"Developer logs: failed to load from DB: {e}")
            return
        for d in ride_dicts:
            self._ride_entries.append(
                RideLogEntry(
                    id=d["id"],
                    user_key=d["user_key"],
                    user_name=d["user_name"],
                    ride_id=d.get("ride_id"),
                    prescheduled_ride_id=d.get("prescheduled_ride_id"),
                    ride_type=d["ride_type"],
                    source=d["source"],
                    lyft_for_user_key=d.get("lyft_for_user_key"),
                    lyft_for_user_name=d.get("lyft_for_user_name"),
                    cancelled=bool(d.get("cancelled", False)),
                    cancelled_at=d.get("cancelled_at"),
                    created_at=d["created_at"],
                )
            )
        for d in access_dicts:
            self._access_entries.append(
                UserAccessEntry(
                    id=d["id"],
                    ip=d["ip"],
                    user_agent=d["user_agent"],
                    path=d["path"],
                    created_at=d["created_at"],
                )
            )
        if self._ride_entries:
            self._ride_id_counter = max(
                _parse_counter_from_id(e.id, "ride") for e in self._ride_entries
            )
        if self._access_entries:
            self._access_id_counter = max(
                _parse_counter_from_id(e.id, "access") for e in self._access_entries
            )
        # Load latest orchestrator run from DB so Developer tab shows it after restart
        try:
            self._orchestrator_log = load_orchestrator_log_latest()
        except Exception as e:
            print(f"Developer logs: failed to load orchestrator log from DB: {e}")

    def _next_ride_id(self) -> str:
        self._ride_id_counter += 1
        return f"ride_{self._ride_id_counter}_{int(_now_ts() * 1000)}"

    def _next_access_id(self) -> str:
        self._access_id_counter += 1
        return f"access_{self._access_id_counter}_{int(_now_ts() * 1000)}"

    # --- Ride log ---
    def append_booking(
        self,
        user_key: str,
        user_name: str,
        ride_id: Optional[int],
        prescheduled_ride_id: Optional[int],
        ride_type: str = "RideSmart",
        source: str = "individual",
        lyft_for_user_key: Optional[str] = None,
        lyft_for_user_name: Optional[str] = None,
    ) -> RideLogEntry:
        with self._lock:
            entry = RideLogEntry(
                id=self._next_ride_id(),
                user_key=user_key,
                user_name=user_name,
                ride_id=ride_id,
                prescheduled_ride_id=prescheduled_ride_id,
                ride_type=ride_type,
                source=source,
                lyft_for_user_key=lyft_for_user_key,
                lyft_for_user_name=lyft_for_user_name,
            )
            try:
                insert_ride(asdict(entry))
            except Exception as e:
                print(f"Developer logs: failed to persist ride: {e}")
                traceback.print_exc()
            self._ride_entries.append(entry)
            self._broadcast_locked()
            return entry

    def mark_cancelled(self, ride_id: int) -> bool:
        """
        Mark the booking with this ride_id (or prescheduled_ride_id) as cancelled.
        MUST only be called after the external cancel API (cancel_ride) has returned
        success (non-None). "Cancelled" in the UI must mean server-confirmed cancellation.
        Returns True if found and updated in memory; DB is always updated when using Postgres
        so all clients/tabs/devices see "Cancelled" on next snapshot.
        """
        now = _now_ts()
        # When using Postgres, always persist cancellation first so every instance's
        # next snapshot() (from DB) shows "Cancelled" even if this instance has no in-memory entry.
        if _use_postgres():
            try:
                update_ride_cancelled(ride_id, now)
            except Exception as ex:
                print(f"Developer logs: failed to persist cancellation: {ex}")
        with self._lock:
            found = False
            for e in self._ride_entries:
                if (e.ride_id is not None and e.ride_id == ride_id) or (
                    e.prescheduled_ride_id is not None and e.prescheduled_ride_id == ride_id
                ):
                    e.cancelled = True
                    e.cancelled_at = now
                    found = True
                    break
            if found:
                # Only persist when not Postgres (Postgres already updated above)
                if not _use_postgres():
                    try:
                        update_ride_cancelled(ride_id, now)
                    except Exception as ex:
                        print(f"Developer logs: failed to persist cancellation: {ex}")
                self._broadcast_locked()
            return found

    def get_ride_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [asdict(e) for e in reversed(self._ride_entries)]

    # --- User access log ---
    def append_access(self, ip: str, user_agent: str, path: str = "/") -> UserAccessEntry:
        with self._lock:
            entry = UserAccessEntry(
                id=self._next_access_id(),
                ip=ip,
                user_agent=user_agent or "",
                path=path,
            )
            try:
                insert_access(asdict(entry))
            except Exception as e:
                print(f"Developer logs: failed to persist access: {e}")
                traceback.print_exc()
            self._access_entries.append(entry)
            self._broadcast_locked()
            return entry

    def get_access_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [asdict(e) for e in reversed(self._access_entries)]

    # --- Orchestrator (user-facing) log (persisted to DB for reference) ---
    def clear_orchestrator_log(self) -> None:
        """Clear the orchestrator log and start a new run (call when a new run starts)."""
        with self._lock:
            self._current_run_started_at = _now_ts()
            self._orchestrator_log.clear()
            self._broadcast_locked()

    def append_orchestrator_log(self, message: str) -> None:
        """Append a line to the user-facing orchestrator log, persist to DB, and broadcast."""
        with self._lock:
            idx = len(self._orchestrator_log)
            self._orchestrator_log.append(message)
            if self._current_run_started_at is not None:
                try:
                    insert_orchestrator_line(
                        self._current_run_started_at, idx, message
                    )
                except Exception as e:
                    print(f"Developer logs: failed to persist orchestrator line: {e}")
            self._broadcast_locked()

    def get_orchestrator_log(self) -> List[str]:
        with self._lock:
            return list(self._orchestrator_log)

    # --- Snapshot for SSE ---
    def snapshot(self) -> Dict[str, Any]:
        # When using Postgres, read from DB every time so all instances/tabs see the same data.
        if _use_postgres():
            try:
                ride_dicts = load_ride_entries()
                access_dicts = load_access_entries()
                orchestrator_lines = load_orchestrator_log_latest()
                with self._lock:
                    return {
                        "ts": _now_ts(),
                        "ride_log": list(reversed(ride_dicts)),
                        "access_log": list(reversed(access_dicts)),
                        "orchestrator_log": orchestrator_lines,
                    }
            except Exception as e:
                print(f"Developer logs: snapshot from DB failed: {e}")
        with self._lock:
            return {
                "ts": _now_ts(),
                "ride_log": [asdict(e) for e in reversed(self._ride_entries)],
                "access_log": [asdict(e) for e in reversed(self._access_entries)],
                "orchestrator_log": list(self._orchestrator_log),
            }

    # --- SSE subscribe / broadcast ---
    def subscribe(self) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
            # When using Postgres, initial snapshot from DB so new client sees shared state
            data = self._snapshot_from_db_if_postgres() or self._snapshot_locked()
            q.put(json.dumps({"type": "snapshot", "data": data}))
        return q

    def unsubscribe(self, q: queue.Queue[str]) -> None:
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s is not q]

    def _encode_snapshot(self) -> str:
        return json.dumps({"type": "snapshot", "data": self.snapshot()})

    def _snapshot_from_db_if_postgres(self) -> Optional[Dict[str, Any]]:
        """When using Postgres, return snapshot from DB; else None."""
        if not _use_postgres():
            return None
        try:
            ride_dicts = load_ride_entries()
            access_dicts = load_access_entries()
            orchestrator_lines = load_orchestrator_log_latest()
            with self._lock:
                return {
                    "ts": _now_ts(),
                    "ride_log": list(reversed(ride_dicts)),
                    "access_log": list(reversed(access_dicts)),
                    "orchestrator_log": orchestrator_lines,
                }
        except Exception as e:
            print(f"Developer logs: snapshot from DB failed: {e}")
            return None

    def _broadcast_locked(self) -> None:
        data = self._snapshot_from_db_if_postgres() or self._snapshot_locked()
        payload = json.dumps({"type": "snapshot", "data": data})
        dead: List[queue.Queue[str]] = []
        for q in self._subscribers:
            try:
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
        if dead:
            self._subscribers = [s for s in self._subscribers if s not in dead]

    def _snapshot_locked(self) -> Dict[str, Any]:
        return {
            "ts": _now_ts(),
            "ride_log": [asdict(e) for e in reversed(self._ride_entries)],
            "access_log": [asdict(e) for e in reversed(self._access_entries)],
            "orchestrator_log": list(self._orchestrator_log),
        }


# Singleton used by API and orchestrator
developer_logs = DeveloperLogStore()
