# trainwatch

Live UK train tracking that alerts when a train passes near a specific
point on the track (not just a station), enriches it with schedule/delay
info, and serves it to a web dashboard — with a physical display planned
as a later client of the same backend.

## Why this isn't just "hit the National Rail API"

Station departure-board APIs (Darwin/LDBWS) tell you when a train is due
at a *station*. They don't tell you when a train passes a point *between*
stations. To detect "a train just passed my house" you need track-level
signalling data — Network Rail's **Train Describer (TD)** feed, which
reports trains stepping between signalling "berths" in near real time.

This project pairs that feed with a schedule API to turn a raw, cryptic
berth event into "12:47 to Charing Cross, running 4 min late."

## Architecture

```
Network Rail TD feed (STOMP)
        │  raw berth step events
        ▼
   ingest service  ──filters to your berth(s)──┐
                                                │ headcode + timestamp
                                                ▼
                                      enrichment service
                                      (looks up headcode via
                                       Realtime Trains / Darwin)
                                                │ enriched event
                                                ▼
                                          Postgres/SQLite
                                                │
                                    ┌───────────┴───────────┐
                                    ▼                       ▼
                              alerts (webhook)         api service
                              (Pushover/ntfy/          (REST + WebSocket)
                               Telegram)                       │
                                                                ▼
                                                     web dashboard /
                                                     future physical display
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design
notes and rationale.

## Status: Phase 1 — identifying your berth

Before any service is useful, you need to know which TD berth(s)
correspond to the track near your home. See
[`scripts/identify_berth.py`](scripts/identify_berth.py) — connect it to
your area's TD feed, watch a real train go past, and correlate the
timestamp against logged berth steps.

## Build phases

- [ ] **Phase 1** — identify your berth(s) (`scripts/identify_berth.py`)
- [ ] **Phase 2** — ingest + enrichment services, writing to DB
- [ ] **Phase 3** — alerting (webhook to Pushover/ntfy/Telegram)
- [ ] **Phase 4** — web dashboard (`services/api` + `web/`)
- [ ] **Phase 5** — physical display client (Pi/ESP32, polls the same API)

## Prerequisites

- A free account at [Network Rail Data Feeds](https://datafeeds.networkrail.co.uk/ntrod/) — gives you TD (and Train Movements) feed access
- A free API key from [Realtime Trains](https://www.realtimetrains.co.uk/about/developer/) — used to resolve headcodes into schedule/delay info
- Docker + Docker Compose (recommended), or Python 3.11+ if running services directly
- Postgres (or SQLite for local dev — see `services/api/db.py`)

## Setup

```bash
cp .env.example .env
# fill in NR_FEED_USERNAME, NR_FEED_PASSWORD, RTT_API_USER, RTT_API_PASS, TD_AREA_CODE

docker compose up --build
```

## Repo layout

```
services/
  ingest/       long-running STOMP client, filters TD feed to your berth(s)
  enrichment/   resolves headcode -> destination/delay via RTT API
  api/          FastAPI REST + WebSocket backend, serves the dashboard
web/            minimal dashboard frontend (vanilla JS, no build step)
scripts/        one-off tools, incl. the berth-identification helper
docs/           architecture notes
```

## License

MIT — see [`LICENSE`](LICENSE).
