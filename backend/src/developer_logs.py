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
    insert_request,
    update_request,
    load_ride_entries,
    load_access_entries,
    load_request_entries,
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


@dataclass
class RequestLogEntry:
    """A single orchestrator request (one full run of the Lyft booker)."""
    id: str
    user_key: str
    user_name: str
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lng: Optional[float] = None
    origin_addr: str = ""
    dest_addr: str = ""
    success: bool = False
    status: str = "running"  # "running" | "success" | "failed"
    log_text: str = ""
    created_at: float = field(default_factory=_now_ts)
    finished_at: Optional[float] = None


class DeveloperLogStore:
    """Developer ride log and user access log: persisted to SQLite, broadcast via SSE."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ride_entries: List[RideLogEntry] = []
        self._access_entries: List[UserAccessEntry] = []
        self._request_entries: List[RequestLogEntry] = []
        self._ride_id_counter = 0
        self._access_id_counter = 0
        self._request_id_counter = 0
        self._subscribers: List[queue.Queue[str]] = []
        self._load_from_db()

    def _load_from_db(self) -> None:
        """Load ride, access, and request entries from DB and set id counters."""
        try:
            init_schema()
            ride_dicts = load_ride_entries()
            access_dicts = load_access_entries()
            request_dicts = load_request_entries(include_log_text=True)
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
        for d in request_dicts:
            self._request_entries.append(
                RequestLogEntry(
                    id=d["id"],
                    user_key=d["user_key"],
                    user_name=d["user_name"],
                    origin_lat=d.get("origin_lat"),
                    origin_lng=d.get("origin_lng"),
                    dest_lat=d.get("dest_lat"),
                    dest_lng=d.get("dest_lng"),
                    origin_addr=d.get("origin_addr", ""),
                    dest_addr=d.get("dest_addr", ""),
                    success=bool(d.get("success", False)),
                    status=d.get("status", "running"),
                    log_text=d.get("log_text", ""),
                    created_at=d["created_at"],
                    finished_at=d.get("finished_at"),
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
        if self._request_entries:
            self._request_id_counter = max(
                _parse_counter_from_id(e.id, "req") for e in self._request_entries
            )

    def _next_ride_id(self) -> str:
        self._ride_id_counter += 1
        return f"ride_{self._ride_id_counter}_{int(_now_ts() * 1000)}"

    def _next_access_id(self) -> str:
        self._access_id_counter += 1
        return f"access_{self._access_id_counter}_{int(_now_ts() * 1000)}"

    def _next_request_id(self) -> str:
        self._request_id_counter += 1
        return f"req_{self._request_id_counter}_{int(_now_ts() * 1000)}"

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

    # --- Request log (orchestrator runs) ---
    def append_request(
        self,
        user_key: str,
        user_name: str,
        origin_lat: Optional[float] = None,
        origin_lng: Optional[float] = None,
        dest_lat: Optional[float] = None,
        dest_lng: Optional[float] = None,
        origin_addr: str = "",
        dest_addr: str = "",
    ) -> RequestLogEntry:
        with self._lock:
            entry = RequestLogEntry(
                id=self._next_request_id(),
                user_key=user_key,
                user_name=user_name,
                origin_lat=origin_lat,
                origin_lng=origin_lng,
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                origin_addr=origin_addr,
                dest_addr=dest_addr,
            )
            try:
                insert_request(asdict(entry))
            except Exception as e:
                print(f"Developer logs: failed to persist request: {e}")
                traceback.print_exc()
            self._request_entries.append(entry)
            self._broadcast_locked()
            return entry

    def update_request_entry(
        self,
        entry_id: str,
        log_text: Optional[str] = None,
        status: Optional[str] = None,
        success: Optional[bool] = None,
        finished_at: Optional[float] = None,
    ) -> None:
        updates: Dict[str, Any] = {}
        if log_text is not None:
            updates["log_text"] = log_text
        if status is not None:
            updates["status"] = status
        if success is not None:
            updates["success"] = success
        if finished_at is not None:
            updates["finished_at"] = finished_at
        if not updates:
            return
        with self._lock:
            for e in self._request_entries:
                if e.id == entry_id:
                    if log_text is not None:
                        e.log_text = log_text
                    if status is not None:
                        e.status = status
                    if success is not None:
                        e.success = success
                    if finished_at is not None:
                        e.finished_at = finished_at
                    break
            try:
                update_request(entry_id, updates)
            except Exception as ex:
                print(f"Developer logs: failed to persist request update: {ex}")
            self._broadcast_locked()

    def get_request_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [asdict(e) for e in reversed(self._request_entries)]

    # --- Snapshot for SSE ---
    def snapshot(self) -> Dict[str, Any]:
        if _use_postgres():
            try:
                ride_dicts = load_ride_entries()
                access_dicts = load_access_entries()
                request_dicts = load_request_entries()
                return {
                    "ts": _now_ts(),
                    "ride_log": list(reversed(ride_dicts)),
                    "access_log": list(reversed(access_dicts)),
                    "request_log": list(reversed(request_dicts)),
                }
            except Exception as e:
                print(f"Developer logs: snapshot from DB failed: {e}")
        with self._lock:
            return self._snapshot_locked()

    # --- SSE subscribe / broadcast ---
    def subscribe(self) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
            if _use_postgres():
                data = self._snapshot_from_db_if_postgres() or self._snapshot_locked()
            else:
                data = self._snapshot_locked()
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
            request_dicts = load_request_entries()
            return {
                "ts": _now_ts(),
                "ride_log": list(reversed(ride_dicts)),
                "access_log": list(reversed(access_dicts)),
                "request_log": list(reversed(request_dicts)),
            }
        except Exception as e:
            print(f"Developer logs: snapshot from DB failed: {e}")
            return None

    def _broadcast_locked(self) -> None:
        data = self._snapshot_locked()
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
            "request_log": [asdict(e) for e in reversed(self._request_entries)],
        }


# Singleton used by API and orchestrator
developer_logs = DeveloperLogStore()
