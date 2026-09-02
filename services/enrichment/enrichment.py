"""
Enrichment service: polls `raw_events` for rows not yet processed, looks
up each headcode via the Realtime Trains (RTT) API for that date, and
writes a human-readable row to `passing_events`.

Runs as a simple polling loop rather than a queue consumer to start —
swap in Redis/Postgres LISTEN-NOTIFY later if polling latency matters.
"""

import os
import time
from datetime import datetime, timezone

import requests
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
RTT_USER = os.environ["RTT_API_USER"]
RTT_PASS = os.environ["RTT_API_PASS"]
POLL_INTERVAL_SECONDS = float(os.environ.get("ENRICH_POLL_INTERVAL", "5"))

RTT_BASE = "https://api.rtt.io/api/v1/json"


def get_db():
    return psycopg2.connect(DATABASE_URL)


def fetch_unprocessed(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, headcode, berth, direction, event_time
            FROM raw_events
            WHERE processed = false
            ORDER BY event_time ASC
            LIMIT 20
            """
        )
        return cur.fetchall()


def mark_processed(conn, event_id):
    with conn, conn.cursor() as cur:
        cur.execute("UPDATE raw_events SET processed = true WHERE id = %s", (event_id,))


def lookup_headcode(headcode, date):
    """
    RTT doesn't support a direct headcode search; in practice you'll query
    a known station near your berth for services around event_time and
    match by headcode. This is a placeholder using RTT's search-by-date
    endpoint structure — replace `NEARBY_STATION_CRS` with the CRS code of
    a station close to your target berth once you've picked one.
    """
    NEARBY_STATION_CRS = os.environ.get("NEARBY_STATION_CRS", "CHX")  # placeholder
    url = f"{RTT_BASE}/search/{NEARBY_STATION_CRS}/{date:%Y}/{date:%m}/{date:%d}"
    resp = requests.get(url, auth=(RTT_USER, RTT_PASS), timeout=10)
    resp.raise_for_status()
    data = resp.json()

    for service in data.get("services", []):
        if service.get("trainIdentity") == headcode:
            return {
                "destination": service["locationDetail"]["destination"][0]["description"],
                "origin": service["locationDetail"]["origin"][0]["description"],
                "operator": service.get("atocName"),
                "scheduled_time": service["locationDetail"].get("gbttBookedDeparture"),
                "estimated_time": service["locationDetail"].get("realtimeDeparture"),
                "delay_minutes": _delay_minutes(service["locationDetail"]),
            }
    return None


def _delay_minutes(location_detail):
    booked = location_detail.get("gbttBookedDeparture")
    actual = location_detail.get("realtimeDeparture")
    if not booked or not actual:
        return None
    fmt = "%H%M"
    delta = (
        datetime.strptime(actual, fmt) - datetime.strptime(booked, fmt)
    ).total_seconds() / 60
    return int(delta)


def insert_passing_event(conn, raw_event, details):
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO passing_events
                (headcode, berth, direction, event_time, origin, destination,
                 operator, scheduled_time, estimated_time, delay_minutes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                raw_event["headcode"],
                raw_event["berth"],
                raw_event["direction"],
                raw_event["event_time"],
                details["origin"] if details else None,
                details["destination"] if details else None,
                details["operator"] if details else None,
                details["scheduled_time"] if details else None,
                details["estimated_time"] if details else None,
                details["delay_minutes"] if details else None,
            ),
        )


def run_once(conn):
    for raw_event in fetch_unprocessed(conn):
        details = None
        try:
            details = lookup_headcode(raw_event["headcode"], datetime.now(timezone.utc))
        except requests.RequestException as e:
            print(f"[enrichment] RTT lookup failed for {raw_event['headcode']}: {e}")

        insert_passing_event(conn, raw_event, details)
        mark_processed(conn, raw_event["id"])
        print(f"[enrichment] processed {raw_event['headcode']} -> {details}")


if __name__ == "__main__":
    conn = get_db()
    print("[enrichment] starting poll loop")
    while True:
        run_once(conn)
        time.sleep(POLL_INTERVAL_SECONDS)
