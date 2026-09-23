import json
import requests
from datetime import datetime, timezone


with open("secrets.json") as f:
    secrets = json.load(f)
    api_key = secrets["RTT_API_KEY"]

REFRESH_TOKEN = api_key
TEST_HEADCODE = str(input("What headcode would you like to search for: ")).upper()
TEST_DATE = datetime.now().strftime("%Y-%m-%d")


TEST_CRS_LIST = ["GRY",
        "TIL",
        "SPO",
        "PIT",
        "UPM",
        "BKG",
        "OCK",
        "RNM",
        "LBG",
        "BEN",
        "LOS",
        "SOF",
        "SBY",]

def get_access_token():
    print("Authenticating with RTT")
    url = "https://data.rtt.io/api/get_access_token"
    headers = {"Authorization": f"Bearer {REFRESH_TOKEN}"}

    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            token = res.json().get("token")
            print(f"success")
            return token
        else:
            print(f"oh no failed")
            return None
    except Exception as e:
        print(f"{e}")
        return None


def test_location_boards(token, headcode, date_str):
    print(f"Looking for Headcode: {headcode}")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    clean_target = headcode.strip().upper()
    found_any = False

    for crs in TEST_CRS_LIST:
        url = "https://data.rtt.io/gb-nr/location"
        params = {"location": crs, "date": date_str}

        print(f"Checking Station CRS: {crs}...", end=" ")
        try:
            res = requests.get(url, headers=headers, params=params, timeout=4)
            if res.status_code != 200:
                print(f"HTTP {res.status_code} Error")
                continue

            data = res.json()
            services = data.get("services", [])
            print(f"({len(services)} services listed)")

            for s in services:
                sched = s.get("scheduleMetadata", {})
                identities = [
                    str(sched.get("trainReportingIdentity", "")).strip().upper(),
                    str(sched.get("identity", "")).strip().upper(),
                    str(s.get("trainIdentity", "")).strip().upper(),
                ]

                if clean_target in identities:
                    found_any = True
                    origins = s.get("origin", [])
                    dests = s.get("destination", [])

                    orig_desc = origins[0].get("location", {}).get("description", "Unknown") if origins else "Unknown"
                    dest_desc = dests[0].get("location", {}).get("description", "Unknown") if dests else "Unknown"

                    print(f"\n >>> MATCH FOUND AT {crs}! <<<")
                    print(f" Service UID : {s.get('serviceUid')}")
                    print(f" Route       : {orig_desc} -> {dest_desc}")
                    print(f" Matched Via : {identities}")
                    print("\nJSON:")
                    print(json.dumps(s, indent=2))
                    return True

        except Exception as e:
            print(f"Error: {e}")

    if not found_any:
        print(f"\nNO MATCH !!!! '{headcode}' was not found.")
        return False


if __name__ == "__main__":
    token = get_access_token()
    if token:
        test_location_boards(token, TEST_HEADCODE, TEST_DATE)