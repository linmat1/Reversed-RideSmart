import requests
import json
try:
    from python import config
except ImportError:
    import config

# API endpoint
url = "https://router-ucaca.live.ridewithvia.com/ops/rider/proposal/prescheduled/recurring/book"

# Dynamic variables
prescheduled_ride_id = 438068778
proposal_uuid = "7ef08a13-f66d-498b-aaec-dfced43269c0"
ride_id = prescheduled_ride_id
auth_token = config.auth_token
origin = {
    "full_geocoded_addr": "I-House",
    "geocoded_addr": "I-House",
    "latlng": {
        "lng": -87.5908128,
        "lat": 41.7878692
    }
}
destination = {
    "latlng": {
        "lat": 41.7851539,
        "lng": -87.6011259
    },
    "geocoded_addr": "Cathey Dining Commons",
    "full_geocoded_addr": "Cathey Dining Commons"
}

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
        "id": 3922267,
        "acct_type": 0,
        "auth_token": auth_token
    },
    "city_id": 783,
    "prescheduled_recurring_series_details": {
        "origin": origin,
        "destination": destination,
        "recurring_series_type": "OT",
        "n_passengers": 2,
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
                "current_passengers_count": 1,
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
    
    # Check if request was successful
    response.raise_for_status()
    
    # Print response status and content
    print(f"Status Code: {response.status_code}\n")
    
    # Try to pretty print JSON response
    try:
        response_json = response.json()
        print("Response (pretty printed):")
        print(json.dumps(response_json, indent=2))
    except ValueError:
        # If response is not JSON, print as text
        print("Response (text):")
        print(response.text)
    
except requests.exceptions.RequestException as e:
    print(f"Error making request: {e}")

