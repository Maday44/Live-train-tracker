import os
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ["DATABASE_URL"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_events (
    id SERIAL PRIMARY KEY,
    headcode TEXT NOT NULL,
    berth TEXT NOT NULL,
    direction TEXT NOT NULL,
    event_time TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    processed BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS passing_events (
    id SERIAL PRIMARY KEY,
    headcode TEXT NOT NULL,
    berth TEXT NOT NULL,
    direction TEXT NOT NULL,
    event_time TEXT NOT NULL,
    origin TEXT,
    destination TEXT,
    operator TEXT,
    scheduled_time TEXT,
    estimated_time TEXT,
    delay_minutes INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def get_db():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_db()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(SCHEMA)
    finally:
        conn.close()


def fetch_recent_events(limit=50):
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM passing_events ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            return cur.fetchall()
    finally:
        conn.close()
