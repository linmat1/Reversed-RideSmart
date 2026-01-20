import requests
import json
try:
    from src import config
except ImportError:
    import config

def get_route(route_identifier):
    """
    Get the route details for a booked ride.
    
    Args:
        route_identifier: str, the route identifier from the booking response
    
    Returns:
        Response JSON with route coordinates and stops, or None if error
    """
    url = "https://router-ucaca.live.ridewithvia.com/ops/rider/route/get"
    
    payload = {
        "client_details": {
            "client_state": {
                "charging": config.charging,
                "battery_level": config.battery_level,
                "client_ts": config.get_current_timestamp()
            },
            "client_spec": {
                "device_name": "iPhone",
                "app_id": "UniversityOfChicagoRider",
                "app_name": "RideSmart",
                "client_version": {
                    "minor_version": "8",
                    "major_version": "4.22.9"
                },
                "client_os": 0,
                "client_type": 0,
                "device_id": "2C33CDBD-5C95-4F2B-9393-C96A9F142A30",
                "client_os_version": "26.3",
                "device_model": "iPhone16,1"
            }
        },
        "rider_service_flag": 0,
        "city_id": 783,
        "route_identifier": route_identifier,
        "mp_session_id": 5075534297536894314,
        "sub_services": [
            "U_Chicago_Safe_Ride"
        ],
        "whos_asking": {
            "acct_type": 0,
            "auth_token": config.auth_token,
            "id": 3922267
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        print(f"Get Route Status Code: {response.status_code}")
        
        try:
            response_json = response.json()
            print("Route Response (pretty printed):")
            print(json.dumps(response_json, indent=2))
            return response_json
        except ValueError:
            print("Response (text):")
            print(response.text)
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error getting route: {e}")
        return None
