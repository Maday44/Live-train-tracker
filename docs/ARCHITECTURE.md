# Architecture notes

## Data sources

### Network Rail Train Describer (TD) feed
- Push feed over STOMP (ActiveMQ), delivered as XML/JSON messages per topic
- Subscribe to a geographic area topic (e.g. `SEUS` for South East)
- Two message classes:
  - **C-class**: berth-to-berth "step" events — a train description (headcode)
    moves from one berth to another. This is what we filter on.
  - **S-class**: raw signalling state (signal aspects, points, track
    circuits) — not needed for this project, can be ignored/dropped
- A berth usually corresponds to a signal or short track section. There is
  no public, complete mapping from berth ID to lat/lon — you identify the
  berth(s) near your home empirically (see `scripts/identify_berth.py`)

### Realtime Trains (RTT) API
- Simple REST/JSON API, HTTP basic auth
- Given a headcode + date (or a station + time), returns the scheduled
  service: origin, destination, calling points, booked vs. actual/estimated
  times, delay
- Used by the enrichment service to turn a bare headcode from the TD feed
  into something human-readable

### Darwin (LDBWS/OpenLDBWS) — optional
- SOAP API (consider a JSON proxy like Huxley, or a typed client library,
  rather than hand-rolling SOAP calls)
- Only needed if you also want a "next departures from [local station]"
  view in the dashboard, independent of the TD-based passing alerts

## Why two separate services (ingest vs. enrichment) instead of one

- The TD feed connection is a persistent, stateful STOMP subscription that
  needs to stay alive and reconnect on drops — keep that concern isolated
- Enrichment involves an external HTTP API with its own rate limits and
  failure modes — isolating it means a slow/failed RTT lookup never risks
  dropping TD messages
- They can be scaled/restarted independently and the queue between them
  (even a simple DB table or Redis list) gives you a natural retry point

## Data flow detail

1. Ingest service holds a STOMP connection to the TD feed, subscribed to
   the relevant area topic.
2. On every C-class message, check if `from_berth` or `to_berth` matches
   your configured berth(s). If so, push `{headcode, timestamp, berth,
   direction}` onto a queue (Postgres table `raw_events` is fine to start).
3. Enrichment service polls/consumes `raw_events`, calls RTT with the
   headcode + date, and writes an enriched row to `passing_events`
   (destination, origin, scheduled time, delay minutes, operator).
4. API service exposes:
   - `GET /events/recent` — last N enriched passing events
   - `WS /events/live` — pushes new events as they're enriched
5. Alerting is just another consumer of `passing_events` (or the same
   WebSocket) that posts to a webhook (Pushover/ntfy/Telegram) — doesn't
   need its own polling loop if it subscribes to the same stream.

## Known rough edges

- **Headcode reuse**: the same headcode is reused by different physical
  trains on different days (and sometimes within a day). Always pass the
  *date* to RTT lookups, and treat headcode+date as the real key, not
  headcode alone.
- **TD feed noise**: occasional missed or duplicate steps happen. Don't
  promise sub-second accuracy in UI copy; dedupe on (headcode, berth,
  timestamp-within-a-few-seconds) if duplicates show up in practice.
- **Berth identification is manual**: there's no API that maps berth IDs
  to physical locations. Budget real time for this — it involves watching
  a real train and cross-referencing logs.
- **Terms of use**: both Network Rail Open Data and RTT have usage
  policies — check current terms before running anything publicly
  accessible (e.g. exposing the dashboard outside your home network).
