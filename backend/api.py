"""
Flask API backend for RideSmart React frontend
Exposes Python functions as REST API endpoints
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
from src.search_ride import search_ride
from src.book_ride import book_ride
from src.cancel_ride import cancel_ride
from src.get_route import get_route
from src import config
from src.destination_config import LOCATIONS, get_location_pair
from src.users import list_users, get_user, get_auth_token, get_user_id, USERS
from src.lyft_orchestrator import LyftOrchestrator
import json

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
        
        response = search_ride(origin, destination, auth_token=auth_token, user_id=user_id)
        
        if response is None:
            return jsonify({"error": "Search failed"}), 500
        
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
        
        response = book_ride(prescheduled_ride_id, proposal_uuid, origin, destination, 
                            auth_token=auth_token, user_id=user_id)
        
        if response is None:
            return jsonify({"error": "Booking failed"}), 500
        
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
        
        response = cancel_ride(ride_id, auth_token=auth_token, user_id=user_id)
        
        if response is None:
            return jsonify({"error": "Cancellation failed"}), 500
        
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
    Run the Lyft orchestrator to get a free Lyft ride.
    
    Request body:
        - original_user: str, user key of person who wants the Lyft
        - route_id: str, route ID from destination_config (optional)
        - origin: dict, custom origin (optional, used if route_id not provided)
        - destination: dict, custom destination (optional)
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
        
        # Run the orchestrator
        orchestrator = LyftOrchestrator(original_user, origin, destination)
        result = orchestrator.run()
        
        return jsonify({
            "success": result['success'],
            "message": result['message'],
            "lyft_booking": result['lyft_booking'],
            "log": orchestrator.log
        })
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

