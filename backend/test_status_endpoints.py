import os
import sys
import time
import json
import unittest


def _ensure_backend_on_path():
    here = os.path.dirname(__file__)
    if here not in sys.path:
        sys.path.insert(0, here)


def _set_test_env():
    # Minimal fake users so backend loads USERS deterministically.
    os.environ["USER_MATTHEW_NAME"] = "Matthew"
    os.environ["USER_MATTHEW_AUTH_TOKEN"] = "test-token-matthew"
    os.environ["USER_MATTHEW_USER_ID"] = "111"

    os.environ["USER_CHARLES_NAME"] = "Charles"
    os.environ["USER_CHARLES_AUTH_TOKEN"] = "test-token-charles"
    os.environ["USER_CHARLES_USER_ID"] = "222"

    os.environ["DEFAULT_USER"] = "matthew"


def _extract_first_sse_json(payload_text: str):
    """
    Given a chunk of SSE text, return the first JSON object from a 'data: ' line.
    """
    for line in payload_text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: ") :])
    return None


class StatusEndpointsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_backend_on_path()
        _set_test_env()

        # Import after env vars are set.
        import api  # noqa: F401
        from src.booking_state import booking_state  # noqa: F401

        cls.api = api
        cls.booking_state = booking_state

    def setUp(self):
        self.client = self.api.app.test_client()

    def test_status_snapshot_has_users(self):
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("users", data)
        self.assertGreaterEqual(len(data["users"]), 2)
        keys = {u["user_key"] for u in data["users"]}
        self.assertIn("matthew", keys)
        self.assertIn("charles", keys)

    def test_status_stream_sends_updates(self):
        # Open stream (first message should be a snapshot)
        resp = self.client.get("/api/status/stream", buffered=False)
        it = iter(resp.response)

        first_chunk = next(it).decode("utf-8", errors="ignore")
        first_msg = _extract_first_sse_json(first_chunk)
        self.assertIsNotNone(first_msg)
        self.assertEqual(first_msg.get("type"), "snapshot")

        # Trigger an update
        self.booking_state.upsert_active_ride("matthew", 123456, ride_type="RideSmart", source="test")

        # Read until we get a data message (skip keepalives)
        updated_msg = None
        start = time.time()
        while time.time() - start < 3 and updated_msg is None:
            chunk = next(it).decode("utf-8", errors="ignore")
            msg = _extract_first_sse_json(chunk)
            if msg:
                updated_msg = msg

        self.assertIsNotNone(updated_msg)
        self.assertEqual(updated_msg.get("type"), "snapshot")
        users = updated_msg["data"]["users"]
        matthew = next(u for u in users if u["user_key"] == "matthew")
        ride_ids = [r["ride_id"] for r in matthew.get("active_rides", [])]
        self.assertIn(123456, ride_ids)

        resp.close()

    def test_book_endpoint_tracks_fallback_prescheduled_id(self):
        # Monkeypatch api.book_ride to avoid network and simulate a response without confirmed ride id.
        original_book_ride = self.api.book_ride
        try:
            def fake_book_ride(*args, **kwargs):
                return {"ok": True}  # no prescheduled_recurring_series_rides

            self.api.book_ride = fake_book_ride

            res = self.client.post(
                "/api/book",
                json={
                    "prescheduled_ride_id": 456362731,
                    "proposal_uuid": "test-uuid",
                    "origin": {"latlng": {"lat": 0, "lng": 0}, "geocoded_addr": "o", "full_geocoded_addr": "o"},
                    "destination": {"latlng": {"lat": 0, "lng": 0}, "geocoded_addr": "d", "full_geocoded_addr": "d"},
                    "user_id": "matthew",
                    "ride_type": "RideSmart",
                },
            )
            self.assertEqual(res.status_code, 200)

            snap = self.booking_state.snapshot()
            matthew = next(u for u in snap["users"] if u["user_key"] == "matthew")
            ride_ids = [r["ride_id"] for r in matthew.get("active_rides", [])]
            self.assertIn(456362731, ride_ids)
        finally:
            self.api.book_ride = original_book_ride


if __name__ == "__main__":
    unittest.main()

