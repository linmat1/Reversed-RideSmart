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
from src.logger import log_lyft_orchestrator
from src.booking_state import booking_state
from src.developer_logs import developer_logs


class LyftOrchestrator:
    """Orchestrates the process of getting a Lyft ride."""
    
    def __init__(self, original_user_key, route_origin, route_destination, log_callback=None):
        """
        Initialize the orchestrator.
        
        Args:
            original_user_key: str, the user key of the person who wants the Lyft
            route_origin: dict, origin location data
            route_destination: dict, destination location data
            log_callback: callable, optional function to call for live logging (receives message string)
        """
        self.original_user_key = original_user_key
        self.route_origin = route_origin
        self.route_destination = route_destination
        self.log_callback = log_callback  # Callback for live logging
        
        # Track state
        self.filler_bookings = []  # List of {user_key, ride_id, user_name} for cleanup
        self.original_lyft_booking = None  # Track original user's Lyft booking: {user_key, ride_id, user_name}
        self.status = "idle"  # idle, searching, booking, success, failed
        self.current_step = ""
        self.log = []  # List of log messages
        # If a client disconnects (mobile flakiness / proxy), we must stop booking ASAP and cleanup.
        self.stop_requested = False
        self.stop_reason = None
        
    def _log(self, message):
        """Add a log message with timestamp and optionally send to callback."""
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self.log.append(entry)
        print(entry)
        # Send to callback for live streaming
        if self.log_callback:
            try:
                self.log_callback(entry)
            except Exception as e:
                print(f"Error in log callback: {e}")

    def request_stop(self, reason="stop requested"):
        """Request the orchestrator to stop ASAP (and cleanup)."""
        if not self.stop_requested:
            self.stop_requested = True
            self.stop_reason = reason
            self._log(f"⚠️ Stop requested: {reason}")
        
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
        try:
            try:
                booking_state.set_status(user_key, "searching", "searching for rides...")
            except Exception:
                pass
            auth_token = get_auth_token(user_key)
            user_id = get_user_id(user_key)
            
            response = search_ride(
                origin=self.route_origin,
                destination=self.route_destination,
                auth_token=auth_token,
                user_id=user_id
            )
            
            if not response or 'proposals' not in response:
                try:
                    booking_state.set_status(user_key, "idle")
                except Exception:
                    pass
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
                # Simple approach: scan the entire proposal for "lyft" anywhere
                import json
                proposal_str = json.dumps(p).lower()
                is_lyft = 'lyft' in proposal_str
                
                if is_lyft:
                    lyft_proposals.append(p)
                else:
                    ridesmart_proposals.append(p)
            
            out = {
                'proposals': proposals,
                'has_lyft': len(lyft_proposals) > 0,
                'lyft_proposal': lyft_proposals[0] if lyft_proposals else None,
                'ridesmart_count': len(ridesmart_proposals),
                'ridesmart_proposals': ridesmart_proposals
            }
            try:
                booking_state.set_status(user_key, "idle")
            except Exception:
                pass
            return out
        except Exception as e:
            self._log(f"  ✗ Exception searching rides: {str(e)}")
            try:
                booking_state.set_status(user_key, "error", str(e))
            except Exception:
                pass
            return {
                'proposals': [],
                'has_lyft': False,
                'lyft_proposal': None,
                'ridesmart_count': 0
            }
    
    def _get_ride_details(self, proposal):
        """Extract readable ride details from a proposal."""
        ride_info = proposal.get('ride_info', {})
        pickup = ride_info.get('pickup', {})
        dropoff = ride_info.get('dropoff', {})
        
        pickup_loc = pickup.get('location', {})
        pickup_desc = pickup_loc.get('short_description') or pickup_loc.get('description', 'Unknown')
        dropoff_loc = dropoff.get('location', {})
        dropoff_desc = dropoff_loc.get('short_description') or dropoff_loc.get('description', 'Unknown')
        
        # Check if it's Lyft
        import json
        proposal_str = json.dumps(proposal).lower()
        is_lyft = 'lyft' in proposal_str
        ride_type = "Lyft" if is_lyft else "RideSmart"
        
        return {
            'type': ride_type,
            'pickup': pickup_desc,
            'dropoff': dropoff_desc,
            'proposal_id': proposal.get('proposal_id', 'N/A'),
            'prescheduled_ride_id': proposal.get('prescheduled_ride_id', 'N/A')
        }
    
    def _book_ride(self, user_key, proposal):
        """
        Book a ride as a specific user.
        
        Returns:
            dict with booking response if successful, or dict with error info if failed
        """
        try:
            try:
                booking_state.set_status(user_key, "booking", "booking ride...")
            except Exception:
                pass
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
            
            # Check if response indicates an error
            if response and isinstance(response, dict) and response.get('success') is False:
                # This is an error response from book_ride
                error_msg = response.get('error', 'Unknown error')
                status_code = response.get('status_code', 'N/A')
                try:
                    booking_state.set_status(user_key, "error", error_msg)
                except Exception:
                    pass
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': status_code,
                    'response': response
                }
            
            return response
        except Exception as e:
            # Exception during booking
            error_info = {
                'success': False,
                'error': str(e),
                'status_code': None
            }
            try:
                booking_state.set_status(user_key, "error", str(e))
            except Exception:
                pass
            return error_info
    
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
        if not self.filler_bookings:
            return
        
        self._log(f"Cancelling {len(self.filler_bookings)} filler booking(s)...")
        
        # Log bulk cancellation start
        log_lyft_orchestrator(
            action='filler_cancel_all_start',
            original_user_key=self.original_user_key,
            filler_bookings_count=len(self.filler_bookings)
        )
        
        remaining = []
        for booking in list(self.filler_bookings):
            try:
                user_key = booking['user_key']
                user_name = booking.get('user_name') or USERS.get(user_key, {}).get('name', 'Unknown')
                ride_id = booking.get('ride_id')
                prescheduled_ride_id = booking.get('prescheduled_ride_id')
                
                # We sometimes fail to extract the "confirmed" ride id from the booking response.
                # In those cases, keep a fallback id (prescheduled_ride_id) and try BOTH for cancellation.
                cancel_ids = []
                if ride_id:
                    cancel_ids.append(ride_id)
                if prescheduled_ride_id and prescheduled_ride_id not in cancel_ids:
                    cancel_ids.append(prescheduled_ride_id)

                if cancel_ids:
                    try:
                        booking_state.set_status(user_key, "cancelling", "cancelling filler booking(s)...")
                    except Exception:
                        pass
                    self._log(f"  Cancelling {user_name}'s booking (ride ID(s): {', '.join(str(x) for x in cancel_ids)})...")
                else:
                    self._log(f"  ✗ Cannot cancel {user_name}'s booking: no ride id captured")
                    try:
                        booking_state.set_status(user_key, "error", "cannot cancel: no ride id captured")
                    except Exception:
                        pass
                    remaining.append(booking)
                    continue

                result = None
                for rid in cancel_ids:
                    result = self._cancel_ride(user_key, rid)
                    if result is not None:
                        break
                
                if result is not None:
                    # External server confirmed cancellation (cancel_ride returned non-None)
                    self._log(f"  ✓ Cancelled {user_name}'s booking")
                    try:
                        for rid in cancel_ids:
                            booking_state.remove_active_ride(user_key, int(rid))
                    except Exception:
                        pass
                    try:
                        # Only mark "Cancelled" in developer log when server confirmed
                        for rid in cancel_ids:
                            developer_logs.mark_cancelled(int(rid))
                    except Exception:
                        pass
                    # Log filler cancellation
                    log_lyft_orchestrator(
                        action='filler_cancel',
                        original_user_key=self.original_user_key,
                        filler_user_key=user_key,
                        filler_user_name=user_name,
                        ride_id=ride_id,
                        success=True
                    )
                else:
                    self._log(f"  ✗ Failed to cancel {user_name}'s booking")
                    try:
                        booking_state.set_status(user_key, "error", "failed to cancel booking")
                    except Exception:
                        pass
                    remaining.append(booking)
                    # Log failed filler cancellation
                    log_lyft_orchestrator(
                        action='filler_cancel',
                        original_user_key=self.original_user_key,
                        filler_user_key=user_key,
                        filler_user_name=user_name,
                        ride_id=ride_id or prescheduled_ride_id,
                        success=False
                    )
            except Exception as e:
                self._log(f"  ✗ Exception cancelling {booking.get('user_key', 'unknown')}'s booking: {str(e)}")
                remaining.append(booking)
                try:
                    booking_state.set_status(booking.get('user_key', 'unknown'), "error", str(e))
                except Exception:
                    pass
                log_lyft_orchestrator(
                    action='filler_cancel_error',
                    original_user_key=self.original_user_key,
                    filler_user_key=booking.get('user_key', 'unknown'),
                    error=str(e)
                )
        
        # Log bulk cancellation complete
        log_lyft_orchestrator(
            action='filler_cancel_all_complete',
            original_user_key=self.original_user_key,
            filler_bookings_count=len(self.filler_bookings)
        )
        
        # Only drop bookings that were successfully cancelled.
        # Any remaining bookings will be retried by the final safety-net cleanup.
        self.filler_bookings = remaining
    
    def _cancel_original_lyft_booking(self):
        """Cancel the original user's Lyft booking if it exists."""
        if not self.original_lyft_booking:
            return
        
        try:
            user_key = self.original_lyft_booking['user_key']
            ride_id = self.original_lyft_booking['ride_id']
            user_name = USERS[user_key]['name']
            
            self._log(f"Cancelling {user_name}'s Lyft booking (ride ID: {ride_id})...")
            result = self._cancel_ride(user_key, ride_id)
            
            if result:
                self._log(f"  ✓ Cancelled {user_name}'s Lyft booking")
            else:
                self._log(f"  ✗ Failed to cancel {user_name}'s Lyft booking")
        except Exception as e:
            self._log(f"  ✗ Exception cancelling original Lyft booking: {str(e)}")
        
        self.original_lyft_booking = None
    
    def _cancel_all_rides(self):
        """
        Cancel ALL filler RideSmart bookings (but NOT the Lyft booking).
        This is called in case of any error to ensure no filler rides are left booked.
        The Lyft booking should NEVER be cancelled - that's the whole point!
        """
        self._log(f"\n=== EMERGENCY CLEANUP: Cancelling filler RideSmart bookings ===")
        self._log(f"NOTE: Lyft booking is preserved (that's the goal!)")
        self._cancel_all_filler_bookings()
        self._log(f"=== Cleanup complete ===\n")
    
    def run(self):
        """
        Run the Lyft booking process.
        
        Returns:
            dict with:
                - success: bool
                - lyft_booking: booking response if successful
                - message: status message
        
        CRITICAL: This method MUST ensure all booked rides are cancelled on ANY failure.
        """
        # Track if we've already cleaned up to prevent double cleanup
        cleanup_done = False
        
        def ensure_cleanup():
            """Ensure cleanup happens even if called multiple times.
            Only cancels filler RideSmart bookings, NOT the Lyft booking."""
            nonlocal cleanup_done
            if not cleanup_done:
                cleanup_done = True
                try:
                    # Only cancel filler bookings, preserve Lyft booking.
                    # Retry a few times because mobile/proxy disconnects and transient network issues are common.
                    max_attempts = 3
                    for attempt in range(1, max_attempts + 1):
                        if not self.filler_bookings:
                            break
                        self._log(f"\n--- Cleanup attempt {attempt}/{max_attempts} ---")
                        self._cancel_all_filler_bookings()
                        if self.filler_bookings and attempt < max_attempts:
                            # Small backoff before retrying cancellations
                            time.sleep(min(2 * attempt, 5))
                except Exception as cleanup_error:
                    # Even cleanup can fail, but we try our best
                    print(f"CRITICAL: Cleanup itself failed: {cleanup_error}")
        
        try:
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
                    
                    lyft_proposal = original_result['lyft_proposal']
                    lyft_details = self._get_ride_details(lyft_proposal)
                    
                    self._log(f"  Booking Lyft for {original_name}...")
                    self._log(f"    Pickup: {lyft_details['pickup']}")
                    self._log(f"    Dropoff: {lyft_details['dropoff']}")
                    self._log(f"    Proposal ID: {lyft_details['proposal_id']}")
                    
                    # Log Lyft booking attempt
                    log_lyft_orchestrator(
                        action='lyft_book_attempt',
                        original_user_key=self.original_user_key,
                        original_user_name=original_name,
                        proposal_id=lyft_details['proposal_id'],
                        pickup=lyft_details['pickup'],
                        dropoff=lyft_details['dropoff']
                    )
                    
                    booking = self._book_ride(self.original_user_key, lyft_proposal)
                    
                    # Check if booking was successful
                    if booking and not (isinstance(booking, dict) and booking.get('success') is False):
                        ride_id = None
                        rides = booking.get('prescheduled_recurring_series_rides', [])
                        if rides:
                            ride_id = rides[0].get('id')
                        
                        if ride_id:
                            self.original_lyft_booking = {
                                'user_key': self.original_user_key,
                                'ride_id': ride_id,
                                'user_name': original_name
                            }
                            try:
                                booking_state.upsert_active_ride(self.original_user_key, int(ride_id), ride_type="Lyft", source="orchestrator")
                            except Exception:
                                pass
                            try:
                                developer_logs.append_booking(
                                    user_key=self.original_user_key,
                                    user_name=original_name,
                                    ride_id=int(ride_id),
                                    prescheduled_ride_id=None,
                                    ride_type="Lyft",
                                    source="orchestrator",
                                )
                            except Exception:
                                pass
                        
                        self._log(f"✓ SUCCESS! {original_name} booked Lyft!")
                        if ride_id:
                            self._log(f"  Confirmed Ride ID: {ride_id}")
                        self.status = "success"
                        return {
                            'success': True,
                            'lyft_booking': booking,
                            'message': f"Lyft booked successfully for {original_name}"
                        }
                    else:
                        # Booking failed - extract error details
                        error_msg = "Unknown error"
                        if isinstance(booking, dict):
                            error_msg = booking.get('error', 'Unknown error')
                            status_code = booking.get('status_code')
                            if status_code:
                                error_msg = f"{error_msg} (HTTP {status_code})"
                        
                        # Try to extract more specific error from response
                        if isinstance(booking, dict) and booking.get('response'):
                            response_data = booking.get('response')
                            if isinstance(response_data, dict):
                                detailed_error = (response_data.get('message') or 
                                                response_data.get('error') or 
                                                response_data.get('error_message') or
                                                response_data.get('detail'))
                                if detailed_error:
                                    error_msg = detailed_error
                        
                        self._log(f"✗ Failed to book Lyft for {original_name}")
                        self._log(f"  Reason: {error_msg}")
                
                self._log(f"✗ Lyft not available for {original_name}")
            
            self._log(f"RideSmart vehicles available: {result['ridesmart_count']}")
            
            # Step 2: Start filling capacity with filler accounts
            self._log(f"\n--- Step 2: Filling RideSmart capacity ---")
            
            for filler_key in filler_accounts:
                if self.stop_requested:
                    self._log(f"\n⚠️ Stopping early ({self.stop_reason}). Cleaning up filler bookings...")
                    ensure_cleanup()
                    self.status = "failed"
                    return {
                        'success': False,
                        'lyft_booking': None,
                        'message': f"Stopped early: {self.stop_reason}. All filler bookings have been cancelled."
                    }
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
                        
                        lyft_proposal = original_result['lyft_proposal']
                        lyft_details = self._get_ride_details(lyft_proposal)
                        
                        self._log(f"  Booking Lyft for {original_name}...")
                        self._log(f"    Pickup: {lyft_details['pickup']}")
                        self._log(f"    Dropoff: {lyft_details['dropoff']}")
                        self._log(f"    Proposal ID: {lyft_details['proposal_id']}")
                        
                        booking = self._book_ride(self.original_user_key, lyft_proposal)
                        
                        # Check if booking was successful
                        if booking and not (isinstance(booking, dict) and booking.get('success') is False):
                            ride_id = None
                            rides = booking.get('prescheduled_recurring_series_rides', [])
                            if rides:
                                ride_id = rides[0].get('id')
                            
                            if ride_id:
                                self.original_lyft_booking = {
                                    'user_key': self.original_user_key,
                                    'ride_id': ride_id,
                                    'user_name': original_name
                                }
                                try:
                                    booking_state.upsert_active_ride(self.original_user_key, int(ride_id), ride_type="Lyft", source="orchestrator")
                                except Exception:
                                    pass
                                try:
                                    developer_logs.append_booking(
                                        user_key=self.original_user_key,
                                        user_name=original_name,
                                        ride_id=int(ride_id),
                                        prescheduled_ride_id=None,
                                        ride_type="Lyft",
                                        source="orchestrator",
                                    )
                                except Exception:
                                    pass
                            
                            self._log(f"✓ SUCCESS! {original_name} booked Lyft!")
                            if ride_id:
                                self._log(f"  Confirmed Ride ID: {ride_id}")
                            
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
                            # Booking failed - extract error details
                            error_msg = "Unknown error"
                            if isinstance(booking, dict):
                                error_msg = booking.get('error', 'Unknown error')
                                status_code = booking.get('status_code')
                                if status_code:
                                    error_msg = f"{error_msg} (HTTP {status_code})"
                            
                            # Try to extract more specific error from response
                            if isinstance(booking, dict) and booking.get('response'):
                                response_data = booking.get('response')
                                if isinstance(response_data, dict):
                                    detailed_error = (response_data.get('message') or 
                                                    response_data.get('error') or 
                                                    response_data.get('error_message') or
                                                    response_data.get('detail'))
                                    if detailed_error:
                                        error_msg = detailed_error
                            
                            self._log(f"✗ Failed to book Lyft for {original_name}")
                            self._log(f"  Reason: {error_msg}")
                            # Error occurred - cancel filler bookings only
                            ensure_cleanup()
                            self.status = "failed"
                            return {
                                'success': False,
                                'lyft_booking': None,
                                'message': f"Failed to book Lyft for {original_name}: {error_msg}. All filler bookings have been cancelled."
                            }
                    else:
                        self._log(f"✗ Lyft not available when {original_name} searched")
                
                # Book a RideSmart ride with this filler account to reduce capacity
                if result['ridesmart_count'] > 0 and result.get('ridesmart_proposals'):
                    if self.stop_requested:
                        self._log(f"\n⚠️ Stopping before booking ({self.stop_reason}). Cleaning up filler bookings...")
                        ensure_cleanup()
                        self.status = "failed"
                        return {
                            'success': False,
                            'lyft_booking': None,
                            'message': f"Stopped early: {self.stop_reason}. All filler bookings have been cancelled."
                        }
                    self.status = "booking"
                    self.current_step = f"Booking RideSmart with {filler_name}"
                    
                    # Retry logic for high demand errors
                    max_retries = 3
                    retry_count = 0
                    booking_successful = False
                    
                    while retry_count <= max_retries and not booking_successful:
                        if self.stop_requested:
                            self._log(f"\n⚠️ Stopping during booking retries ({self.stop_reason}). Cleaning up filler bookings...")
                            ensure_cleanup()
                            self.status = "failed"
                            return {
                                'success': False,
                                'lyft_booking': None,
                                'message': f"Stopped early: {self.stop_reason}. All filler bookings have been cancelled."
                            }
                        if retry_count > 0:
                            self._log(f"  Retry attempt {retry_count}/{max_retries} for {filler_name}...")
                            # Wait a bit before retrying (exponential backoff)
                            wait_time = min(2 * retry_count, 5)  # 2s, 4s, 5s max
                            time.sleep(wait_time)
                            
                            # Re-search for rides with this filler account
                            self._log(f"  Re-searching for rides with {filler_name}...")
                            result = self._search_for_rides(filler_key)
                            
                            # Check if Lyft became available during retry
                            if result['has_lyft']:
                                self._log(f"\n✓ Lyft became available during retry!")
                                self._log(f"Searching as {original_name} to book Lyft...")
                                
                                original_result = self._search_for_rides(self.original_user_key)
                                
                                if original_result['has_lyft']:
                                    self.status = "booking"
                                    self.current_step = f"Booking Lyft for {original_name}"
                                    
                                    lyft_proposal = original_result['lyft_proposal']
                                    lyft_details = self._get_ride_details(lyft_proposal)
                                    
                                    self._log(f"  Booking Lyft for {original_name}...")
                                    self._log(f"    Pickup: {lyft_details['pickup']}")
                                    self._log(f"    Dropoff: {lyft_details['dropoff']}")
                                    self._log(f"    Proposal ID: {lyft_details['proposal_id']}")
                                    
                                    booking = self._book_ride(self.original_user_key, lyft_proposal)
                                    
                                    # Check if booking was successful
                                    if booking and not (isinstance(booking, dict) and booking.get('success') is False):
                                        ride_id = None
                                        rides = booking.get('prescheduled_recurring_series_rides', [])
                                        if rides:
                                            ride_id = rides[0].get('id')
                                        
                                        if ride_id:
                                            self.original_lyft_booking = {
                                                'user_key': self.original_user_key,
                                                'ride_id': ride_id,
                                                'user_name': original_name
                                            }
                                            try:
                                                booking_state.upsert_active_ride(self.original_user_key, int(ride_id), ride_type="Lyft", source="orchestrator")
                                            except Exception:
                                                pass
                                            try:
                                                developer_logs.append_booking(
                                                    user_key=self.original_user_key,
                                                    user_name=original_name,
                                                    ride_id=int(ride_id),
                                                    prescheduled_ride_id=None,
                                                    ride_type="Lyft",
                                                    source="orchestrator",
                                                )
                                            except Exception:
                                                pass
                                        
                                        self._log(f"✓ SUCCESS! {original_name} booked Lyft!")
                                        if ride_id:
                                            self._log(f"  Confirmed Ride ID: {ride_id}")
                                        
                                        # Cancel all filler bookings
                                        self._log(f"\n--- Cleanup: Cancelling filler bookings ---")
                                        self._cancel_all_filler_bookings()
                                        
                                        self.status = "success"
                                        return {
                                            'success': True,
                                            'lyft_booking': booking,
                                            'message': f"Lyft booked successfully for {original_name}"
                                        }
                            
                            # Check if RideSmart is still available
                            if result['ridesmart_count'] == 0 or not result.get('ridesmart_proposals'):
                                self._log(f"  No RideSmart rides available for retry with {filler_name}")
                                break
                        
                        ridesmart_proposal = result['ridesmart_proposals'][0]
                        ride_details = self._get_ride_details(ridesmart_proposal)
                        
                        # Log detailed ride information
                        if retry_count == 0:
                            self._log(f"  Booking RideSmart with {filler_name}...")
                        self._log(f"    Ride Type: {ride_details['type']}")
                        self._log(f"    Pickup: {ride_details['pickup']}")
                        self._log(f"    Dropoff: {ride_details['dropoff']}")
                        self._log(f"    Proposal ID: {ride_details['proposal_id']}")
                        self._log(f"    Ride ID: {ride_details['prescheduled_ride_id']}")
                        
                        # Log to file (only on first attempt)
                        if retry_count == 0:
                            log_lyft_orchestrator(
                                action='filler_book',
                                original_user_key=self.original_user_key,
                                filler_user_key=filler_key,
                                filler_user_name=filler_name,
                                ride_type='RideSmart',
                                proposal_id=ride_details['proposal_id'],
                                prescheduled_ride_id=ride_details['prescheduled_ride_id'],
                                pickup=ride_details['pickup'],
                                dropoff=ride_details['dropoff']
                            )
                        
                        booking = self._book_ride(filler_key, ridesmart_proposal)
                        
                        # Check if booking was successful
                        if booking and not (isinstance(booking, dict) and booking.get('success') is False):
                            # Extract ride ID for later cancellation
                            ride_id = None
                            rides = booking.get('prescheduled_recurring_series_rides', [])
                            if rides:
                                ride_id = rides[0].get('id')
                            prescheduled_ride_id = ridesmart_proposal.get('prescheduled_ride_id')
                            
                            # Always track *something* that can be cancelled later.
                            # `ride_id` is preferred, but `prescheduled_ride_id` is a useful fallback.
                            self.filler_bookings.append({
                                'user_key': filler_key,
                                'user_name': filler_name,
                                'ride_id': ride_id,
                                'prescheduled_ride_id': prescheduled_ride_id
                            })

                            # Emit logs in a consistent format so the frontend can reliably parse them.
                            # Use whichever id we have available.
                            display_id = ride_id or prescheduled_ride_id
                            if display_id:
                                self._log(f"  ✓ {filler_name} booked RideSmart (ride ID: {display_id})")
                            else:
                                self._log(f"  ✓ {filler_name} booked RideSmart (ride ID: unknown)")
                            if ride_id:
                                self._log(f"    Confirmed Ride ID: {ride_id}")

                            # Update shared state (prefer confirmed ride_id, fallback to prescheduled id).
                            try:
                                if ride_id:
                                    booking_state.upsert_active_ride(filler_key, int(ride_id), ride_type="RideSmart", source="orchestrator")
                                elif prescheduled_ride_id:
                                    booking_state.upsert_active_ride(filler_key, int(prescheduled_ride_id), ride_type="RideSmart", source="orchestrator")
                            except Exception:
                                pass
                            try:
                                developer_logs.append_booking(
                                    user_key=filler_key,
                                    user_name=filler_name,
                                    ride_id=int(ride_id) if ride_id else None,
                                    prescheduled_ride_id=int(prescheduled_ride_id) if prescheduled_ride_id else None,
                                    ride_type="RideSmart",
                                    source="orchestrator",
                                    lyft_for_user_key=self.original_user_key,
                                    lyft_for_user_name=original_name,
                                )
                            except Exception:
                                pass
                            if ride_id:
                                log_lyft_orchestrator(
                                    action='filler_book_success',
                                    original_user_key=self.original_user_key,
                                    filler_user_key=filler_key,
                                    filler_user_name=filler_name,
                                    ride_id=ride_id
                                )
                                booking_successful = True
                            elif prescheduled_ride_id:
                                booking_successful = True
                            else:
                                self._log(f"  ⚠ {filler_name} booked but couldn't extract confirmed ride ID (will cancel using fallback if possible)")
                                log_lyft_orchestrator(
                                    action='filler_book_success_no_ride_id',
                                    original_user_key=self.original_user_key,
                                    filler_user_key=filler_key,
                                    filler_user_name=filler_name,
                                    prescheduled_ride_id=prescheduled_ride_id
                                )
                                booking_successful = True  # Still count as success
                        else:
                            # Booking failed - extract error details
                            error_msg = "Unknown error"
                            if isinstance(booking, dict):
                                error_msg = booking.get('error', 'Unknown error')
                                status_code = booking.get('status_code')
                                if status_code:
                                    error_msg = f"{error_msg} (HTTP {status_code})"
                            
                            # Try to extract more specific error from response
                            if isinstance(booking, dict) and booking.get('response'):
                                response_data = booking.get('response')
                                if isinstance(response_data, dict):
                                    # Look for common error message fields
                                    detailed_error = (response_data.get('message') or 
                                                    response_data.get('error') or 
                                                    response_data.get('error_message') or
                                                    response_data.get('detail'))
                                    if detailed_error:
                                        error_msg = detailed_error
                            
                            self._log(f"  ✗ Failed to book RideSmart with {filler_name}")
                            self._log(f"    Reason: {error_msg}")
                            
                            # Check if this is the high demand error that we should retry
                            high_demand_error = "We're currently experiencing very high demand" in error_msg or \
                                              "all our seats are filled" in error_msg.lower() or \
                                              "high demand" in error_msg.lower()
                            
                            if high_demand_error and retry_count < max_retries:
                                self._log(f"    High demand detected - will retry...")
                                retry_count += 1
                                # Continue loop to retry
                            else:
                                # Not a retryable error or max retries reached
                                if retry_count >= max_retries:
                                    self._log(f"    Max retries ({max_retries}) reached for {filler_name}")
                                
                                # Log failed filler booking attempt
                                log_lyft_orchestrator(
                                    action='filler_book_failed',
                                    original_user_key=self.original_user_key,
                                    filler_user_key=filler_key,
                                    filler_user_name=filler_name,
                                    error=error_msg
                                )
                                break  # Exit retry loop
                else:
                    self._log(f"  No RideSmart rides available to book")
            
            # If we get here, we've used all filler accounts but no Lyft
            self._log(f"\n--- All filler accounts used, checking one more time ---")
            
            # Final check with original user
            original_result = self._search_for_rides(self.original_user_key)
            
            if original_result['has_lyft']:
                self.status = "booking"
                self.current_step = f"Booking Lyft for {original_name}"
                
                lyft_proposal = original_result['lyft_proposal']
                lyft_details = self._get_ride_details(lyft_proposal)
                
                self._log(f"  Booking Lyft for {original_name}...")
                self._log(f"    Pickup: {lyft_details['pickup']}")
                self._log(f"    Dropoff: {lyft_details['dropoff']}")
                self._log(f"    Proposal ID: {lyft_details['proposal_id']}")
                
                booking = self._book_ride(self.original_user_key, lyft_proposal)
                
                # Check if booking was successful
                if booking and not (isinstance(booking, dict) and booking.get('success') is False):
                    ride_id = None
                    rides = booking.get('prescheduled_recurring_series_rides', [])
                    if rides:
                        ride_id = rides[0].get('id')
                    
                    if ride_id:
                        self.original_lyft_booking = {
                            'user_key': self.original_user_key,
                            'ride_id': ride_id,
                            'user_name': original_name
                        }
                        try:
                            booking_state.upsert_active_ride(self.original_user_key, int(ride_id), ride_type="Lyft", source="orchestrator")
                        except Exception:
                            pass
                        try:
                            developer_logs.append_booking(
                                user_key=self.original_user_key,
                                user_name=original_name,
                                ride_id=int(ride_id),
                                prescheduled_ride_id=None,
                                ride_type="Lyft",
                                source="orchestrator",
                            )
                        except Exception:
                            pass
                    
                    self._log(f"✓ SUCCESS! {original_name} booked Lyft!")
                    if ride_id:
                        self._log(f"  Confirmed Ride ID: {ride_id}")
                    
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
                    # Booking failed - extract error details
                    error_msg = "Unknown error"
                    if isinstance(booking, dict):
                        error_msg = booking.get('error', 'Unknown error')
                        status_code = booking.get('status_code')
                        if status_code:
                            error_msg = f"{error_msg} (HTTP {status_code})"
                    
                    # Try to extract more specific error from response
                    if isinstance(booking, dict) and booking.get('response'):
                        response_data = booking.get('response')
                        if isinstance(response_data, dict):
                            detailed_error = (response_data.get('message') or 
                                            response_data.get('error') or 
                                            response_data.get('error_message') or
                                            response_data.get('detail'))
                            if detailed_error:
                                error_msg = detailed_error
                    
                    self._log(f"✗ Failed to book Lyft for {original_name}")
                    self._log(f"  Reason: {error_msg}")
            
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
        except KeyboardInterrupt:
            # Handle interruption gracefully
            self._log(f"\n⚠️ INTERRUPTED: Process was interrupted")
            ensure_cleanup()
            # Check if we have a Lyft booking to preserve
            if self.original_lyft_booking:
                self.status = "success"
                return {
                    'success': True,
                    'lyft_booking': {'prescheduled_recurring_series_rides': [{'id': self.original_lyft_booking['ride_id']}]},
                    'message': "Process was interrupted, but Lyft booking is preserved. Filler bookings cancelled."
                }
            self.status = "failed"
            return {
                'success': False,
                'lyft_booking': None,
                'message': "Process was interrupted. All filler bookings have been cancelled."
            }
        except Exception as e:
            # CRITICAL: Cancel filler bookings on any error, but preserve Lyft if it exists
            self._log(f"\n⚠️ CRITICAL ERROR: {str(e)}")
            self._log(f"=== EMERGENCY CLEANUP: Cancelling filler RideSmart bookings ===")
            ensure_cleanup()
            # Check if we have a Lyft booking to preserve
            if self.original_lyft_booking:
                self._log(f"✓ Lyft booking preserved (ride ID: {self.original_lyft_booking['ride_id']})")
                self.status = "success"
                return {
                    'success': True,
                    'lyft_booking': {'prescheduled_recurring_series_rides': [{'id': self.original_lyft_booking['ride_id']}]},
                    'message': f"Error occurred, but Lyft booking is preserved. Filler bookings cancelled: {str(e)}"
                }
            self.status = "failed"
            return {
                'success': False,
                'lyft_booking': None,
                'message': f"Error occurred: {str(e)}. All filler bookings have been cancelled."
            }
        finally:
            # FINAL SAFETY NET: Ensure cleanup happens no matter what
            ensure_cleanup()
    
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
