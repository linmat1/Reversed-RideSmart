"""
Server-owned booking status store.

Goal:
- Keep track of active bookings per user (RideSmart/Lyft) and a simple status.
- Provide a single "source of truth" that can be shared across all web clients.
- Support Server-Sent Events (SSE) by broadcasting snapshot updates to subscribers.

Notes:
- This is process-memory state. For Render robustness, run a single worker or use
  a shared store (Redis/DB). This module is designed so storage can be swapped later.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple


def _now_ts() -> float:
    return time.time()


@dataclass
class ActiveRide:
    ride_id: int
    ride_type: str = "unknown"  # "RideSmart" | "Lyft" | "unknown"
    source: str = "unknown"  # "orchestrator" | "individual" | "unknown"
    created_at: float = field(default_factory=_now_ts)


@dataclass
class UserBookingState:
    user_key: str
    user_name: str
    status: str = "idle"  # idle | searching | booking | booked | cancelling | error | orchestrating
    message: str = ""
    active_rides: List[ActiveRide] = field(default_factory=list)
    updated_at: float = field(default_factory=_now_ts)


class BookingStateStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users: Dict[str, UserBookingState] = {}
        self._subscribers: List[queue.Queue[str]] = []

    # --- initialization ---
    def init_users(self, users: Dict[str, Dict[str, Any]]) -> None:
        """Initialize known users (idempotent)."""
        with self._lock:
            for user_key, info in users.items():
                if user_key not in self._users:
                    self._users[user_key] = UserBookingState(
                        user_key=user_key,
                        user_name=info.get("name") or user_key,
                    )
                else:
                    # Keep existing runtime state, but refresh name if changed.
                    self._users[user_key].user_name = info.get("name") or user_key
            self._publish_locked()

    # --- state mutation helpers ---
    def set_status(self, user_key: str, status: str, message: str = "") -> None:
        with self._lock:
            st = self._get_or_create_locked(user_key)
            st.status = status
            st.message = message
            st.updated_at = _now_ts()
            self._publish_locked()

    def upsert_active_ride(
        self,
        user_key: str,
        ride_id: int,
        ride_type: str = "unknown",
        source: str = "unknown",
    ) -> None:
        with self._lock:
            st = self._get_or_create_locked(user_key)
            for r in st.active_rides:
                if r.ride_id == ride_id:
                    # Update metadata, keep original created_at
                    r.ride_type = ride_type or r.ride_type
                    r.source = source or r.source
                    st.updated_at = _now_ts()
                    st.status = "booked"
                    self._publish_locked()
                    return
            st.active_rides.append(ActiveRide(ride_id=int(ride_id), ride_type=ride_type, source=source))
            st.status = "booked"
            st.updated_at = _now_ts()
            self._publish_locked()

    def remove_active_ride(self, user_key: str, ride_id: int) -> None:
        with self._lock:
            st = self._get_or_create_locked(user_key)
            st.active_rides = [r for r in st.active_rides if r.ride_id != int(ride_id)]
            st.updated_at = _now_ts()
            if not st.active_rides and st.status in {"booked", "cancelling"}:
                st.status = "idle"
                st.message = ""
            self._publish_locked()

    def clear_all_active_rides(self, user_key: str) -> None:
        with self._lock:
            st = self._get_or_create_locked(user_key)
            st.active_rides = []
            st.status = "idle"
            st.message = ""
            st.updated_at = _now_ts()
            self._publish_locked()

    # --- snapshots ---
    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> Dict[str, Any]:
        users = []
        for user_key in sorted(self._users.keys()):
            st = self._users[user_key]
            users.append(
                {
                    "user_key": st.user_key,
                    "user_name": st.user_name,
                    "status": st.status,
                    "message": st.message,
                    "updated_at": st.updated_at,
                    "active_rides": [asdict(r) for r in st.active_rides],
                }
            )
        return {"ts": _now_ts(), "users": users}

    # --- pub/sub for SSE ---
    def subscribe(self) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
            # Immediately send a snapshot
            q.put(self._encode_snapshot_locked())
        return q

    def unsubscribe(self, q: queue.Queue[str]) -> None:
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s is not q]

    def _publish_locked(self) -> None:
        payload = self._encode_snapshot_locked()
        dead: List[queue.Queue[str]] = []
        for q in self._subscribers:
            try:
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
        if dead:
            self._subscribers = [q for q in self._subscribers if q not in dead]

    def _encode_snapshot_locked(self) -> str:
        return json.dumps({"type": "snapshot", "data": self._snapshot_locked()})

    def _get_or_create_locked(self, user_key: str) -> UserBookingState:
        if user_key not in self._users:
            self._users[user_key] = UserBookingState(user_key=user_key, user_name=user_key)
        return self._users[user_key]


# Singleton store used by the API and orchestrator.
booking_state = BookingStateStore()

