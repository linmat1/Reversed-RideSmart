import requests
import json
import config

def cancel_ride(ride_id):
    """
    Cancel a ride with the given ride ID.
    
    Args:
        ride_id: int, the ride ID to cancel
    
    Returns:
        Response JSON or None if error
    """
    # API endpoint
    url = "https://router-ucaca.live.ridewithvia.com/ops/rider/ride/cancel"
    
    # JSON payload
    payload = {
        "client_details": {
            "client_state": {
                "battery_level": config.battery_level,
                "charging": config.charging,
                "client_ts": config.get_current_timestamp()
            },
            "client_spec": {
                "client_type": 0,
                "device_id": "2C33CDBD-5C95-4F2B-9393-C96A9F142A30",
                "app_name": "RideSmart",
                "device_name": "iPhone",
                "app_id": "UniversityOfChicagoRider",
                "client_os": 0,
                "client_version": {
                    "major_version": "4.22.9",
                    "minor_version": "8"
                },
                "client_os_version": "26.3",
                "device_model": "iPhone16,1"
            }
        },
        "ride_id": ride_id,
        "whos_asking": {
            "auth_token": config.auth_token,
            "id": 3922267,
            "acct_type": 0
        },
        "mp_session_id": 8004176786723592206,
        "ride_supplier": 0,
        "sub_services": [
            "U_Chicago_Safe_Ride"
        ],
        "rider_service_flag": 0,
        "city_id": 783
    }
    
    # Headers
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Make POST request with JSON data
        response = requests.post(url, json=payload, headers=headers)
        
        # Check if request was successful
        response.raise_for_status()
        
        # Print response status and content
        print(f"Status Code: {response.status_code}\n")
        
        # Try to pretty print JSON response
        try:
            response_json = response.json()
            print("Response (pretty printed):")
            print(json.dumps(response_json, indent=2))
            return response_json
        except ValueError:
            # If response is not JSON, print as text
            print("Response (text):")
            print(response.text)
            return response.text
        
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return None

