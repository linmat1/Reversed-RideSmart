"""
Lyft Orchestrator Module

This module handles the logic for getting a Lyft ride by:
1. Having filler accounts book RideSmart rides to fill capacity
2. Once Lyft becomes available, the original person books the Lyft
3. All filler bookings are then cancelled
"""

import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
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
        """Add a log message with timestamp (Chicago time) and optionally send to callback."""
        timestamp = datetime.now(ZoneInfo("America/Chicago")).strftime("%H:%M:%S")
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
    
    def _book_lyft_for_original(self, lyft_proposal, original_name):
        """
        Book Lyft for the original user.
        Extracted to avoid duplicating this logic across multiple call sites in run().

        Returns:
            dict with success, lyft_booking, message
        """
        lyft_details = self._get_ride_details(lyft_proposal)

        self._log(f"  Booking Lyft for {original_name}...")
        self._log(f"    Pickup: {lyft_details['pickup']}")
        self._log(f"    Dropoff: {lyft_details['dropoff']}")
        self._log(f"    Proposal ID: {lyft_details['proposal_id']}")

        log_lyft_orchestrator(
            action='lyft_book_attempt',
            original_user_key=self.original_user_key,
            original_user_name=original_name,
            proposal_id=lyft_details['proposal_id'],
            pickup=lyft_details['pickup'],
            dropoff=lyft_details['dropoff']
        )

        booking = self._book_ride(self.original_user_key, lyft_proposal)

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

            return {
                'success': True,
                'lyft_booking': booking,
                'message': f"Lyft booked successfully for {original_name}"
            }

        # Extract error details
        error_msg = "Unknown error"
        if isinstance(booking, dict):
            error_msg = booking.get('error', 'Unknown error')
            status_code = booking.get('status_code')
            if status_code:
                error_msg = f"{error_msg} (HTTP {status_code})"
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

        return {
            'success': False,
            'lyft_booking': None,
            'message': f"Failed to book Lyft for {original_name}: {error_msg}"
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
        """Cancel all filler bookings in parallel."""
        if not self.filler_bookings:
            return

        self._log(f"Cancelling {len(self.filler_bookings)} filler booking(s) in parallel...")

        log_lyft_orchestrator(
            action='filler_cancel_all_start',
            original_user_key=self.original_user_key,
            filler_bookings_count=len(self.filler_bookings)
        )

        bookings_to_cancel = list(self.filler_bookings)
        remaining = []
        remaining_lock = threading.Lock()

        def cancel_one(booking):
            try:
                user_key = booking['user_key']
                user_name = booking.get('user_name') or USERS.get(user_key, {}).get('name', 'Unknown')
                ride_id = booking.get('ride_id')
                prescheduled_ride_id = booking.get('prescheduled_ride_id')

                # Try confirmed ride_id first, fall back to prescheduled_ride_id.
                cancel_ids = []
                if ride_id:
                    cancel_ids.append(ride_id)
                if prescheduled_ride_id and prescheduled_ride_id not in cancel_ids:
                    cancel_ids.append(prescheduled_ride_id)

                if not cancel_ids:
                    self._log(f"  ✗ Cannot cancel {user_name}'s booking: no ride id captured")
                    try:
                        booking_state.set_status(user_key, "error", "cannot cancel: no ride id captured")
                    except Exception:
                        pass
                    with remaining_lock:
                        remaining.append(booking)
                    return

                try:
                    booking_state.set_status(user_key, "cancelling", "cancelling filler booking(s)...")
                except Exception:
                    pass

                self._log(f"  Cancelling {user_name}'s booking (ride ID(s): {', '.join(str(x) for x in cancel_ids)})...")

                result = None
                for rid in cancel_ids:
                    result = self._cancel_ride(user_key, rid)
                    if result is not None:
                        break

                if result is not None:
                    self._log(f"  ✓ Cancelled {user_name}'s booking")
                    try:
                        for rid in cancel_ids:
                            booking_state.remove_active_ride(user_key, int(rid))
                    except Exception:
                        pass
                    try:
                        for rid in cancel_ids:
                            developer_logs.mark_cancelled(int(rid))
                    except Exception:
                        pass
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
                    with remaining_lock:
                        remaining.append(booking)
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
                with remaining_lock:
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

        with ThreadPoolExecutor(max_workers=max(1, len(bookings_to_cancel))) as executor:
            futures = [executor.submit(cancel_one, b) for b in bookings_to_cancel]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    pass

        log_lyft_orchestrator(
            action='filler_cancel_all_complete',
            original_user_key=self.original_user_key,
            filler_bookings_count=len(self.filler_bookings)
        )

        # Only drop bookings that were successfully cancelled.
        # Any remaining will be retried by ensure_cleanup().
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

        Flow:
            Phase 1   — Parallel searches: all filler accounts search simultaneously (~12s)
            Phase 2+3 — Simultaneous: fillers book in parallel while original user polls for Lyft (~12-24s)
                         Fillers distributed across vehicles (filler i → vehicle i % num_vehicles).
            Phase 4   — Lyft booking: book Lyft for original user (~12s)
            Phase 5   — Parallel cleanup: cancel all filler bookings simultaneously (~12s)
        """
        cleanup_done = False
        filler_bookings_lock = threading.Lock()

        def ensure_cleanup():
            """Cancel all filler bookings, retrying up to 3 times. Never cancels the Lyft booking."""
            nonlocal cleanup_done
            if not cleanup_done:
                cleanup_done = True
                try:
                    max_attempts = 3
                    for attempt in range(1, max_attempts + 1):
                        if not self.filler_bookings:
                            break
                        self._log(f"\n--- Cleanup attempt {attempt}/{max_attempts} ---")
                        self._cancel_all_filler_bookings()
                        if self.filler_bookings and attempt < max_attempts:
                            time.sleep(min(2 * attempt, 5))
                except Exception as cleanup_error:
                    print(f"CRITICAL: Cleanup itself failed: {cleanup_error}")
        
        try:
            self.status = "searching"
            self.log = []
            original_name = USERS[self.original_user_key]['name']
            filler_accounts = self._get_filler_accounts()

            self._log(f"=== Starting Lyft Orchestrator ===")
            self._log(f"Original user: {original_name}")
            self._log(f"Filler accounts: {[USERS[k]['name'] for k in filler_accounts]}")

            if not filler_accounts:
                self._log("ERROR: No filler accounts available!")
                self.status = "failed"
                return {
                    'success': False,
                    'lyft_booking': None,
                    'message': "No filler accounts available"
                }

            # ── Phase 1: Parallel searches ────────────────────────────────────
            self._log(f"\n--- Phase 1: Searching with all {len(filler_accounts)} filler accounts in parallel ---")
            self.current_step = "Searching (parallel)"

            filler_results = {}
            with ThreadPoolExecutor(max_workers=len(filler_accounts)) as executor:
                futures = {executor.submit(self._search_for_rides, key): key for key in filler_accounts}
                for future in as_completed(futures):
                    key = futures[future]
                    try:
                        filler_results[key] = future.result()
                    except Exception as e:
                        self._log(f"  Search failed for {USERS[key]['name']}: {e}")
                        filler_results[key] = {
                            'proposals': [], 'has_lyft': False,
                            'lyft_proposal': None, 'ridesmart_count': 0
                        }

            total_ridesmart = sum(r.get('ridesmart_count', 0) for r in filler_results.values())
            self._log(f"  Searches complete: {total_ridesmart} total RideSmart vehicle(s) seen")

            # Fast path: Lyft already available before any bookings
            if any(r['has_lyft'] for r in filler_results.values()):
                self._log(f"✓ Lyft already available! Skipping filler bookings.")
                self._log(f"  Searching as {original_name} to book Lyft...")
                original_result = self._search_for_rides(self.original_user_key)
                if original_result['has_lyft']:
                    self.status = "booking"
                    self.current_step = f"Booking Lyft for {original_name}"
                    result = self._book_lyft_for_original(original_result['lyft_proposal'], original_name)
                    self.status = "success" if result['success'] else "failed"
                    return result
                self._log(f"✗ Lyft not available when {original_name} searched")

            # Stop check between phases
            if self.stop_requested:
                self._log(f"\n⚠️ Stop requested. No filler bookings were made.")
                self.status = "failed"
                return {
                    'success': False,
                    'lyft_booking': None,
                    'message': f"Stopped early: {self.stop_reason}. No filler bookings were made."
                }

            # ── Phase 2+3 (simultaneous): Filler bookings + Lyft polling ─────
            self._log(f"\n--- Phase 2: Booking {len(filler_accounts)} fillers in parallel while polling for Lyft ---")
            self.current_step = "Booking fillers (parallel)"
            self.status = "booking"

            # Infrastructure for parallel Lyft polling
            lyft_found_event = threading.Event()
            phase2_complete = threading.Event()
            lyft_result_holder = [None]

            def poll_for_lyft():
                """Search for Lyft continuously until found or Phase 2 finishes without finding it."""
                attempt = 0
                while not self.stop_requested:
                    attempt += 1
                    self._log(f"  [{original_name} search #{attempt}] Searching for Lyft...")
                    result = self._search_for_rides(self.original_user_key)
                    if result['has_lyft']:
                        self._log(f"  [{original_name} search #{attempt}] ✓ Lyft found!")
                        lyft_result_holder[0] = result
                        lyft_found_event.set()
                        return
                    self._log(f"  [{original_name} search #{attempt}] No Lyft yet")
                    # Phase 2 finished and this search didn't find Lyft — stop polling
                    if phase2_complete.is_set():
                        return

            def book_filler(filler_index, filler_key):
                filler_name = USERS[filler_key]['name']
                current_result = filler_results.get(filler_key, {})
                max_retries = 3
                retry_count = 0

                while retry_count <= max_retries:
                    if self.stop_requested:
                        return None

                    proposals = current_result.get('ridesmart_proposals', [])
                    if not proposals:
                        if retry_count == 0:
                            self._log(f"  {filler_name}: no RideSmart proposals available")
                        return None

                    if retry_count > 0:
                        self._log(f"  {filler_name}: retry {retry_count}/{max_retries}...")

                    # Distribute fillers across vehicles: filler 0 → slot 0, filler 1 → slot 1, etc.
                    slot = filler_index % len(proposals)
                    proposal = proposals[slot]
                    ride_details = self._get_ride_details(proposal)

                    if retry_count == 0:
                        self._log(f"  Booking RideSmart with {filler_name} (vehicle slot {slot + 1}/{len(proposals)})...")
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

                    booking = self._book_ride(filler_key, proposal)

                    if booking and not (isinstance(booking, dict) and booking.get('success') is False):
                        ride_id = None
                        rides = booking.get('prescheduled_recurring_series_rides', [])
                        if rides:
                            ride_id = rides[0].get('id')
                        prescheduled_ride_id = proposal.get('prescheduled_ride_id')

                        entry = {
                            'user_key': filler_key,
                            'user_name': filler_name,
                            'ride_id': ride_id,
                            'prescheduled_ride_id': prescheduled_ride_id,
                        }
                        with filler_bookings_lock:
                            self.filler_bookings.append(entry)

                        display_id = ride_id or prescheduled_ride_id
                        self._log(f"  ✓ {filler_name} booked RideSmart (ride ID: {display_id or 'unknown'})")

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
                        log_lyft_orchestrator(
                            action='filler_book_success',
                            original_user_key=self.original_user_key,
                            filler_user_key=filler_key,
                            filler_user_name=filler_name,
                            ride_id=ride_id or prescheduled_ride_id
                        )
                        return entry

                    # Booking failed — extract error and check if retryable
                    error_msg = "Unknown error"
                    if isinstance(booking, dict):
                        error_msg = booking.get('error', 'Unknown error')
                        status_code = booking.get('status_code')
                        if status_code:
                            error_msg = f"{error_msg} (HTTP {status_code})"
                    if isinstance(booking, dict) and booking.get('response'):
                        response_data = booking.get('response')
                        if isinstance(response_data, dict):
                            detailed_error = (response_data.get('message') or
                                              response_data.get('error') or
                                              response_data.get('error_message') or
                                              response_data.get('detail'))
                            if detailed_error:
                                error_msg = detailed_error

                    self._log(f"  ✗ {filler_name} failed: {error_msg}")

                    high_demand = ("We're currently experiencing very high demand" in error_msg or
                                   "all our seats are filled" in error_msg.lower() or
                                   "high demand" in error_msg.lower())

                    if high_demand and retry_count < max_retries:
                        wait_time = min(2 * (retry_count + 1), 5)
                        self._log(f"    High demand — waiting {wait_time}s then retrying...")
                        time.sleep(wait_time)
                        current_result = self._search_for_rides(filler_key)
                        retry_count += 1
                    else:
                        log_lyft_orchestrator(
                            action='filler_book_failed',
                            original_user_key=self.original_user_key,
                            filler_user_key=filler_key,
                            filler_user_name=filler_name,
                            error=error_msg
                        )
                        return None

                return None

            # Start Lyft polling in background while fillers book
            poll_thread = threading.Thread(target=poll_for_lyft, daemon=True)
            poll_thread.start()

            with ThreadPoolExecutor(max_workers=len(filler_accounts)) as executor:
                futures = [executor.submit(book_filler, i, key) for i, key in enumerate(filler_accounts)]
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception:
                        pass

            phase2_complete.set()
            poll_thread.join()  # wait for current search cycle to finish (at most ~12s)

            successful = len(self.filler_bookings)
            self._log(f"\n  {successful}/{len(filler_accounts)} filler accounts booked successfully")

            # Stop check between phases
            if self.stop_requested:
                self._log(f"\n⚠️ Stop requested. Cleaning up {successful} filler booking(s)...")
                ensure_cleanup()
                self.status = "failed"
                return {
                    'success': False,
                    'lyft_booking': None,
                    'message': f"Stopped early: {self.stop_reason}. All filler bookings have been cancelled."
                }

            # ── Phase 4: Book Lyft (if found during polling) ──────────────────
            if lyft_found_event.is_set():
                self._log(f"\n✓ Lyft is available!")
                self.status = "booking"
                self.current_step = f"Booking Lyft for {original_name}"
                result = self._book_lyft_for_original(lyft_result_holder[0]['lyft_proposal'], original_name)

                # ── Phase 5: Cancel all fillers in parallel ───────────────────
                self._log(f"\n--- Phase 5: Cancelling {len(self.filler_bookings)} filler booking(s) in parallel ---")
                ensure_cleanup()

                self.status = "success" if result['success'] else "failed"
                if not result['success']:
                    result['message'] += ". All filler bookings have been cancelled."
                return result
            else:
                self._log(f"✗ Lyft did not appear after filling capacity")
                ensure_cleanup()
                self.status = "failed"
                return {
                    'success': False,
                    'lyft_booking': None,
                    'message': "Lyft did not appear after filling capacity. All filler bookings have been cancelled."
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
