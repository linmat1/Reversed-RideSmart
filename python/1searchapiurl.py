import requests
import json
import config

# API endpoint
url = "https://router-ucaca.live.ridewithvia.com/ops/rider/proposal/prescheduled/recurring/validate"

# JSON payload
payload = {
    "client_details": {
        "client_state": {
            "charging": config.charging,
            "client_ts": config.get_current_timestamp(),
            "battery_level": config.battery_level
        },
        "client_spec": {
            "device_model": "iPhone16,1",
            "app_id": "UniversityOfChicagoRider",
            "app_name": "RideSmart",
            "device_id": "2C33CDBD-5C95-4F2B-9393-C96A9F142A30",
            "client_os": 0,
            "device_name": "iPhone",
            "client_os_version": "26.3",
            "client_version": {
                "major_version": "4.22.9",
                "minor_version": "8"
            },
            "client_type": 0
        }
    },
    "whos_asking": {
        "auth_token": config.auth_token,
        "id": 3922267,
        "acct_type": 0
    },
    "prescheduled_recurring_series_id": 0,
    "sub_services": [
        "U_Chicago_Safe_Ride"
    ],
    "id": 0,
    "supported_features": [
        "MULTIPLE_PROPOSALS",
        "UNAVAILABLE_PROVIDERS",
        "PUBLIC_TRANSPORT",
        "PUBLIC_TRANSPORT_BUY_TICKET",
        "PREBOOKING_RIDE_SUPPLIER",
        "PREBOOKING_INTER_MODAL",
        "INTERMODAL_SECOND_LEG",
        "GENERIC_PROPOSALS",
        "NOW_LATER",
        "AUTONOMOUS_VEHICLE",
        "THIRD_PARTY",
        "RECURRING_INTERMODAL"
    ],
    "end_date_timestamp": config.get_current_timestamp(),
    "prescheduled_recurring_series_ride_details": {
        "display_time": []
    },
    "prescheduled_recurring_series_details": {
        "origin": {
            "latlng": {
                "lng": -87.5908127,
                "lat": 41.7878692
            },
            "full_geocoded_addr": "U-House",
            "geocoded_addr": "U-House"
        },
        "recurring_series_type": "OT",
        "plus_one_types": [
            {
                "is_item": False,
                "current_passengers_count": 1,
                "minimum_passengers_count": 1,
                "title": "Me",
                "id": 6261,
                "maximum_passengers_count": 1
            },
            {
                "is_item": False,
                "current_passengers_count": 0,
                "minimum_passengers_count": 0,
                "title": "Extra Rider",
                "id": 6263,
                "maximum_passengers_count": 1
            }
        ],
        "destination": {
            "latlng": {
                "lng": -87.6011258,
                "lat": 41.7851539
            },
            "full_geocoded_addr": "Not Cathey Dining Commons",
            "geocoded_addr": "NotCathey Dining Commons"
        },
        "n_passengers": 1
    },
    "mp_session_id": 6640750950572533545,
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
        
        # Filter out public transport proposals
        if "proposals" in response_json:
            original_count = len(response_json["proposals"])
            # Filter proposals: remove those with public_transport_info or type is multi_leg_public_transportation
            filtered_proposals = [
                proposal for proposal in response_json["proposals"]
                if "public_transport_info" not in proposal.get("ride_info", {})
                and proposal.get("type") != "multi_leg_public_transportation"
            ]
            response_json["proposals"] = filtered_proposals
            filtered_count = len(filtered_proposals)
            print(f"Filtered out {original_count - filtered_count} public transport proposal(s)")
            print(f"Remaining proposals: {filtered_count}\n")
        
        print("Response (pretty printed):")
        print(json.dumps(response_json, indent=2))
    except ValueError:
        # If response is not JSON, print as text
        print("Response (text):")
        print(response.text)
    
except requests.exceptions.RequestException as e:
    print(f"Error making request: {e}")

