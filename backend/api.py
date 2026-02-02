"""
Flask API backend for RideSmart React frontend
Exposes Python functions as REST API endpoints
"""
from flask import Flask, jsonify, request, Response, session, stream_with_context
from flask_cors import CORS
from src.search_ride import search_ride
from src.book_ride import book_ride
from src.cancel_ride import cancel_ride
from src.get_route import get_route
from src import config
from src.destination_config import LOCATIONS, get_location_pair
from src.users import list_users, get_user, get_auth_token, get_user_id, USERS, verify_password, user_has_password
from src.lyft_orchestrator import LyftOrchestrator
from src.logger import log_booking, log_lyft_orchestrator, log_search
from src.booking_state import booking_state
from src.developer_logs import developer_logs
from src.developer_logs_db import get_storage_info
import json
import os
import queue
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-in-production')
# Allow credentials so session cookies work with frontend
# With credentials, browser requires a specific origin (not *). Default for dev.
_cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:3000').strip().split(',')
CORS(app, supports_credentials=True, origins=[o.strip() for o in _cors_origins if o.strip()])

# Initialize server-owned booking state with known users (safe if USERS is empty).
try:
    booking_state.init_users(USERS)
except Exception as e:
    print(f"Warning: could not init booking state users: {e}")


def login_required():
    """True if any user has a password (login is enforced)."""
    return any(user_has_password(k) for k in USERS)


def get_current_user_key():
    """
    Return the authenticated user key for this request.
    - If login is required and session has a valid user_id, return it.
    - If login is required and no valid session, return None.
    - If login is not required, return user_id from request body or DEFAULT_USER.
    """
    if login_required():
        session_user = session.get('user_id')
        if session_user and session_user in USERS:
            return session_user
        return None
    data = request.get_json(silent=True) or {}
    return data.get('user_id') or os.environ.get('DEFAULT_USER', 'matthew')


@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Log in with user_id (username) and password. No sign-up; admin provides passwords."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        user_key = (data.get('user_id') or '').strip().lower()
        password = data.get('password') or ''
        if not user_key:
            return jsonify({"error": "user_id required"}), 400
        if not password:
            return jsonify({"error": "password required"}), 400
        if user_key not in USERS:
            return jsonify({"error": "Invalid user or password"}), 401
        if not verify_password(user_key, password):
            return jsonify({"error": "Invalid user or password"}), 401
        session['user_id'] = user_key
        user = get_user(user_key)
        return jsonify({
            "user": {"id": user_key, "name": user["name"]},
            "message": "Logged in"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """Log out the current user."""
    try:
        session.pop('user_id', None)
        return jsonify({"message": "Logged out"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    """Return the current user if logged in; 401 if login required but not logged in."""
    if not login_required():
        # No passwords configured: return first user as "current" for compatibility
        first_key = next(iter(USERS), None)
        if first_key:
            u = get_user(first_key)
            return jsonify({"user": {"id": first_key, "name": u["name"]}})
        return jsonify({"error": "No users configured"}), 500
    user_key = session.get('user_id')
    if not user_key or user_key not in USERS:
        return jsonify({"error": "Not logged in"}), 401
    user = get_user(user_key)
    return jsonify({"user": {"id": user_key, "name": user["name"]}})


def require_user():
    """Return (user_key, None) for the current request user, or (None, error_response) if unauthorized."""
    user_key = get_current_user_key()
    if user_key:
        return user_key, None
    if login_required():
        return None, (jsonify({"error": "Not logged in"}), 401)
    return None, (jsonify({"error": "user_id required"}), 400)


@app.route('/')
def index():
    """Health check / API info"""
    return jsonify({
        "status": "ok",
        "message": "RideSmart API is running",
        "endpoints": [
            "POST /api/auth/login",
            "POST /api/auth/logout",
            "GET  /api/auth/me",
            "GET  /api/config",
            "GET  /api/routes",
            "GET  /api/users",
            "POST /api/search",
            "POST /api/book",
            "POST /api/cancel",
            "GET  /api/status",
            "GET  /api/status/stream",
            "POST /api/lyft/run",
            "POST /api/lyft/check",
            "GET  /api/developer/stream",
            "GET  /api/developer/snapshot",
            "GET  /api/developer/storage",
            "POST /api/developer/access",
            "GET  /api/cron/cancel-stale-fillers (cron: every minute)"
        ]
    })


# --- Developer logs (real-time ride log + user access log) ---
@app.route('/api/developer/stream', methods=['GET'])
def developer_stream():
    """Server-Sent Events stream of developer logs (ride log + user access log)."""
    subscriber_q = developer_logs.subscribe()

    def generate():
        try:
            while True:
                try:
                    payload = subscriber_q.get(timeout=10)
                    yield f"data: {payload}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            developer_logs.unsubscribe(subscriber_q)
            raise
        except Exception:
            developer_logs.unsubscribe(subscriber_q)
            raise

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@app.route('/api/developer/snapshot', methods=['GET'])
def developer_snapshot():
    """One-off snapshot of developer logs."""
    try:
        return jsonify(developer_logs.snapshot())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/developer/access', methods=['POST', 'GET'])
def developer_access():
    """Record a website access (IP, time, user-agent). Called by frontend on load."""
    try:
        ip = request.remote_addr or ""
        user_agent = request.headers.get("User-Agent") or ""
        path = request.args.get("path") or request.path or "/"
        developer_logs.append_access(ip=ip, user_agent=user_agent, path=path)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/developer/storage', methods=['GET'])
def developer_storage():
    """Return which DB is used for developer logs (postgres = persists; sqlite on Vercel does not)."""
    try:
        return jsonify(get_storage_info())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get server-owned booking status snapshot (all users). Requires login if passwords are set."""
    try:
        if login_required():
            user_key, err = require_user()
            if err:
                return err
        return jsonify(booking_state.snapshot())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/status/stream', methods=['GET'])
def stream_status():
    """Server-Sent Events stream of booking status snapshots. Requires login if passwords are set."""
    if login_required():
        user_key, err = require_user()
        if err:
            return err
    subscriber_q = booking_state.subscribe()

    def generate():
        try:
            while True:
                try:
                    payload = subscriber_q.get(timeout=10)
                    yield f"data: {payload}\n\n"
                except queue.Empty:
                    # keepalive (prevents some proxies from closing idle connections)
                    yield ": keepalive\n\n"
        except GeneratorExit:
            # Client disconnected
            booking_state.unsubscribe(subscriber_q)
            raise
        except Exception:
            booking_state.unsubscribe(subscriber_q)
            raise

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

@app.route('/api/search', methods=['POST'])
def search():
    """Search for available rides"""
    try:
        user_key, err = require_user()
        if err:
            return err

        # Use default origin/destination from config
        origin = config.default_origin
        destination = config.default_destination

        # Allow custom origin/destination from request body if provided
        data = request.get_json() or {}
        if 'route_id' in data:
            # Use route from destination_config
            try:
                origin, destination = get_location_pair(data['route_id'])
            except ValueError:
                return jsonify({"error": f"Route '{data['route_id']}' not found"}), 400
        elif 'origin' in data:
            origin = data['origin']
        if 'destination' in data and 'route_id' not in data:
            destination = data['destination']

        # User from session / require_user
        auth_token = get_auth_token(user_key)
        user_id = get_user_id(user_key)
        
        # Get user name for logging
        user = get_user(user_key)
        user_name = user.get('name') if user else None

        response = search_ride(origin, destination, auth_token=auth_token, user_id=user_id)

        if response is None:
            booking_state.set_status(user_key, "error", "search failed")
            return jsonify({"error": "Search failed"}), 500
        
        # Log the search
        proposal_count = len(response.get('proposals', []))
        log_search(
            user_key=user_key,
            user_name=user_name,
            route_id=data.get('route_id'),
            origin=origin,
            destination=destination,
            proposal_count=proposal_count
        )
        booking_state.set_status(user_key, "idle")
        return jsonify(response)
    except Exception as e:
        # Don't fail status updates on errors, but try.
        try:
            user_key = get_current_user_key()
            if user_key:
                booking_state.set_status(user_key, "error", str(e))
        except Exception:
            pass
        return jsonify({"error": str(e)}), 500


@app.route('/api/book', methods=['POST'])
def book():
    """Book a ride"""
    try:
        user_key, err = require_user()
        if err:
            return err

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        prescheduled_ride_id = data.get('prescheduled_ride_id')
        proposal_uuid = data.get('proposal_uuid')
        origin = data.get('origin', config.default_origin)
        destination = data.get('destination', config.default_destination)

        if not prescheduled_ride_id or not proposal_uuid:
            return jsonify({"error": "Missing required fields"}), 400

        auth_token = get_auth_token(user_key)
        user_id = get_user_id(user_key)
        ride_type = data.get('ride_type')  # optional, helps status panel

        user = get_user(user_key)
        user_name = user.get('name') if user else None
        booking_state.set_status(user_key, "booking", "booking ride...")
        
        response = book_ride(prescheduled_ride_id, proposal_uuid, origin, destination, 
                            auth_token=auth_token, user_id=user_id)
        
        if response is None:
            # Log failed booking
            log_booking(
                action='book_failed',
                user_key=user_key,
                user_name=user_name,
                prescheduled_ride_id=prescheduled_ride_id,
                proposal_uuid=proposal_uuid,
                origin=origin,
                destination=destination
            )
            booking_state.set_status(user_key, "error", "booking failed")
            return jsonify({"error": "Booking failed"}), 500
        
        # Extract ride ID from response
        ride_id = None
        if isinstance(response, dict):
            rides = response.get('prescheduled_recurring_series_rides', [])
            if rides:
                ride_id = rides[0].get('id')

        # Prefer the confirmed ride id from booking response, but fall back to the
        # prescheduled_ride_id (the one shown in the UI/proposal) so we can still cancel.
        tracked_ride_id = ride_id or prescheduled_ride_id
        if tracked_ride_id:
            booking_state.upsert_active_ride(
                user_key,
                ride_id=int(tracked_ride_id),
                ride_type=ride_type or "unknown",
                source="individual",
            )
        else:
            booking_state.set_status(user_key, "booked", "booked (ride id unknown)")
        
        # Log successful booking
        log_booking(
            action='book',
            user_key=user_key,
            user_name=user_name,
            prescheduled_ride_id=prescheduled_ride_id,
            proposal_uuid=proposal_uuid,
            ride_id=ride_id,
            origin=origin,
            destination=destination
        )
        # Developer ride log (individual booking)
        try:
            developer_logs.append_booking(
                user_key=user_key,
                user_name=user_name or user_key or 'unknown',
                ride_id=int(ride_id) if ride_id is not None else None,
                prescheduled_ride_id=int(prescheduled_ride_id) if prescheduled_ride_id is not None else None,
                ride_type=ride_type or "RideSmart",
                source="individual",
            )
        except Exception:
            pass

        return jsonify(response)
    except Exception as e:
        try:
            user_key = get_current_user_key()
            if user_key:
                booking_state.set_status(user_key, "error", str(e))
        except Exception:
            pass
        return jsonify({"error": str(e)}), 500


@app.route('/api/cancel', methods=['POST'])
def cancel():
    """Cancel a ride"""
    try:
        user_key, err = require_user()
        if err:
            return err

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        ride_id = data.get('ride_id')
        if not ride_id:
            return jsonify({"error": "Missing ride_id"}), 400

        auth_token = get_auth_token(user_key)
        user_id = get_user_id(user_key)

        user = get_user(user_key)
        user_name = user.get('name') if user else None
        booking_state.set_status(user_key, "cancelling", f"cancelling ride {ride_id}...")
        
        response = cancel_ride(ride_id, auth_token=auth_token, user_id=user_id)

        if response is None:
            # External server did not confirm cancellation - do NOT mark as cancelled in developer log
            log_booking(
                action='cancel_failed',
                user_key=user_key,
                user_name=user_name,
                ride_id=ride_id
            )
            booking_state.set_status(user_key, "error", "cancellation failed")
            return jsonify({"error": "Cancellation failed"}), 500

        # Only here: external server confirmed cancellation (cancel_ride returned response)
        log_booking(
            action='cancel',
            user_key=user_key,
            user_name=user_name,
            ride_id=ride_id
        )
        booking_state.remove_active_ride(user_key, int(ride_id))
        try:
            # Developer log: show "Cancelled" only when external server confirmed
            developer_logs.mark_cancelled(int(ride_id))
        except Exception:
            pass
        return jsonify(response)
    except Exception as e:
        try:
            user_key = get_current_user_key()
            if user_key:
                booking_state.set_status(user_key, "error", str(e))
        except Exception:
            pass
        return jsonify({"error": str(e)}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get default origin and destination"""
    try:
        return jsonify({
            "origin": config.default_origin,
            "destination": config.default_destination
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/route/get', methods=['POST'])
def get_ride_route():
    """Get the route for a booked ride"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        route_identifier = data.get('route_identifier')
        if not route_identifier:
            return jsonify({"error": "Missing route_identifier"}), 400
        
        response = get_route(route_identifier)
        
        if response is None:
            return jsonify({"error": "Failed to get route"}), 500
        
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/routes', methods=['GET'])
def get_routes():
    """Get all available routes"""
    try:
        routes = []
        for route_name, route_data in LOCATIONS.items():
            origin = route_data.get("origin", {})
            destination = route_data.get("destination", {})
            routes.append({
                "id": route_name,
                "name": route_name.replace("_", " ").title(),
                "origin": {
                    "name": origin.get("geocoded_addr") or origin.get("full_geocoded_addr") or route_name.split("_to_")[0].replace("_", " ").title(),
                    "data": origin
                },
                "destination": {
                    "name": destination.get("geocoded_addr") or destination.get("full_geocoded_addr") or route_name.split("_to_")[-1].replace("_", " ").title(),
                    "data": destination
                }
            })
        return jsonify({"routes": routes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all available users"""
    try:
        users = list_users()
        return jsonify({"users": users})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/lyft/run', methods=['POST'])
def run_lyft_orchestrator():
    """
    Run the Lyft orchestrator to get a free Lyft ride (with live streaming logs).
    
    Request body:
        - original_user: str, user key of person who wants the Lyft
        - route_id: str, route ID from destination_config (optional)
        - origin: dict, custom origin (optional, used if route_id not provided)
        - destination: dict, custom destination (optional)
    
    Returns Server-Sent Events stream with live logs and final result.
    """
    try:
        user_key, err = require_user()
        if err:
            return err
        # Use logged-in user as the person who gets the Lyft (no impersonation)
        original_user = user_key

        data = request.get_json() or {}
        
        # Get origin/destination
        if 'route_id' in data:
            try:
                origin, destination = get_location_pair(data['route_id'])
            except ValueError:
                return jsonify({"error": f"Route '{data['route_id']}' not found"}), 400
        else:
            origin = data.get('origin', config.default_origin)
            destination = data.get('destination', config.default_destination)
        
        # Create a queue for log messages
        log_queue = queue.Queue()
        result_container = {'result': None}
        
        def log_callback(message):
            """Callback: send to Lyft Booker UI and to developer orchestrator log (same log in Developer tab)."""
            developer_logs.append_orchestrator_log(message)
            log_queue.put(('log', message))
        
        # Store orchestrator instance for emergency cleanup
        orchestrator_instance = {'orchestrator': None}
        
        # Clear orchestrator log so Developer tab shows only this run
        developer_logs.clear_orchestrator_log()
        
        def run_orchestrator():
            """Run the orchestrator in a separate thread."""
            orchestrator = None
            try:
                # Get user name for logging
                original_user_obj = get_user(original_user)
                original_user_name = original_user_obj.get('name') if original_user_obj else None
                
                # Log orchestrator start
                route_info = data.get('route_id') or 'custom'
                log_lyft_orchestrator(
                    action='start',
                    original_user_key=original_user,
                    original_user_name=original_user_name,
                    route_id=data.get('route_id'),
                    origin=origin,
                    destination=destination
                )
                
                orchestrator = LyftOrchestrator(original_user, origin, destination, log_callback=log_callback)
                orchestrator_instance['orchestrator'] = orchestrator  # Store for emergency cleanup
                try:
                    booking_state.set_status(original_user, "orchestrating", "running lyft orchestrator...")
                except Exception:
                    pass
                result = orchestrator.run()
                result_container['result'] = result
                
                # Log orchestrator completion
                if result.get('success'):
                    log_lyft_orchestrator(
                        action='success',
                        original_user_key=original_user,
                        original_user_name=original_user_name,
                        route_id=data.get('route_id'),
                        lyft_booking=result.get('lyft_booking') is not None,
                        filler_bookings_count=len(orchestrator.filler_bookings) if orchestrator else 0
                    )
                else:
                    log_lyft_orchestrator(
                        action='failed',
                        original_user_key=original_user,
                        original_user_name=original_user_name,
                        route_id=data.get('route_id'),
                        message=result.get('message'),
                        filler_bookings_count=len(orchestrator.filler_bookings) if orchestrator else 0
                    )
                
                log_queue.put(('result', result))
            except KeyboardInterrupt:
                # Handle interruption - only cancel filler bookings
                if orchestrator:
                    try:
                        orchestrator._cancel_all_filler_bookings()
                        # Check if Lyft booking exists and preserve it
                        if orchestrator.original_lyft_booking:
                            result_container['result'] = {
                                'success': True,
                                'lyft_booking': {'prescheduled_recurring_series_rides': [{'id': orchestrator.original_lyft_booking['ride_id']}]},
                                'message': 'Process was interrupted, but Lyft booking is preserved. Filler bookings cancelled.'
                            }
                            log_queue.put(('result', result_container['result']))
                        else:
                            log_queue.put(('error', 'Process was interrupted. All filler bookings have been cancelled.'))
                    except:
                        pass
            except Exception as e:
                # CRITICAL: Emergency cleanup - only cancel filler bookings, preserve Lyft
                if orchestrator:
                    try:
                        orchestrator._cancel_all_filler_bookings()
                        # Check if Lyft booking exists and preserve it
                        if orchestrator.original_lyft_booking:
                            result_container['result'] = {
                                'success': True,
                                'lyft_booking': {'prescheduled_recurring_series_rides': [{'id': orchestrator.original_lyft_booking['ride_id']}]},
                                'message': f'Error occurred, but Lyft booking is preserved. Filler bookings cancelled: {str(e)}'
                            }
                            log_queue.put(('result', result_container['result']))
                        else:
                            # Log orchestrator error
                            original_user_obj = get_user(original_user)
                            original_user_name = original_user_obj.get('name') if original_user_obj else None
                            log_lyft_orchestrator(
                                action='error',
                                original_user_key=original_user,
                                original_user_name=original_user_name,
                                error=str(e)
                            )
                            error_msg = f"Error: {str(e)}. All filler bookings have been cancelled."
                            log_queue.put(('error', error_msg))
                    except Exception as cleanup_error:
                        print(f"CRITICAL: Emergency cleanup failed: {cleanup_error}")
                        # Still try to preserve Lyft booking info if available
                        if orchestrator and orchestrator.original_lyft_booking:
                            result_container['result'] = {
                                'success': True,
                                'lyft_booking': {'prescheduled_recurring_series_rides': [{'id': orchestrator.original_lyft_booking['ride_id']}]},
                                'message': f'Error occurred, but Lyft booking is preserved. Cleanup failed: {str(e)}'
                            }
                            log_queue.put(('result', result_container['result']))
                else:
                    # Log orchestrator error
                    original_user_obj = get_user(original_user)
                    original_user_name = original_user_obj.get('name') if original_user_obj else None
                    log_lyft_orchestrator(
                        action='error',
                        original_user_key=original_user,
                        original_user_name=original_user_name,
                        error=str(e)
                    )
                    error_msg = f"Error: {str(e)}. All filler bookings have been cancelled."
                    log_queue.put(('error', error_msg))
            finally:
                # If orchestrator finishes and original user has no active rides tracked here,
                # leave their status as-is; otherwise set to idle.
                try:
                    snap = booking_state.snapshot()
                    u = next((x for x in snap.get("users", []) if x.get("user_key") == original_user), None)
                    if u and not u.get("active_rides"):
                        booking_state.set_status(original_user, "idle")
                except Exception:
                    pass
        
        # Start orchestrator in a thread
        thread = threading.Thread(target=run_orchestrator, daemon=True)
        thread.start()
        
        def generate():
            """Generator function for Server-Sent Events."""
            try:
                while True:
                    try:
                        # Get message from queue with timeout
                        item = log_queue.get(timeout=1)
                        msg_type, content = item
                        
                        if msg_type == 'log':
                            # Send log message
                            yield f"data: {json.dumps({'type': 'log', 'message': content})}\n\n"
                        elif msg_type == 'result':
                            # Send final result
                            yield f"data: {json.dumps({'type': 'result', 'data': content})}\n\n"
                            break
                        elif msg_type == 'error':
                            # Send error
                            yield f"data: {json.dumps({'type': 'error', 'message': content})}\n\n"
                            break
                    except queue.Empty:
                        # Check if thread is still alive
                        if not thread.is_alive():
                            # Thread finished, check for result
                            if result_container['result']:
                                yield f"data: {json.dumps({'type': 'result', 'data': result_container['result']})}\n\n"
                            else:
                                # Thread died without result - emergency cleanup (only filler bookings)
                                if orchestrator_instance['orchestrator']:
                                    try:
                                        orchestrator = orchestrator_instance['orchestrator']
                                        orchestrator._cancel_all_filler_bookings()
                                        # Check if Lyft booking exists and preserve it
                                        if orchestrator.original_lyft_booking:
                                            result_data = {
                                                'success': True,
                                                'lyft_booking': {'prescheduled_recurring_series_rides': [{'id': orchestrator.original_lyft_booking['ride_id']}]},
                                                'message': 'Thread died unexpectedly, but Lyft booking is preserved. Filler bookings cancelled.'
                                            }
                                            yield f"data: {json.dumps({'type': 'result', 'data': result_data})}\n\n"
                                        else:
                                            yield f"data: {json.dumps({'type': 'error', 'message': 'Orchestrator thread died unexpectedly. All filler bookings have been cancelled.'})}\n\n"
                                    except:
                                        yield f"data: {json.dumps({'type': 'error', 'message': 'Orchestrator thread died unexpectedly. Attempted to cancel filler bookings.'})}\n\n"
                                else:
                                    yield f"data: {json.dumps({'type': 'error', 'message': 'Orchestrator thread died unexpectedly.'})}\n\n"
                            break
                        # Send keepalive
                        yield ": keepalive\n\n"
            except GeneratorExit:
                # Client disconnected - emergency cleanup (only filler bookings, preserve Lyft)
                if orchestrator_instance['orchestrator']:
                    try:
                        orchestrator_instance['orchestrator'].request_stop("client disconnected")
                        orchestrator_instance['orchestrator']._cancel_all_filler_bookings()
                        # Lyft booking is preserved automatically since we only cancel filler bookings
                    except:
                        pass
                raise
            except Exception as e:
                # Any other error - emergency cleanup (only filler bookings, preserve Lyft)
                if orchestrator_instance['orchestrator']:
                    try:
                        orchestrator = orchestrator_instance['orchestrator']
                        orchestrator.request_stop(f"stream error: {str(e)}")
                        orchestrator._cancel_all_filler_bookings()
                        # Check if Lyft booking exists and try to send it
                        if orchestrator.original_lyft_booking:
                            result_data = {
                                'success': True,
                                'lyft_booking': {'prescheduled_recurring_series_rides': [{'id': orchestrator.original_lyft_booking['ride_id']}]},
                                'message': f'Stream error, but Lyft booking is preserved. Filler bookings cancelled: {str(e)}'
                            }
                            yield f"data: {json.dumps({'type': 'result', 'data': result_data})}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'error', 'message': f'Stream error: {str(e)}. All filler bookings have been cancelled.'})}\n\n"
                    except:
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Stream error: {str(e)}. Attempted to cancel filler bookings.'})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Stream error: {str(e)}'})}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/lyft/cancel-booking', methods=['POST'])
def cancel_individual_booking():
    """
    Manually cancel a specific booking (filler or original user's booking).
    Logged-in user can only cancel their own bookings unless user_id matches session.
    Request body: ride_id (user_id is the logged-in user).
    """
    try:
        user_key, err = require_user()
        if err:
            return err

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        ride_id = data.get('ride_id')
        if not ride_id:
            return jsonify({"error": "Missing ride_id"}), 400

        # Optional: allow cancelling another user's booking only if body user_id matches session (same user)
        body_user = data.get('user_id')
        if body_user and body_user != user_key:
            return jsonify({"error": "Cannot cancel another user's booking"}), 403
        
        # Cancel the ride
        auth_token = get_auth_token(user_key)
        user_id = get_user_id(user_key)
        try:
            booking_state.set_status(user_key, "cancelling", f"cancelling ride {ride_id}...")
        except Exception:
            pass
        
        response = cancel_ride(ride_id, auth_token=auth_token, user_id=user_id)
        
        if response:
            # External server confirmed cancellation - update developer log so "Cancelled" shows
            user_name = USERS[user_key]['name']
            try:
                booking_state.remove_active_ride(user_key, int(ride_id))
            except Exception:
                pass
            try:
                developer_logs.mark_cancelled(int(ride_id))
            except Exception:
                pass
            return jsonify({
                "success": True,
                "message": f"Successfully cancelled {user_name}'s booking (ride ID: {ride_id})",
                "cancellation_response": response
            })
        else:
            try:
                booking_state.set_status(user_key, "error", "cancellation failed")
            except Exception:
                pass
            return jsonify({
                "success": False,
                "message": f"Failed to cancel booking (ride ID: {ride_id})"
            }), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Cron: cancel filler bookings older than 3.5 minutes (safety net for mobile timeouts / disconnect)
STALE_FILLER_SECONDS = 3.5 * 60  # 210 seconds


@app.route('/api/cron/cancel-stale-fillers', methods=['GET', 'POST'])
def cron_cancel_stale_fillers():
    """
    Cancel all filler RideSmart bookings older than 3.5 minutes.
    Call every minute (e.g. Vercel Cron). Optional: set CRON_SECRET and pass ?secret=... or header X-Cron-Secret.
    """
    secret = request.args.get('secret') or request.headers.get('X-Cron-Secret')
    if os.environ.get('CRON_SECRET') and secret != os.environ.get('CRON_SECRET'):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        snap = developer_logs.snapshot()
        ride_log = snap.get('ride_log') or []
        now = time.time()
        stale = [
            r for r in ride_log
            if r.get('source') == 'orchestrator'
            and r.get('lyft_for_user_key')
            and (r.get('ride_type') or 'RideSmart') == 'RideSmart'
            and not r.get('cancelled')
            and (float(r.get('created_at') or 0) < now - STALE_FILLER_SECONDS)
        ]
        cancelled_count = 0
        for r in stale:
            user_key = r.get('user_key')
            ride_id = r.get('ride_id') or r.get('prescheduled_ride_id')
            if not user_key or ride_id is None:
                continue
            if user_key not in USERS:
                continue
            try:
                auth_token = get_auth_token(user_key)
                user_id = get_user_id(user_key)
                resp = cancel_ride(int(ride_id), auth_token=auth_token, user_id=user_id)
                if resp is not None:
                    developer_logs.mark_cancelled(int(ride_id))
                    cancelled_count += 1
            except Exception:
                pass
        return jsonify({"ok": True, "cancelled": cancelled_count, "checked": len(stale)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/lyft/check', methods=['POST'])
def check_lyft_availability():
    """
    Quick check if Lyft is available for a route (without booking anything).
    Uses logged-in user. Request body: route_id (optional), origin/destination (optional).
    """
    try:
        user_key, err = require_user()
        if err:
            return err

        data = request.get_json() or {}

        auth_token = get_auth_token(user_key)
        user_id = get_user_id(user_key)
        
        # Get origin/destination
        if 'route_id' in data:
            try:
                origin, destination = get_location_pair(data['route_id'])
            except ValueError:
                return jsonify({"error": f"Route '{data['route_id']}' not found"}), 400
        else:
            origin = data.get('origin', config.default_origin)
            destination = data.get('destination', config.default_destination)
        
        # Search for rides
        response = search_ride(origin, destination, auth_token=auth_token, user_id=user_id)
        
        if not response or 'proposals' not in response:
            return jsonify({
                "has_lyft": False,
                "ridesmart_count": 0,
                "proposals": []
            })
        
        proposals = response.get('proposals', [])
        
        # Categorize proposals
        lyft_count = 0
        ridesmart_count = 0
        
        for p in proposals:
            # Simple approach: scan the entire proposal for "lyft" anywhere
            proposal_str = json.dumps(p).lower()
            is_lyft = 'lyft' in proposal_str
            
            if is_lyft:
                lyft_count += 1
            else:
                ridesmart_count += 1
        
        return jsonify({
            "has_lyft": lyft_count > 0,
            "lyft_count": lyft_count,
            "ridesmart_count": ridesmart_count,
            "total_proposals": len(proposals)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

