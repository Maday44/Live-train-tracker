import requests


def fetch_rtt_service(headcode, date_str):

    url = f"https://api.realtimetrains.co.uk/v1/json/search/{headcode}/{date_str}"

    response = requests.get(url, auth=("", ""))
    if response.status_code == 200:
        data = response.json()
        services = data.get("services", [])

        for s in services:
            uid = s.get("serviceUid")
            origin = (
                s.get("locationDetail", {}).get("origin", [{}])[0].get("description")
            )
            destination = (
                s.get("locationDetail", {})
                .get("destination", [{}])[0]
                .get("description")
            )

            return {
                "rtt_service_uid": uid,
                "origin": origin,
                "destination": destination,
            }
    return None
