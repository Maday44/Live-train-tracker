import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

# Read DATABASE_URL from .env or default to sqlite

RAW_DB_URL = os.getenv("DATABASE_URL", "")
IS_SQLITE = RAW_DB_URL.startswith("sqlite") or not RAW_DB_URL
SQLITE_FILE = "trainwatch.db"

if IS_SQLITE:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS raw_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        headcode TEXT NOT NULL,
        berth TEXT NOT NULL,
        direction TEXT NOT NULL,
        event_time TEXT NOT NULL,
        received_at TEXT NOT NULL,
        processed BOOLEAN NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS passing_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
else:
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
        created_at TIMESTAMPTZ DEFAULT now()
    );
    """


def get_db():
    if IS_SQLITE:
        conn = sqlite3.connect(SQLITE_FILE)
        conn.row_factory = sqlite3.Row
        return conn
    else:
        import psycopg2

        return psycopg2.connect(RAW_DB_URL)


def init_db():
    conn = get_db()
    try:
        if IS_SQLITE:
            with conn:
                conn.executescript(SCHEMA)
            print("✓ Local SQLite database initialized (trainwatch.db)")
        else:
            with conn, conn.cursor() as cur:
                cur.execute(SCHEMA)
            print("✓ PostgreSQL database initialized successfully")
    finally:
        conn.close()


def fetch_recent_events(limit=50):
    conn = get_db()
    try:
        if IS_SQLITE:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM passing_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
        else:
            import psycopg2.extras

            with conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cur:
                cur.execute(
                    "SELECT * FROM passing_events ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                return cur.fetchall()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()