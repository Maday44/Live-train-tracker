import requests
from datetime import datetime, timezone
from requests.exceptions import RequestException

"""
RTT train API
https://realtimetrains.github.io/api-specification/

Access tokens only last couple of minutes when no loger valid request another
"""

_token_cache = {
    "access_token": None,
    "valid_until": None
}


_headcode_cache = {}

# Map Network Rail Area IDs to key stations on those routes.
# The are maps for areas ids near my area and may pass by me
# CRS codes
AREA_LOCATIONS_MAP = {
    "Q6": ["GRY", "TIL", "SPO", "PIT", "UPM", "BKG", "OCK", "RNM", "LBG", "BEN", "LOS", "SOF", "SBY"],  # C2C & Thameside Freight
}


def get_valid_access_token(refresh_token):
# Access tokens dont last long
    now = datetime.now(timezone.utc)

    # Check if that token is still valid for more than 20 secs
    if _token_cache["access_token"] and _token_cache["valid_until"]:
        if (_token_cache["valid_until"] - now).total_seconds() > 20:
            return _token_cache["access_token"]

    url = "https://data.rtt.io/api/get_access_token"
    headers = {"Authorization": f"Bearer {refresh_token}"}

    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            _token_cache["access_token"] = data.get("token")
            valid_str = data.get("validUntil")
            if valid_str:
                _token_cache["valid_until"] = datetime.fromisoformat(valid_str)
            return _token_cache["access_token"]
        else:
            print(f"[RTT Auth Error] {res.status_code}: {res.text}", flush=True)
    except RequestException as e:
        print(f"[RTT Auth Exception] {e}", flush=True)

    return None


def fetch_rtt_service_by_headcode(headcode, location_code, date_str, refresh_token, area_id=None):
    """
    Finds a service using a headcode (e.g., '2D40', '4L19') by searching
    station schedules in the target area.
    """
    cache_key = f"{date_str}:{headcode}"
    
    # 1. Check cache first (returns dict or None if previously marked as unmatched)
    if cache_key in _headcode_cache:
        return _headcode_cache[cache_key]

    access_token = get_valid_access_token(refresh_token)
    if not access_token:
        return None

    found_locations = []

    # CRS location code 3 digits all caps with A-Z
    if location_code:
        found_locations.append(location_code.upper())
        
    # Append fallback area stations
    if area_id in AREA_LOCATIONS_MAP:
        for crs in AREA_LOCATIONS_MAP[area_id]:
            if crs not in found_locations:
                found_locations.append(crs)

    formatted_date = date_str.replace("/", "-")
    headers = {"Authorization": f"Bearer {access_token}"}

    # Loop until matched match
    for crs in found_locations:
        url = "https://data.rtt.io/gb-nr/location"
        params = {"location": crs, "date": formatted_date}

        try:
            res = requests.get(url, headers=headers, params=params, timeout=3)
            if res.status_code == 200:
                data = res.json()
                for service in data.get("services", []):
                    sched = service.get("scheduleMetadata", {})
                    
                    # Match on headcode OR matching operational train identity
                    if sched.get("trainReportingIdentity") == headcode:
                        origins = service.get("origin", [])
                        dests = service.get("destination", [])
                        orig_desc = origins[0].get("location", {}).get("description", "Unknown") if origins else "Unknown"
                        dest_desc = dests[0].get("location", {}).get("description", "Unknown") if dests else "Unknown"
                        
                        result = {
                            "rtt_service_uid": service.get("serviceUid") or sched.get("identity"),
                            "origin": orig_desc,
                            "destination": dest_desc
                        }
                        
                        # Cache the successful match
                        _headcode_cache[cache_key] = result
                        print(f"RTT FOUND - Headcode {headcode} at CRS:{crs} -> {result['rtt_service_uid']} ({orig_desc} -> {dest_desc})", flush=True)
                        return result
        except Exception as e:
            print(f"[RTT Error, CRS:{crs}] {e}", flush=True)

    # 2. KEY FIX: Cache None so failed lookups (like 2R26) aren't re-queried continuously
    _headcode_cache[cache_key] = None
    print(f"RTT NO MATCH - Headcode {headcode}", flush=True)
    return None

def fetch_rtt_service(identifier, date_str, refresh_token, location_code=None, area_id=None, is_uid=False):
    """
    identifier - uses the Headcode ('4L19') or Service UID ('G07989')
    date_str - dates are formatted as '2026-09-16' etc.
    refresh_token - is the RTT API key in secrets.json
    It to RTT roughly to then get short-lived access token, 
    which is then used for all train schedule queries.
    location_code - Optional station CRS (e.g. 'GRY')
    area_id: Signaling area ID like 'Q6'
    is_uid: True if identifier is already a Service UID
    """
    if not is_uid:
        return fetch_rtt_service_by_headcode(
            headcode=identifier,
            location_code=location_code,
            date_str=date_str,
            refresh_token=refresh_token,
            area_id=area_id
        )

    access_token = get_valid_access_token(refresh_token)
    if not access_token:
        return None

    formatted_date = date_str.replace("/", "-")
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    url = "https://data.rtt.io/gb-nr/service"
    params = {"service": identifier, "date": formatted_date}
    
    try:
        res = requests.get(url, headers=headers, params=params, timeout=3)
        if res.status_code == 200:
            data = res.json()
            origins = data.get("origin", [])
            dests = data.get("destination", [])
            return {
                "rtt_service_uid": data.get("serviceUid") or identifier,
                "origin": origins[0].get("location", {}).get("description", "Unknown"),
                "destination": dests[0].get("location", {}).get("description", "Unknown")
            }
    except RequestException as e:
        print(f"[RTT Error] {identifier}: {e}", flush=True)

    return None