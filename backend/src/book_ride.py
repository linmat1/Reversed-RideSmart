import requests
import json
try:
    from src import config
except ImportError:
    import config

def book_ride(prescheduled_ride_id, proposal_uuid, origin, destination, auth_token=None, user_id=None):
    """
    Book a ride with the given proposal UUID and ride ID.
    
    Args:
        prescheduled_ride_id: int, the ride ID to book
        proposal_uuid: str, the UUID of the proposal to book
        origin: dict with keys 'latlng', 'geocoded_addr', 'full_geocoded_addr'
        destination: dict with keys 'latlng', 'geocoded_addr', 'full_geocoded_addr'
        auth_token: str, authentication token. If None, uses default from config
        user_id: int, user ID. If None, uses default from config
    
    Returns:
        Response JSON or None if error
    """
    # Use defaults from config if not provided
    if auth_token is None:
        auth_token = config.auth_token
    if user_id is None:
        user_id = config.user_id
        
    # API endpoint
    url = "https://router-ucaca.live.ridewithvia.com/ops/rider/proposal/prescheduled/recurring/book"
    
    ride_id = prescheduled_ride_id
    
    # JSON payload
    payload = {
        "client_details": {
            "client_spec": {
                "client_version": {
                    "major_version": "4.22.9",
                    "minor_version": "8"
                },
                "client_os_version": "26.3",
                "client_os": 0,
                "client_type": 0,
                "app_name": "RideSmart",
                "device_name": "iPhone",
                "device_model": "iPhone16,1",
                "device_id": "2C33CDBD-5C95-4F2B-9393-C96A9F142A30",
                "app_id": "UniversityOfChicagoRider"
            },
            "client_state": {
                "battery_level": config.battery_level,
                "charging": config.charging,
                "client_ts": config.get_current_timestamp()
            }
        },
        "sub_services": [
            "U_Chicago_Safe_Ride"
        ],
        "rider_service_flag": 0,
        "whos_asking": {
            "id": user_id,
            "acct_type": 0,
            "auth_token": auth_token
        },
        "city_id": 783,
        "prescheduled_recurring_series_details": {
            "origin": origin,
            "destination": destination,
            "recurring_series_type": "OT",
            "n_passengers": config.n_passengers,
            "plus_one_types": [
                {
                    "id": 6261,
                    "maximum_passengers_count": 1,
                    "minimum_passengers_count": 1,
                    "current_passengers_count": 1,
                    "title": "Me",
                    "is_item": False
                },
                {
                    "id": 6263,
                    "maximum_passengers_count": 1,
                    "minimum_passengers_count": 0,
                    "title": "Extra Rider",
                    "current_passengers_count": 1 if config.include_extra_rider else 0,
                    "is_item": False
                }
            ]
        },
        "prescheduled_recurring_series_ride_details": {
            "display_time": []
        },
        "id": ride_id,
        "prescheduled_ride_id": prescheduled_ride_id,
        "prescheduled_recurring_series_id": 0,
        "mp_session_id": 8880627820818019707,
        "proposal_uuid": proposal_uuid,
        "end_date_timestamp": config.get_current_timestamp(),
        "supported_features": [
            "INTERMODAL_SECOND_LEG",
            "RECURRING_INTERMODAL"
        ]
    }
    
    # Headers
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Make POST request with JSON data
        response = requests.post(url, json=payload, headers=headers)
        
        # Print response status and content
        print(f"Status Code: {response.status_code}\n")
        
        # Try to parse JSON response
        try:
            response_json = response.json()
            print("Response (pretty printed):")
            print(json.dumps(response_json, indent=2))
            
            # Check if request was successful
            if response.status_code == 200:
                return response_json
            else:
                # Return error information
                error_message = response_json.get('message') or response_json.get('error') or f"HTTP {response.status_code}"
                return {
                    'success': False,
                    'error': error_message,
                    'status_code': response.status_code,
                    'response': response_json
                }
        except ValueError:
            # If response is not JSON, check status code
            if response.status_code == 200:
                print("Response (text):")
                print(response.text)
                return response.text
            else:
                error_message = response.text or f"HTTP {response.status_code}"
                return {
                    'success': False,
                    'error': error_message,
                    'status_code': response.status_code,
                    'response': response.text
                }
        
    except requests.exceptions.HTTPError as e:
        # HTTP error (4xx, 5xx)
        error_info = {
            'success': False,
            'error': str(e),
            'status_code': e.response.status_code if e.response else None
        }
        try:
            if e.response:
                error_info['response'] = e.response.json()
                error_info['error'] = e.response.json().get('message') or e.response.json().get('error') or str(e)
        except:
            if e.response:
                error_info['response'] = e.response.text
        print(f"HTTP Error making request: {error_info}")
        return error_info
    except requests.exceptions.RequestException as e:
        # Network or other request error
        error_info = {
            'success': False,
            'error': str(e),
            'status_code': None
        }
        print(f"Error making request: {error_info}")
        return error_info

