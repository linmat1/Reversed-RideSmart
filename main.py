from python.search_ride import search_ride
from python.book_ride import book_ride
from python.cancel_ride import cancel_ride
from python import config
from python.display_available_rides import display_available_rides
import json
from datetime import datetime

def main():
    """Main function to search, display, book, and optionally cancel rides."""
    print("=" * 60)
    print("RideSmart - Search, Book, and Cancel")
    print("=" * 60)
    
    # Step 1: Search for rides
    print("\nSearching for rides with default origin and destination...")
    search_response = search_ride()
    
    proposals = search_response.get("proposals", [])
    if len(proposals) == 0:
        print("Error: No ride proposals available.")
        return
    
    # Step 2: Display available rides
    display_available_rides(search_response)
    
    # Step 3: Let user choose a ride
    print("\n" + "=" * 60)
    while True:
        try:
            choice = input(f"\nSelect a ride to book (1-{len(proposals)}) or 'q' to quit: ").strip().lower()
            
            if choice == 'q':
                print("Cancelled.")
                return
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(proposals):
                selected_proposal = proposals[choice_num - 1]
                break
            else:
                print(f"Please enter a number between 1 and {len(proposals)}")
        except ValueError:
            print("Please enter a valid number or 'q' to quit")
    
    # Step 4: Extract information from selected proposal
    proposal_uuid = selected_proposal.get("proposal_uuid")
    
    # Get the prescheduled_ride_id for cancellation
    prescheduled_ride_id = selected_proposal.get("prescheduled_ride_id")
    
    # Get origin and destination from config defaults
    origin = config.default_origin
    destination = config.default_destination
    
    print(f"\n✓ Selected proposal {choice_num}")
    print(f"✓ Proposal UUID: {proposal_uuid}")
    print(f"✓ Prescheduled Ride ID: {prescheduled_ride_id}")
    print(f"\nBooking ride...")
    
    # Step 5: Book the ride
    book_response = book_ride(prescheduled_ride_id, proposal_uuid, origin, destination)
    
    if not book_response:
        print("Error: Booking failed.")
        return
    
    print("\n✓ Ride booked successfully!")
    print(f"✓ Prescheduled Ride ID: {prescheduled_ride_id}")
    
    # Step 6: Ask if user wants to cancel
    print("\n" + "=" * 60)
    while True:
        cancel_choice = input(f"\nWould you like to cancel this ride (ID: {prescheduled_ride_id})? (y/n): ").strip().lower()
        if cancel_choice in ['y', 'yes']:
            print("\n" + "=" * 60)
            print("Cancelling Ride...")
            print("=" * 60)
            cancel_response = cancel_ride(prescheduled_ride_id)
            if cancel_response:
                print("\n✓ Ride cancelled successfully!")
            else:
                print("\n✗ Error: Cancellation may have failed.")
            break
        elif cancel_choice in ['n', 'no']:
            print(f"\nRide {prescheduled_ride_id} remains booked.")
            break
        else:
            print("Please enter 'y' or 'n'")
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)

if __name__ == "__main__":
    main()
