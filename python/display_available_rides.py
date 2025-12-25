from python.search_ride import search_ride
from python.book_ride import book_ride
from python.cancel_ride import cancel_ride
from python import config
import json
from datetime import datetime

def display_available_rides(search_response):
    """
    Display available rides from a search response in a formatted, readable way.
    
    Args:
        search_response: dict, the response from search_ride() containing proposals
    
    Returns:
        None (prints to console)
    """
    if not search_response or "proposals" not in search_response:
        print("No proposals found in search response.")
        return
    
    proposals = search_response.get("proposals", [])
    if len(proposals) == 0:
        print("No ride proposals available.")
        return
    
    print("\n" + "=" * 60)
    print("Available Rides:")
    print("=" * 60)
    
    for i, proposal in enumerate(proposals, 1):
        ride_info = proposal.get("ride_info", {})
        pickup = ride_info.get("pickup", {})
        dropoff = ride_info.get("dropoff", {})
        
        # Get pickup location
        pickup_loc = pickup.get("location", {})
        pickup_desc = pickup_loc.get("short_description") or pickup_loc.get("description", "Unknown")
        walking_dist = pickup.get("walking_distance_description", "")
        if walking_dist:
            walking_dist = f"({walking_dist} walk)"
        
        # Get dropoff location
        dropoff_loc = dropoff.get("location", {})
        dropoff_desc = dropoff_loc.get("short_description") or dropoff_loc.get("description", "Unknown")
        
        # Get ETA
        eta_ts = pickup.get("eta_ts", 0)
        if eta_ts:
            try:
                eta_time = datetime.fromtimestamp(eta_ts).strftime("%I:%M %p")
            except:
                eta_time = "N/A"
        else:
            eta_time = "N/A"
        
        # Get cost
        cost = ride_info.get("ride_cost", 0)
        cost_str = f"${cost:.2f}" if cost > 0 else "Free"
        
        # Get proposal identifiers
        proposal_uuid = proposal.get("proposal_uuid", "N/A")
        prescheduled_ride_id = proposal.get("prescheduled_ride_id", "N/A")
        
        print(f"\n[{i}] Proposal ID: {proposal.get('proposal_id', 'N/A')}")
        print(f"    Prescheduled Ride ID: {prescheduled_ride_id}")
        print(f"    Proposal UUID: {proposal_uuid}")
        print(f"    Pickup: {pickup_desc} {walking_dist}")
        print(f"    Dropoff: {dropoff_desc}")
        print(f"    ETA: {eta_time}")
        print(f"    Cost: {cost_str}")
    
    print("\n" + "=" * 60)
