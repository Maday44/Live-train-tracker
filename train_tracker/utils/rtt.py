import time
import requests
from datetime import datetime, timezone
from requests.exceptions import RequestException

"""
RTT Train API Handler
https://realtimetrains.github.io/api-specification/
"""

_token_cache = {"access_token": None, "valid_until": None}
_headcode_cache = {}

AREA_LOCATIONS_MAP = {
    "Q6": [
        "PSE",
        "PIT",
        "BNF",
        "LOS",
        "SBY",
        "SOC",
        "CLK",
        "WCF",
        "SOE",
        "TPB",
        "SPO",
        "TIL",
        "GRY",
        "UPM",
        "BKG",
        "FNC",
        "LST",
        "SRA",
        "WHM",
        "LHS",
        "DDK",
        "RNM",
        "OCK",
        "CFH",
        "PFL",
        "ETL",
        "WHD",
        "LAI",
        "BSO",
        "TILBYJN",
        "GRYSJN",
        "PITSEAJN",
        "UPMNSTRJ",
        "BRKNGJN",
    ]
}


def get_valid_access_token(refresh_token):
    now = datetime.now(timezone.utc)

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


def fetch_rtt_service_by_headcode(
    headcode, location_code, date_str, refresh_token, area_id=None
):
    clean_headcode = headcode.strip().upper()
    cache_key = f"{date_str}:{clean_headcode}"

    if cache_key in _headcode_cache and _headcode_cache[cache_key] is not None:
        return _headcode_cache[cache_key]

    access_token = get_valid_access_token(refresh_token)

    if access_token:
        formatted_date = date_str.replace("/", "-")
        headers = {"Authorization": f"Bearer {access_token}"}

        found_locations = []
        if location_code:
            found_locations.append(location_code.upper())

        if area_id in AREA_LOCATIONS_MAP:
            for crs in AREA_LOCATIONS_MAP[area_id]:
                if crs not in found_locations:
                    found_locations.append(crs)

        now = datetime.now(timezone.utc)
        time_str = now.strftime("%H%M")

        for crs in found_locations:
            url = "https://data.rtt.io/gb-nr/location"
            params = {
                "location": crs,
                "date": formatted_date,
                "time": time_str,
                "time_window": 120,
            }

            time.sleep(0.20)

            try:
                res = requests.get(url, headers=headers, params=params, timeout=3)

                # Auto-retry handling if rate limited
                if res.status_code == 429:
                    time.sleep(2.1)
                    res = requests.get(url, headers=headers, params=params, timeout=3)

                if res.status_code == 200:
                    data = res.json()
                    for service in data.get("services", []):
                        sched = service.get("scheduleMetadata", {})

                        identities = [
                            str(sched.get("trainReportingIdentity", ""))
                            .strip()
                            .upper(),
                            str(sched.get("identity", "")).strip().upper(),
                            str(service.get("trainIdentity", "")).strip().upper(),
                        ]

                        if clean_headcode in identities:
                            origins = service.get("origin", [])
                            dests = service.get("destination", [])

                            orig_desc = (
                                origins[0]
                                .get("location", {})
                                .get("description", "Unknown")
                                if origins
                                else "Unknown"
                            )
                            dest_desc = (
                                dests[0]
                                .get("location", {})
                                .get("description", "Unknown")
                                if dests
                                else "Unknown"
                            )

                            # Handle null serviceUid by falling back to schedule identity
                            service_uid = (
                                service.get("serviceUid")
                                or sched.get("identity")
                                or sched.get("uniqueIdentity")
                            )

                            result = {
                                "rtt_service_uid": service_uid,
                                "origin": orig_desc,
                                "destination": dest_desc,
                            }

                            _headcode_cache[cache_key] = result
                            print(
                                f"RTT FOUND - Headcode {clean_headcode} at CRS:{crs} -> {service_uid} ({orig_desc} -> {dest_desc})",
                                flush=True,
                            )
                            return result
            except Exception as e:
                print(f"[RTT Error, CRS:{crs}] {e}", flush=True)

    print(f"RTT NO MATCH - Headcode {clean_headcode}", flush=True)
    return None


def fetch_rtt_service(
    identifier, date_str, refresh_token, location_code=None, area_id=None, is_uid=False
):
    if not is_uid:
        return fetch_rtt_service_by_headcode(
            headcode=identifier,
            location_code=location_code,
            date_str=date_str,
            refresh_token=refresh_token,
            area_id=area_id,
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
                "origin": (
                    origins[0].get("location", {}).get("description", "Unknown")
                    if origins
                    else "Unknown"
                ),
                "destination": (
                    dests[0].get("location", {}).get("description", "Unknown")
                    if dests
                    else "Unknown"
                ),
            }
    except RequestException as e:
        print(f"[RTT Error] {identifier}: {e}", flush=True)

    return None
