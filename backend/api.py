"""
Flask API backend for RideSmart React frontend
Exposes Python functions as REST API endpoints
"""
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
from src.search_ride import search_ride
from src.book_ride import book_ride
from src.cancel_ride import cancel_ride
from src.get_route import get_route
from src import config
from src.destination_config import LOCATIONS, get_location_pair
from src.users import list_users, get_user, get_auth_token, get_user_id, USERS
from src.lyft_orchestrator import LyftOrchestrator
from src.logger import log_booking, log_lyft_orchestrator, log_search
import json
import queue
import threading

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

@app.route('/')
def index():
    """Health check / API info"""
    return jsonify({
        "status": "ok",
        "message": "RideSmart API is running",
        "endpoints": [
            "GET  /api/config",
            "GET  /api/routes", 
            "GET  /api/users",
            "POST /api/search",
            "POST /api/book",
            "POST /api/cancel",
            "POST /api/lyft/run",
            "POST /api/lyft/check"
        ]
    })

@app.route('/api/search', methods=['POST'])
def search():
    """Search for available rides"""
    try:
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
        
        # Get user credentials if specified
        user_key = data.get('user_id')
        auth_token = get_auth_token(user_key) if user_key else None
        user_id = get_user_id(user_key) if user_key else None
        
        # Get user name for logging
        user_name = None
        if user_key:
            user = get_user(user_key)
            user_name = user.get('name') if user else None
        
        response = search_ride(origin, destination, auth_token=auth_token, user_id=user_id)
        
        if response is None:
            return jsonify({"error": "Search failed"}), 500
        
        # Log the search
        proposal_count = len(response.get('proposals', []))
        log_search(
            user_key=user_key or 'default',
            user_name=user_name,
            route_id=data.get('route_id'),
            origin=origin,
            destination=destination,
            proposal_count=proposal_count
        )
        
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/book', methods=['POST'])
def book():
    """Book a ride"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        prescheduled_ride_id = data.get('prescheduled_ride_id')
        proposal_uuid = data.get('proposal_uuid')
        origin = data.get('origin', config.default_origin)
        destination = data.get('destination', config.default_destination)
        
        if not prescheduled_ride_id or not proposal_uuid:
            return jsonify({"error": "Missing required fields"}), 400
        
        # Get user credentials if specified
        user_key = data.get('user_id')
        auth_token = get_auth_token(user_key) if user_key else None
        user_id = get_user_id(user_key) if user_key else None
        
        # Get user name for logging
        user_name = None
        if user_key:
            user = get_user(user_key)
            user_name = user.get('name') if user else None
        
        response = book_ride(prescheduled_ride_id, proposal_uuid, origin, destination, 
                            auth_token=auth_token, user_id=user_id)
        
        if response is None:
            # Log failed booking
            log_booking(
                action='book_failed',
                user_key=user_key or 'default',
                user_name=user_name,
                prescheduled_ride_id=prescheduled_ride_id,
                proposal_uuid=proposal_uuid,
                origin=origin,
                destination=destination
            )
            return jsonify({"error": "Booking failed"}), 500
        
        # Extract ride ID from response
        ride_id = None
        if isinstance(response, dict):
            rides = response.get('prescheduled_recurring_series_rides', [])
            if rides:
                ride_id = rides[0].get('id')
        
        # Log successful booking
        log_booking(
            action='book',
            user_key=user_key or 'default',
            user_name=user_name,
            prescheduled_ride_id=prescheduled_ride_id,
            proposal_uuid=proposal_uuid,
            ride_id=ride_id,
            origin=origin,
            destination=destination
        )
        
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/cancel', methods=['POST'])
def cancel():
    """Cancel a ride"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        ride_id = data.get('ride_id')
        if not ride_id:
            return jsonify({"error": "Missing ride_id"}), 400
        
        # Get user credentials if specified
        user_key = data.get('user_id')
        auth_token = get_auth_token(user_key) if user_key else None
        user_id = get_user_id(user_key) if user_key else None
        
        # Get user name for logging
        user_name = None
        if user_key:
            user = get_user(user_key)
            user_name = user.get('name') if user else None
        
        response = cancel_ride(ride_id, auth_token=auth_token, user_id=user_id)
        
        if response is None:
            # Log failed cancellation
            log_booking(
                action='cancel_failed',
                user_key=user_key or 'default',
                user_name=user_name,
                ride_id=ride_id
            )
            return jsonify({"error": "Cancellation failed"}), 500
        
        # Log successful cancellation
        log_booking(
            action='cancel',
            user_key=user_key or 'default',
            user_name=user_name,
            ride_id=ride_id
        )
        
        return jsonify(response)
    except Exception as e:
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
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        original_user = data.get('original_user')
        if not original_user:
            return jsonify({"error": "Missing original_user"}), 400
        
        if original_user not in USERS:
            return jsonify({"error": f"User '{original_user}' not found"}), 400
        
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
            """Callback function to send logs to the queue."""
            log_queue.put(('log', message))
        
        # Store orchestrator instance for emergency cleanup
        orchestrator_instance = {'orchestrator': None}
        
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
    
    Request body:
        - user_id: str, user key of the person whose booking to cancel
        - ride_id: int, the ride ID to cancel
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        user_key = data.get('user_id')
        ride_id = data.get('ride_id')
        
        if not user_key:
            return jsonify({"error": "Missing user_id"}), 400
        if not ride_id:
            return jsonify({"error": "Missing ride_id"}), 400
        
        if user_key not in USERS:
            return jsonify({"error": f"User '{user_key}' not found"}), 400
        
        # Cancel the ride
        auth_token = get_auth_token(user_key)
        user_id = get_user_id(user_key)
        
        response = cancel_ride(ride_id, auth_token=auth_token, user_id=user_id)
        
        if response:
            user_name = USERS[user_key]['name']
            return jsonify({
                "success": True,
                "message": f"Successfully cancelled {user_name}'s booking (ride ID: {ride_id})",
                "cancellation_response": response
            })
        else:
            return jsonify({
                "success": False,
                "message": f"Failed to cancel booking (ride ID: {ride_id})"
            }), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/lyft/check', methods=['POST'])
def check_lyft_availability():
    """
    Quick check if Lyft is available for a route (without booking anything).
    
    Request body:
        - user_id: str, user key to search as
        - route_id: str, route ID (optional)
        - origin/destination: custom locations (optional)
    """
    try:
        data = request.get_json() or {}
        
        user_key = data.get('user_id')
        auth_token = get_auth_token(user_key) if user_key else None
        user_id = get_user_id(user_key) if user_key else None
        
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

