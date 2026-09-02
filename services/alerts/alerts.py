"""
Phase 3 — alerting. Deliberately dumb: polls the API service's REST
endpoint (rather than the DB directly) so it stays a pure consumer, same
as the future physical display will be.

Point ALERT_WEBHOOK_URL at whichever service you prefer:
  - ntfy.sh:   https://ntfy.sh/<your-topic>            (POST plain text)
  - Pushover:  https://api.pushover.net/1/messages.json (POST form data)
  - Telegram:  https://api.telegram.org/bot<token>/sendMessage
Adjust `send_alert` below to match the payload shape your chosen service expects.
"""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.environ.get("API_BASE", "http://api:8000")
WEBHOOK_URL = os.environ["ALERT_WEBHOOK_URL"]
POLL_INTERVAL_SECONDS = float(os.environ.get("ALERT_POLL_INTERVAL", "5"))

seen_ids = set()


def send_alert(event):
    delay = event.get("delay_minutes")
    delay_str = f", {delay} min late" if delay and delay > 0 else ", on time"
    message = f"Train passed: {event.get('headcode', '?')} to {event.get('destination', 'unknown')}{delay_str}"

    # Default: plain-text POST body, works as-is for ntfy.sh.
    # Swap this for Pushover/Telegram's expected payload shape if needed.
    try:
        requests.post(WEBHOOK_URL, data=message.encode(), timeout=5)
        print(f"[alerts] sent: {message}")
    except requests.RequestException as e:
        print(f"[alerts] failed to send alert: {e}")


def poll():
    resp = requests.get(f"{API_BASE}/events/recent", params={"limit": 10}, timeout=10)
    resp.raise_for_status()
    for event in resp.json():
        if event["id"] not in seen_ids:
            seen_ids.add(event["id"])
            send_alert(event)


if __name__ == "__main__":
    print("[alerts] starting poll loop")
    # Prime seen_ids on startup so we don't re-alert on old events.
    try:
        resp = requests.get(f"{API_BASE}/events/recent", params={"limit": 50}, timeout=10)
        for event in resp.json():
            seen_ids.add(event["id"])
    except requests.RequestException:
        pass

    while True:
        try:
            poll()
        except requests.RequestException as e:
            print(f"[alerts] poll failed: {e}")
        time.sleep(POLL_INTERVAL_SECONDS)
