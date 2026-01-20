"""
Lyft Orchestrator Module

This module handles the logic for getting a Lyft ride by:
1. Having filler accounts book RideSmart rides to fill capacity
2. Once Lyft becomes available, the original person books the Lyft
3. All filler bookings are then cancelled
"""

import time
from src.search_ride import search_ride
from src.book_ride import book_ride
from src.cancel_ride import cancel_ride
from src.users import USERS, get_auth_token, get_user_id, list_users


class LyftOrchestrator:
    """Orchestrates the process of getting a Lyft ride."""
    
    def __init__(self, original_user_key, route_origin, route_destination):
        """
        Initialize the orchestrator.
        
        Args:
            original_user_key: str, the user key of the person who wants the Lyft
            route_origin: dict, origin location data
            route_destination: dict, destination location data
        """
        self.original_user_key = original_user_key
        self.route_origin = route_origin
        self.route_destination = route_destination
        
        # Track state
        self.filler_bookings = []  # List of {user_key, ride_id} for cleanup
        self.status = "idle"  # idle, searching, booking, success, failed
        self.current_step = ""
        self.log = []  # List of log messages
        
    def _log(self, message):
        """Add a log message with timestamp."""
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self.log.append(entry)
        print(entry)
        
    def _get_filler_accounts(self):
        """Get list of filler account keys (all except original user)."""
        return [key for key in USERS.keys() if key != self.original_user_key]
    
    def _search_for_rides(self, user_key):
        """
        Search for rides as a specific user.
        
        Returns:
            dict with keys:
                - proposals: list of ride proposals
                - has_lyft: bool, whether Lyft is available
                - lyft_proposal: the Lyft proposal if available, else None
                - ridesmart_count: number of RideSmart vehicles available
        """
        auth_token = get_auth_token(user_key)
        user_id = get_user_id(user_key)
        
        response = search_ride(
            origin=self.route_origin,
            destination=self.route_destination,
            auth_token=auth_token,
            user_id=user_id
        )
        
        if not response or 'proposals' not in response:
            return {
                'proposals': [],
                'has_lyft': False,
                'lyft_proposal': None,
                'ridesmart_count': 0
            }
        
        proposals = response.get('proposals', [])
        
        # Separate Lyft and RideSmart proposals
        lyft_proposals = []
        ridesmart_proposals = []
        
        for p in proposals:
            ride_info = p.get('ride_info', {})
            ride_supplier = p.get('ride_supplier') or ride_info.get('ride_supplier')
            
            # Check multiple possible indicators for Lyft
            proposal_options_id = p.get('proposal_options_id', '') or ''
            extra_details = p.get('extra_details', {}) or ride_info.get('extra_details', {}) or {}
            external_provider_type = extra_details.get('external_provider_type', '') or ''
            
            is_lyft = (
                ride_supplier == 1 or 
                p.get('type') == 'lyft' or 
                p.get('provider') == 'lyft' or
                'lyft' in proposal_options_id.lower() or
                external_provider_type.lower() == 'lyft'
            )
            
            if is_lyft:
                lyft_proposals.append(p)
            else:
                ridesmart_proposals.append(p)
        
        return {
            'proposals': proposals,
            'has_lyft': len(lyft_proposals) > 0,
            'lyft_proposal': lyft_proposals[0] if lyft_proposals else None,
            'ridesmart_count': len(ridesmart_proposals),
            'ridesmart_proposals': ridesmart_proposals
        }
    
    def _book_ride(self, user_key, proposal):
        """
        Book a ride as a specific user.
        
        Returns:
            dict with booking response, or None if failed
        """
        auth_token = get_auth_token(user_key)
        user_id = get_user_id(user_key)
        
        response = book_ride(
            prescheduled_ride_id=proposal.get('prescheduled_ride_id'),
            proposal_uuid=proposal.get('proposal_uuid'),
            origin=self.route_origin,
            destination=self.route_destination,
            auth_token=auth_token,
            user_id=user_id
        )
        
        return response
    
    def _cancel_ride(self, user_key, ride_id):
        """Cancel a ride as a specific user."""
        auth_token = get_auth_token(user_key)
        user_id = get_user_id(user_key)
        
        response = cancel_ride(
            ride_id=ride_id,
            auth_token=auth_token,
            user_id=user_id
        )
        
        return response
    
    def _cancel_all_filler_bookings(self):
        """Cancel all filler bookings."""
        self._log(f"Cancelling {len(self.filler_bookings)} filler booking(s)...")
        
        for booking in self.filler_bookings:
            user_key = booking['user_key']
            ride_id = booking['ride_id']
            user_name = USERS[user_key]['name']
            
            self._log(f"  Cancelling {user_name}'s booking (ride ID: {ride_id})...")
            result = self._cancel_ride(user_key, ride_id)
            
            if result:
                self._log(f"  ✓ Cancelled {user_name}'s booking")
            else:
                self._log(f"  ✗ Failed to cancel {user_name}'s booking")
        
        self.filler_bookings = []
    
    def run(self):
        """
        Run the Lyft booking process.
        
        Returns:
            dict with:
                - success: bool
                - lyft_booking: booking response if successful
                - message: status message
        """
        self.status = "searching"
        self.log = []
        original_name = USERS[self.original_user_key]['name']
        
        self._log(f"=== Starting Lyft Orchestrator ===")
        self._log(f"Original user: {original_name}")
        self._log(f"Filler accounts: {[USERS[k]['name'] for k in self._get_filler_accounts()]}")
        
        # Step 1: Check if Lyft is already available with a filler account
        filler_accounts = self._get_filler_accounts()
        
        if not filler_accounts:
            self._log("ERROR: No filler accounts available!")
            self.status = "failed"
            return {
                'success': False,
                'lyft_booking': None,
                'message': "No filler accounts available"
            }
        
        # Use first filler to check initial state
        check_account = filler_accounts[0]
        check_name = USERS[check_account]['name']
        
        self._log(f"\n--- Step 1: Initial check with {check_name} ---")
        self.current_step = f"Checking availability with {check_name}"
        
        result = self._search_for_rides(check_account)
        
        if result['has_lyft']:
            self._log(f"✓ Lyft already available!")
            self._log(f"  Searching as {original_name} to book Lyft...")
            
            # Search as original user and book Lyft
            original_result = self._search_for_rides(self.original_user_key)
            
            if original_result['has_lyft']:
                self.status = "booking"
                self.current_step = f"Booking Lyft for {original_name}"
                
                booking = self._book_ride(self.original_user_key, original_result['lyft_proposal'])
                
                if booking:
                    self._log(f"✓ SUCCESS! {original_name} booked Lyft!")
                    self.status = "success"
                    return {
                        'success': True,
                        'lyft_booking': booking,
                        'message': f"Lyft booked successfully for {original_name}"
                    }
            
            self._log(f"✗ Lyft not available for {original_name}")
        
        self._log(f"RideSmart vehicles available: {result['ridesmart_count']}")
        
        # Step 2: Start filling capacity with filler accounts
        self._log(f"\n--- Step 2: Filling RideSmart capacity ---")
        
        for filler_key in filler_accounts:
            filler_name = USERS[filler_key]['name']
            self.current_step = f"Searching as {filler_name}"
            
            self._log(f"\nSearching as {filler_name}...")
            result = self._search_for_rides(filler_key)
            
            self._log(f"  RideSmart available: {result['ridesmart_count']}, Lyft available: {result['has_lyft']}")
            
            if result['has_lyft']:
                # Lyft is now available! Book for original user
                self._log(f"\n✓ Lyft became available!")
                self._log(f"Searching as {original_name} to book Lyft...")
                
                original_result = self._search_for_rides(self.original_user_key)
                
                if original_result['has_lyft']:
                    self.status = "booking"
                    self.current_step = f"Booking Lyft for {original_name}"
                    
                    booking = self._book_ride(self.original_user_key, original_result['lyft_proposal'])
                    
                    if booking:
                        self._log(f"✓ SUCCESS! {original_name} booked Lyft!")
                        
                        # Cancel all filler bookings
                        self._log(f"\n--- Cleanup: Cancelling filler bookings ---")
                        self._cancel_all_filler_bookings()
                        
                        self.status = "success"
                        return {
                            'success': True,
                            'lyft_booking': booking,
                            'message': f"Lyft booked successfully for {original_name}"
                        }
                    else:
                        self._log(f"✗ Failed to book Lyft for {original_name}")
                else:
                    self._log(f"✗ Lyft not available when {original_name} searched")
            
            # Book a RideSmart ride with this filler account to reduce capacity
            if result['ridesmart_count'] > 0 and result.get('ridesmart_proposals'):
                self.status = "booking"
                self.current_step = f"Booking RideSmart with {filler_name}"
                
                ridesmart_proposal = result['ridesmart_proposals'][0]
                self._log(f"  Booking RideSmart with {filler_name}...")
                
                booking = self._book_ride(filler_key, ridesmart_proposal)
                
                if booking:
                    # Extract ride ID for later cancellation
                    ride_id = None
                    rides = booking.get('prescheduled_recurring_series_rides', [])
                    if rides:
                        ride_id = rides[0].get('id')
                    
                    if ride_id:
                        self.filler_bookings.append({
                            'user_key': filler_key,
                            'ride_id': ride_id
                        })
                        self._log(f"  ✓ {filler_name} booked RideSmart (ride ID: {ride_id})")
                    else:
                        self._log(f"  ✓ {filler_name} booked but couldn't get ride ID")
                else:
                    self._log(f"  ✗ Failed to book RideSmart with {filler_name}")
            else:
                self._log(f"  No RideSmart rides to book")
        
        # If we get here, we've used all filler accounts but no Lyft
        self._log(f"\n--- All filler accounts used, checking one more time ---")
        
        # Final check with original user
        original_result = self._search_for_rides(self.original_user_key)
        
        if original_result['has_lyft']:
            self.status = "booking"
            self.current_step = f"Booking Lyft for {original_name}"
            
            booking = self._book_ride(self.original_user_key, original_result['lyft_proposal'])
            
            if booking:
                self._log(f"✓ SUCCESS! {original_name} booked Lyft!")
                
                # Cancel all filler bookings
                self._log(f"\n--- Cleanup: Cancelling filler bookings ---")
                self._cancel_all_filler_bookings()
                
                self.status = "success"
                return {
                    'success': True,
                    'lyft_booking': booking,
                    'message': f"Lyft booked successfully for {original_name}"
                }
        
        # Failed - clean up filler bookings
        self._log(f"\n✗ FAILED: Could not get Lyft for {original_name}")
        self._log(f"\n--- Cleanup: Cancelling filler bookings ---")
        self._cancel_all_filler_bookings()
        
        self.status = "failed"
        return {
            'success': False,
            'lyft_booking': None,
            'message': f"Could not get Lyft - not enough filler accounts or RideSmart has too much capacity"
        }
    
    def get_status(self):
        """Get current status for UI."""
        return {
            'status': self.status,
            'current_step': self.current_step,
            'filler_bookings_count': len(self.filler_bookings),
            'log': self.log
        }


def run_lyft_orchestrator(original_user_key, origin, destination):
    """
    Convenience function to run the orchestrator.
    
    Args:
        original_user_key: str, user key of person who wants Lyft
        origin: dict, origin location
        destination: dict, destination location
    
    Returns:
        dict with success status and booking info
    """
    orchestrator = LyftOrchestrator(original_user_key, origin, destination)
    return orchestrator.run()
