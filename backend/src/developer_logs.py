"""
Developer logs: ride status log and user access log.
Stored in memory, broadcast in real time to all clients via SSE.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional


def _now_ts() -> float:
    return time.time()


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
    """In-memory store for developer ride log and user access log with SSE broadcast."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ride_entries: List[RideLogEntry] = []
        self._access_entries: List[UserAccessEntry] = []
        self._ride_id_counter = 0
        self._access_id_counter = 0
        self._subscribers: List[queue.Queue[str]] = []

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
            self._ride_entries.append(entry)
            self._broadcast_locked()
            return entry

    def mark_cancelled(self, ride_id: int) -> bool:
        """
        Mark the booking with this ride_id (or prescheduled_ride_id) as cancelled.
        MUST only be called after the external cancel API (cancel_ride) has returned
        success (non-None). "Cancelled" in the UI must mean server-confirmed cancellation.
        Returns True if found and updated.
        """
        with self._lock:
            now = _now_ts()
            for e in self._ride_entries:
                if (e.ride_id is not None and e.ride_id == ride_id) or (
                    e.prescheduled_ride_id is not None and e.prescheduled_ride_id == ride_id
                ):
                    e.cancelled = True
                    e.cancelled_at = now
                    self._broadcast_locked()
                    return True
            return False

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
            self._access_entries.append(entry)
            self._broadcast_locked()
            return entry

    def get_access_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [asdict(e) for e in reversed(self._access_entries)]

    # --- Snapshot for SSE ---
    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "ts": _now_ts(),
                "ride_log": [asdict(e) for e in reversed(self._ride_entries)],
                "access_log": [asdict(e) for e in reversed(self._access_entries)],
            }

    # --- SSE subscribe / broadcast ---
    def subscribe(self) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
            q.put(json.dumps({"type": "snapshot", "data": self._snapshot_locked()}))
        return q

    def unsubscribe(self, q: queue.Queue[str]) -> None:
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s is not q]

    def _encode_snapshot(self) -> str:
        return json.dumps({"type": "snapshot", "data": self.snapshot()})

    def _broadcast_locked(self) -> None:
        payload = json.dumps({"type": "snapshot", "data": self._snapshot_locked()})
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
        }


# Singleton used by API and orchestrator
developer_logs = DeveloperLogStore()
