import os
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from db import get_db, IS_SQLITE

load_dotenv()

RTT_USER = os.environ.get("RTT_API_USER", "")
RTT_PASS = os.environ.get("RTT_API_PASS", "")
NEARBY_STATION_CRS = os.environ.get("NEARBY_STATION_CRS", "TIL")
POLL_INTERVAL_SECONDS = float(os.environ.get("ENRICH_POLL_INTERVAL", "5"))

RTT_BASE = "https://api.rtt.io/api/v1/json"


def fetch_unprocessed(conn):
    if IS_SQLITE:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, headcode, berth, direction, event_time
            FROM raw_events
            WHERE processed = 0
            ORDER BY event_time ASC
            LIMIT 20
            """
        )
        return [dict(row) for row in cur.fetchall()]
    else:
        import psycopg2.extras
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
    if IS_SQLITE:
        with conn:
            conn.execute("UPDATE raw_events SET processed = 1 WHERE id = ?", (event_id,))
    else:
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE raw_events SET processed = true WHERE id = %s", (event_id,))


def lookup_headcode(headcode, date):
    if not RTT_USER or not RTT_PASS:
        return None

    url = f"{RTT_BASE}/search/{NEARBY_STATION_CRS}/{date:%Y}/{date:%m}/{date:%d}"
    resp = requests.get(url, auth=(RTT_USER, RTT_PASS), timeout=10)
    resp.raise_for_status()
    data = resp.json()

    for service in data.get("services", []):
        if service.get("trainIdentity") == headcode:
            loc = service.get("locationDetail", {})
            origins = loc.get("origin", [{}])
            dests = loc.get("destination", [{}])
            return {
                "origin": origins[0].get("description") if origins else None,
                "destination": dests[0].get("description") if dests else None,
                "operator": service.get("atocName"),
                "scheduled_time": loc.get("gbttBookedDeparture") or loc.get("gbttBookedArrival"),
                "estimated_time": loc.get("realtimeDeparture") or loc.get("realtimeArrival"),
                "delay_minutes": _delay_minutes(loc),
            }
    return None


def _delay_minutes(location_detail):
    booked = location_detail.get("gbttBookedDeparture") or location_detail.get("gbttBookedArrival")
    actual = location_detail.get("realtimeDeparture") or location_detail.get("realtimeArrival")
    if not booked or not actual:
        return None
    try:
        fmt = "%H%M"
        delta = (
            datetime.strptime(actual, fmt) - datetime.strptime(booked, fmt)
        ).total_seconds() / 60
        return int(delta)
    except Exception:
        return None


def insert_passing_event(conn, raw_event, details):
    params = (
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
    )

    if IS_SQLITE:
        with conn:
            conn.execute(
                """
                INSERT INTO passing_events
                    (headcode, berth, direction, event_time, origin, destination,
                     operator, scheduled_time, estimated_time, delay_minutes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
    else:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO passing_events
                    (headcode, berth, direction, event_time, origin, destination,
                     operator, scheduled_time, estimated_time, delay_minutes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                params,
            )


def run_once():
    conn = get_db()
    try:
        unprocessed = fetch_unprocessed(conn)
        for raw_event in unprocessed:
            details = None
            try:
                details = lookup_headcode(raw_event["headcode"], datetime.now(timezone.utc))
            except requests.RequestException as e:
                print(f"[enrichment] RTT lookup failed for {raw_event['headcode']}: {e}")

            insert_passing_event(conn, raw_event, details)
            mark_processed(conn, raw_event["id"])
            print(f"[enrichment] processed {raw_event['headcode']} -> {details}")
    finally:
        conn.close()


if __name__ == "__main__":
    print("[enrichment] starting poll loop")
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[enrichment] error encountered: {e}")
        time.sleep(POLL_INTERVAL_SECONDS)