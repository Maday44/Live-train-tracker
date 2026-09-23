import json
import requests
import time
from datetime import datetime, timezone


try:
    with open("secrets.json") as f:
        secrets = json.load(f)
        api_key = secrets["RTT_API_KEY"]
except Exception as e:
    print(f"Error loading secrets.json: {e}")
    exit(1)

REFRESH_TOKEN = api_key
TEST_HEADCODE = str(input("What headcode would you like to search for: ")).strip().upper()


TEST_CRS_LIST = [
    "PSE", "PIT", "BNF", "LOS", "SBY", "SOC", "CLK", "WCF", "SOE", "TPB",
    "SPO", "TIL", "GRY", "UPM", "BKG", "FNC", "LST", "SRA", "WHM", "LHS",
    "DDK", "RNM", "OCK", "CFH", "PFL", "ETL", "WHD", "LAI", "BSO",
    "TILBYJN", "GRYSJN", "PITSEAJN", "UPMNSTRJ", "BRKNGJN"
]


def get_access_token():
    print("Authenticating with RTT...")
    url = "https://data.rtt.io/api/get_access_token"
    headers = {"Authorization": f"Bearer {REFRESH_TOKEN}"}

    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            token = res.json().get("token")
            print("Authentication SUCCESS\n")
            return token
        else:
            print(f"Authentication FAILED (HTTP {res.status_code})")
            return None
    except Exception as e:
        print(f"Auth Exception: {e}")
        return None


def test_location_boards(token, headcode):
    print(f"=== Searching for Headcode: {headcode} ===")
    
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    for crs in TEST_CRS_LIST:
        url = "https://data.rtt.io/gb-nr/location"
        params = {
            "location": crs,
            "date": date_str,
            "time": time_str,
            "time_window": 120
        }

        # Pace requests to avoid HTTP 429 rate limits
        time.sleep(0.12)

        try:
            res = requests.get(url, headers=headers, params=params, timeout=4)

            # Auto-retry handling if rate limited
            if res.status_code == 429:
                print(f"Checking {crs:8}... [HTTP 429 Rate Limited] Pausing 2s...")
                time.sleep(2)
                res = requests.get(url, headers=headers, params=params, timeout=4)

            if res.status_code != 200:
                print(f"Checking {crs:8}... HTTP {res.status_code} Error")
                continue

            data = res.json()
            services = data.get("services", [])
            print(f"Checking {crs:8}... ({len(services)} services listed)")

            for s in services:
                sched = s.get("scheduleMetadata", {})
                identities = [
                    str(sched.get("trainReportingIdentity", "")).strip().upper(),
                    str(sched.get("identity", "")).strip().upper(),
                    str(s.get("trainIdentity", "")).strip().upper(),
                ]

                if headcode in identities:
                    origins = s.get("origin", [])
                    dests = s.get("destination", [])

                    orig_desc = origins[0].get("location", {}).get("description", "Unknown") if origins else "Unknown"
                    dest_desc = dests[0].get("location", {}).get("description", "Unknown") if dests else "Unknown"

                    print(f"\n==========================================")
                    print(f" MATCH FOUND AT LOCATION: {crs}")
                    print(f" Service UID : {s.get('serviceUid')}")
                    print(f" Route       : {orig_desc} -> {dest_desc}")
                    print(f" Matched Via : {identities}")
                    print(f"==========================================")
                    print("\nJSON Response Payload:")
                    print(json.dumps(s, indent=2))
                    return True

        except Exception as e:
            print(f"Checking {crs:8}... Exception: {e}")

    print(f"\nNO MATCH: Headcode '{headcode}' was not found across checked locations.")
    return False


if __name__ == "__main__":
    token = get_access_token()
    if token:
        test_location_boards(token, TEST_HEADCODE)

"""
JSON:
{
  "temporalData": {
    "arrival": {
      "scheduleInternal": "2026-09-23T21:17:00",
      "scheduleAdvertised": "2026-09-23T21:17:00",
      "realtimeForecast": "2026-09-23T21:19:00",
      "isCancelled": false
    },
    "departure": {
      "scheduleInternal": "2026-09-23T21:17:00",
      "scheduleAdvertised": "2026-09-23T21:17:00",
      "realtimeForecast": "2026-09-23T21:19:00",
      "isCancelled": false
    },
    "scheduledCallType": "ADVERTISED_OPEN",
    "realtimeCallType": "ADVERTISED_OPEN",
    "displayAs": "CALL",
    "isInterpolated": false
  },
  "locationMetadata": {
    "platform": {
      "planned": "1",
      "forecast": "1"
    },
    "numberOfVehicles": 8,
    "allocationIndex": 0
  },
  "scheduleMetadata": {
    "uniqueIdentity": "gb-nr:F51028:2026-09-23",
    "namespace": "gb-nr",
    "identity": "F51028",
    "departureDate": "2026-09-23",
    "operator": {
      "code": "CC",
      "name": "c2c"
    },
    "modeType": "TRAIN",
    "inPassengerService": true,
    "trainReportingIdentity": "2D79"
  },
  "origin": [
    {
      "location": {
        "description": "Southend Central",
        "longCodes": [
          "STHCENT"
        ]
      },
      "temporalData": {
        "scheduleInternal": "2026-09-23T20:35:00",
        "scheduleAdvertised": "2026-09-23T20:35:00"
      }
    }
  ],
  "destination": [
    {
      "location": {
        "description": "London Fenchurch Street",
        "longCodes": [
          "FENCHRS"
        ]
      },
      "temporalData": {
        "scheduleInternal": "2026-09-23T21:54:00",
        "scheduleAdvertised": "2026-09-23T21:54:00"
      }
    }
  ]
}
"""