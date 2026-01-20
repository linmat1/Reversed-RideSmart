#!/usr/bin/env python3
"""
Lyft Booking CLI

Command-line interface for the Lyft orchestrator.
Usage: python lyft_cli.py
"""

import sys
import os

# Add the backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.lyft_orchestrator import LyftOrchestrator
from src.users import USERS, list_users
from src.destination_config import LOCATIONS, get_location_pair, list_available_locations


def print_header():
    """Print CLI header."""
    print("=" * 60)
    print("  🚗 LYFT ORCHESTRATOR CLI")
    print("  Get free Lyft rides by filling RideSmart capacity")
    print("=" * 60)
    print()


def select_user(prompt, exclude_key=None):
    """Let user select from available accounts."""
    users = [(key, data['name']) for key, data in USERS.items() if key != exclude_key]
    
    if not users:
        print("No users available!")
        return None
    
    print(f"\n{prompt}")
    for i, (key, name) in enumerate(users, 1):
        print(f"  {i}. {name}")
    
    while True:
        try:
            choice = input(f"\nSelect (1-{len(users)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(users):
                return users[idx][0]
            print(f"Please enter a number between 1 and {len(users)}")
        except ValueError:
            print("Please enter a valid number")


def select_route():
    """Let user select a route."""
    locations = list_available_locations()
    
    print("\nAvailable routes:")
    for i, loc in enumerate(locations, 1):
        origin = LOCATIONS[loc]['origin'].get('geocoded_addr', loc)
        dest = LOCATIONS[loc]['destination'].get('geocoded_addr', loc)
        print(f"  {i}. {origin} → {dest}")
    
    while True:
        try:
            choice = input(f"\nSelect route (1-{len(locations)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(locations):
                loc_key = locations[idx]
                origin, destination = get_location_pair(loc_key)
                return origin, destination, loc_key
            print(f"Please enter a number between 1 and {len(locations)}")
        except ValueError:
            print("Please enter a valid number")


def main():
    """Main CLI function."""
    print_header()
    
    # Check we have enough accounts
    if len(USERS) < 2:
        print("ERROR: Need at least 2 user accounts configured!")
        print("Add more users in backend/src/users.py")
        return
    
    print(f"Available accounts: {len(USERS)}")
    for key, data in USERS.items():
        print(f"  - {data['name']} ({key})")
    
    # Select original user (who wants the Lyft)
    original_user = select_user("Who is the ORIGINAL person (who wants the Lyft)?")
    if not original_user:
        return
    
    original_name = USERS[original_user]['name']
    print(f"\n✓ Original user: {original_name}")
    
    # Show filler accounts
    filler_accounts = [k for k in USERS.keys() if k != original_user]
    print(f"✓ Filler accounts: {[USERS[k]['name'] for k in filler_accounts]}")
    
    # Select route
    origin, destination, route_key = select_route()
    print(f"\n✓ Route: {origin.get('geocoded_addr', 'Unknown')} → {destination.get('geocoded_addr', 'Unknown')}")
    
    # Confirm
    print("\n" + "=" * 60)
    print("READY TO START")
    print("=" * 60)
    print(f"Original user: {original_name}")
    print(f"Filler accounts: {[USERS[k]['name'] for k in filler_accounts]}")
    print(f"Route: {origin.get('geocoded_addr')} → {destination.get('geocoded_addr')}")
    print()
    
    confirm = input("Start the Lyft orchestrator? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("Cancelled.")
        return
    
    print("\n")
    
    # Run the orchestrator
    orchestrator = LyftOrchestrator(original_user, origin, destination)
    result = orchestrator.run()
    
    # Print final result
    print("\n" + "=" * 60)
    if result['success']:
        print("🎉 SUCCESS!")
        print(f"Lyft booked for {original_name}!")
    else:
        print("❌ FAILED")
        print(result['message'])
    print("=" * 60)


if __name__ == "__main__":
    main()
