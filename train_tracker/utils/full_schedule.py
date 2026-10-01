import os
import requests
from datetime import datetime, timezone
from train_tracker.models import *

# Realtime Trains Credentials
RTT_USER = os.getenv("RTT_USER")
RTT_PASS = os.getenv("RTT_PASS")
RTT_BASE_URL = "https://api.rtt.io/json/search"

def fetch_and_save_tilbury_schedule(target_date=None):
    """
    Fetches the full day's schedule for Tilbury Town (TIL) from RTT API 
    and saves/updates database records.
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc)

    year = target_date.strftime("%Y")
    month = target_date.strftime("%m")
    day = target_date.strftime("%d")


    url = f"{RTT_BASE_URL}/TIL/{year}/{month}/{day}"
    
    response = requests.get(url, auth=(RTT_USER, RTT_PASS))
    if response.status_code != 200:
        print(f"Error fetching RTT data: {response.status_code}")
        return

    data = response.json()
    services = data.get("services", [])

    for service in services:
        location_detail = service.get("locationDetail", {})
 
        service_uid = service.get("serviceUid")
        headcode = service.get("trainIdentity", "0000")
        
        gbtt_booked = location_detail.get("gbttBookedDeparture") or location_detail.get("gbttBookedArrival")
        realtime_actual = location_detail.get("realtimeDeparture") or location_detail.get("realtimeArrival")
        
        is_cancelled = location_detail.get("displayAs") == "CANCELLED" or service.get("isCancelled", False)

        if not gbtt_booked:
            continue

        sched_hour, sched_min = int(gbtt_booked[:2]), int(gbtt_booked[2:])
        sched_dt = target_date.replace(hour=sched_hour, minute=sched_min, second=0, microsecond=0)


        delay_minutes = 0
        actual_dt = None


        if realtime_actual and not is_cancelled:
            act_hour, act_min = int(realtime_actual[:2]), int(realtime_actual[2:])
            actual_dt = target_date.replace(hour=act_hour, minute=act_min, second=0, microsecond=0)
            
            # Difference in minutes
            diff = int((actual_dt - sched_dt).total_seconds() / 60)
            delay_minutes = diff

            if diff > 0:
                status = f" - {diff}m)"
            elif diff < 0:
                status = f" + {abs(diff)}"
            else:
                status = "On Time"

        record = StationSchedule.query.filter_by(
            rtt_service_uid=service_uid,
            crs_code="TIL"
        ).first()

        if not record:
            record = StationSchedule(rtt_service_uid=service_uid, crs_code="TIL")
            db.session.add(record)

        record.headcode = headcode
        record.origin_station = location_detail.get("origin", [{}])[0].get("description")
        record.destination_station = location_detail.get("destination", [{}])[0].get("description")
        record.scheduled_time = sched_dt
        record.actual_time = actual_dt
        record.is_cancelled = is_cancelled
        record.status = "CANCELLED" if is_cancelled else status
        record.delay_minutes = delay_minutes
        record.msg_type = "SCHEDULE"

    db.session.commit()