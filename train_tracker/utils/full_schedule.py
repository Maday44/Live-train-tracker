import threading
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from flask import current_app

from train_tracker.models import db, StationSchedule

# Confirmed working domain from PowerShell trace
RTT_BASE = "https://data.rtt.io"
TOKEN_URL = f"{RTT_BASE}/api/get_access_token"
LOCATION_URL = f"{RTT_BASE}/gb-nr/location"

LONDON = ZoneInfo("Europe/London")

MAX_WINDOW_MINUTES = 1439
TOKEN_EXPIRY_MARGIN = timedelta(seconds=60)
MIN_FETCH_INTERVAL = 300

_token_lock = threading.Lock()
_token = {"value": None, "expires": None}
_blocked_until = 0.0
_last_fetch = {}


class RttError(Exception):
    pass


class RttRateLimited(RttError):
    def __init__(self, retry_after):
        super().__init__(f"Rate limited by RTT, retry in {retry_after}s")
        self.retry_after = retry_after


def _check_rate_limit(resp):
    global _blocked_until
    if resp.status_code == 429:
        try:
            retry_after = int(resp.headers.get("Retry-After", 60))
        except ValueError:
            retry_after = 60
        _blocked_until = time.time() + retry_after
        raise RttRateLimited(retry_after)


def _get_access_token(force=False):
    refresh_token = (
        current_app.config.get("RTT_REFRESH_TOKEN")
        or current_app.config.get("RTT_API_KEY")
        or current_app.config.get("RTT_API_TOKEN")
    )
    if not refresh_token:
        raise RttError("RTT_REFRESH_TOKEN is not configured in application settings.")

    with _token_lock:
        now = datetime.now(timezone.utc)
        if (
            not force
            and _token["value"]
            and _token["expires"]
            and _token["expires"] - TOKEN_EXPIRY_MARGIN > now
        ):
            return _token["value"]

        resp = requests.get(
            TOKEN_URL,
            headers={"Authorization": f"Bearer {refresh_token}"},
            timeout=10,
        )
        _check_rate_limit(resp)
        resp.raise_for_status()
        body = resp.json()

        _token["value"] = body["token"]
        _token["expires"] = datetime.fromisoformat(body["validUntil"])
        return _token["value"]


def _request_location(crs_code, start):
    params = {
        "code": crs_code,
        "timeFrom": start.isoformat(),
        "timeWindow": MAX_WINDOW_MINUTES,
    }

    def do_request(token):
        return requests.get(
            LOCATION_URL,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=15,
        )

    resp = do_request(_get_access_token())
    if resp.status_code == 401:
        resp = do_request(_get_access_token(force=True))

    _check_rate_limit(resp)
    resp.raise_for_status()
    return resp


def _parse_iso(value):
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LONDON)
    return dt.astimezone(timezone.utc)


def _first_description(entries):
    if entries:
        return entries[0].get("location", {}).get("description", "Unknown")
    return "Unknown"


def fetch_and_save_tilbury_schedule(
    target_date=None,
    crs_code="TIL",
    include_buses=True,
    force=False,
):
    if target_date is None:
        day = datetime.now(LONDON).date()
    elif isinstance(target_date, datetime):
        day = target_date.astimezone(LONDON).date() if target_date.tzinfo else target_date.date()
    elif isinstance(target_date, date):
        day = target_date
    else:
        raise TypeError("target_date must be a date or datetime")

    start = datetime(day.year, day.month, day.day, tzinfo=LONDON)

    now_ts = time.time()
    if now_ts < _blocked_until:
        wait = int(_blocked_until - now_ts)
        current_app.logger.warning(f"RTT rate limit active, skipping fetch for {wait}s")
        return False

    last = _last_fetch.get((crs_code, day))
    if not force and last and now_ts - last < MIN_FETCH_INTERVAL:
        current_app.logger.info(f"Skipping fetch for {crs_code} {day}: fetched recently")
        return True

    try:
        resp = _request_location(crs_code, start)
    except RttRateLimited as e:
        current_app.logger.warning(str(e))
        return False
    except (RttError, requests.RequestException) as e:
        current_app.logger.error(f"Failed to fetch data from RTT API: {e}")
        return False

    if resp.status_code == 204:
        _last_fetch[(crs_code, day)] = now_ts
        return True

    services = resp.json().get("services", [])
    if not services:
        _last_fetch[(crs_code, day)] = now_ts
        return True

    saved = 0
    for item in services:
        meta = item.get("scheduleMetadata", {})
        temporal = item.get("temporalData", {})

        if not include_buses and meta.get("modeType") != "TRAIN":
            continue

        call = temporal.get("departure") or temporal.get("arrival") or {}

        scheduled_dt = _parse_iso(call.get("scheduleAdvertised"))
        if scheduled_dt is None:
            continue

        actual_dt = _parse_iso(call.get("realtimeForecast"))
        is_cancelled = bool(call.get("isCancelled")) or temporal.get("displayAs") == "CANCELLED"

        delay_minutes = 0
        status = "ON TIME"

        if is_cancelled:
            status = "CANCELLED"
        elif actual_dt:
            diff_seconds = (actual_dt - scheduled_dt).total_seconds()
            delay_minutes = max(0, int(diff_seconds // 60))

            if delay_minutes > 0:
                status = f"LATE ({delay_minutes}m)"
            elif diff_seconds < -60:
                status = "EARLY"

        service_uid = meta.get("identity")

        record = StationSchedule.query.filter_by(
            rtt_service_uid=service_uid,
            scheduled_time=scheduled_dt,
        ).first()

        if not record:
            record = StationSchedule(
                rtt_service_uid=service_uid,
                crs_code=crs_code,
                scheduled_time=scheduled_dt,
            )
            db.session.add(record)

        record.headcode = meta.get("trainReportingIdentity") or service_uid or "TRAIN"
        record.origin_station = _first_description(item.get("origin"))
        record.destination_station = _first_description(item.get("destination"))
        record.actual_time = actual_dt
        record.delay_minutes = delay_minutes
        record.is_cancelled = is_cancelled
        record.status = status

        saved += 1

    db.session.commit()
    _last_fetch[(crs_code, day)] = now_ts
    current_app.logger.info(f"Saved {saved} services for {crs_code} on {day}")
    return True