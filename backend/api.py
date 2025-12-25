"""
Flask API backend for RideSmart React frontend
Exposes Python functions as REST API endpoints
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
from src.search_ride import search_ride
from src.book_ride import book_ride
from src.cancel_ride import cancel_ride
from src import config
from src.destination_config import LOCATIONS, get_location_pair
import json

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

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
        
        response = search_ride(origin, destination)
        
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
        
        response = book_ride(prescheduled_ride_id, proposal_uuid, origin, destination)
        
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
        
        response = cancel_ride(ride_id)
        
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)

