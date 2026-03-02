"""
Test: can User B book a ride using User A's search results?

If YES → proposals are not user-scoped; we could search once and book with all fillers.
If NO  → proposals are user-scoped; each filler must search separately (current approach is correct).

Usage:
    cd backend
    python test_cross_user.py [user_a_key] [user_b_key]

    # Or with defaults (picks first two users from USERS):
    python test_cross_user.py
"""

import sys
import json
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.users import USERS, get_auth_token, get_user_id
from src.search_ride import search_ride
from src.book_ride import book_ride
from src.cancel_ride import cancel_ride
from src import config


def main():
    user_keys = list(USERS.keys())
    if len(user_keys) < 2:
        print("ERROR: Need at least 2 users in USERS dict.")
        sys.exit(1)

    user_a_key = sys.argv[1] if len(sys.argv) > 1 else user_keys[0]
    user_b_key = sys.argv[2] if len(sys.argv) > 2 else user_keys[1]

    if user_a_key not in USERS or user_b_key not in USERS:
        print(f"ERROR: unknown user key. Available: {list(USERS.keys())}")
        sys.exit(1)

    user_a_name = USERS[user_a_key]['name']
    user_b_name = USERS[user_b_key]['name']

    print(f"=== Cross-User Booking Test ===")
    print(f"Searcher : {user_a_name} ({user_a_key})")
    print(f"Booker   : {user_b_name} ({user_b_key})")
    print(f"Origin   : {config.default_origin.get('geocoded_addr', '?')}")
    print(f"Dest     : {config.default_destination.get('geocoded_addr', '?')}")
    print()

    # ── Step 1: Search as User A ──────────────────────────────────────────────
    print(f"[1/3] Searching as {user_a_name}...")
    result = search_ride(
        origin=config.default_origin,
        destination=config.default_destination,
        auth_token=get_auth_token(user_a_key),
        user_id=get_user_id(user_a_key),
    )

    if not result or 'proposals' not in result:
        print("ERROR: No proposals returned. Check auth tokens or route.")
        sys.exit(1)

    # Find a RideSmart proposal (not Lyft)
    ridesmart_proposal = None
    for p in result.get('proposals', []):
        if 'lyft' not in json.dumps(p).lower():
            ridesmart_proposal = p
            break

    if not ridesmart_proposal:
        print("No RideSmart proposals found. Try again when RideSmart is available.")
        sys.exit(1)

    prescheduled_ride_id = ridesmart_proposal.get('prescheduled_ride_id')
    proposal_uuid = ridesmart_proposal.get('proposal_uuid')
    print(f"  Got proposal — prescheduled_ride_id={prescheduled_ride_id}, proposal_uuid={proposal_uuid}")
    print()

    # ── Step 2: Book as User B using User A's proposal ────────────────────────
    print(f"[2/3] Booking as {user_b_name} using {user_a_name}'s proposal...")
    booking = book_ride(
        prescheduled_ride_id=prescheduled_ride_id,
        proposal_uuid=proposal_uuid,
        origin=config.default_origin,
        destination=config.default_destination,
        auth_token=get_auth_token(user_b_key),
        user_id=get_user_id(user_b_key),
    )
    print()

    # ── Step 3: Interpret result + cancel if needed ───────────────────────────
    if isinstance(booking, dict) and booking.get('success') is False:
        error = booking.get('error', 'unknown')
        print(f"[3/3] Booking FAILED: {error}")
        print()
        print("CONCLUSION: Proposals ARE user-scoped.")
        print("  → Each filler must search for themselves before booking.")
        print("  → Current approach (search all in Phase 1, each books their own) is correct.")
    else:
        # Succeeded — extract ride ID and cancel immediately
        ride_id = None
        rides = booking.get('prescheduled_recurring_series_rides', []) if isinstance(booking, dict) else []
        if rides:
            ride_id = rides[0].get('id')

        print(f"[3/3] Booking SUCCEEDED (ride ID: {ride_id}). Cancelling now...")
        if ride_id:
            cancel_result = cancel_ride(
                ride_id=ride_id,
                auth_token=get_auth_token(user_b_key),
                user_id=get_user_id(user_b_key),
            )
            print(f"  Cancel result: {cancel_result}")

        print()
        print("CONCLUSION: Proposals are NOT user-scoped.")
        print("  → User B can book using User A's prescheduled_ride_id / proposal_uuid.")
        print("  → Optimization possible: search once, book with all fillers in parallel.")


if __name__ == '__main__':
    main()
