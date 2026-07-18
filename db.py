"""
SQLite schema + connection helper.
Swap this file out (or point DB_PATH at a Postgres DSN with a different
driver) if you later "upgrade to Postgres" per the project brief -
everything else talks to the DB only through get_connection()/init_db().
"""
import sqlite3
import os
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS fx_rates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,          -- YYYY-MM-DD, the rate's effective date
    currency_pair   TEXT NOT NULL,          -- e.g. 'USD/LKR'
    rate            REAL NOT NULL,
    source          TEXT NOT NULL,
    loaded_at       TEXT NOT NULL,          -- ISO timestamp when the row was written
    pct_change      REAL,                   -- % change vs previous stored rate for this pair
    is_anomaly      INTEGER NOT NULL DEFAULT 0,  -- 1 if |pct_change| > threshold
    UNIQUE(date, currency_pair)             -- idempotent: re-running same-day load won't duplicate
);

CREATE INDEX IF NOT EXISTS idx_fx_rates_pair_date ON fx_rates(currency_pair, date);
"""


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
