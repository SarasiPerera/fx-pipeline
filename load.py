"""
Load step: get the previous rate for each pair (for anomaly detection),
then upsert the new batch into SQLite. Idempotent - re-running for the
same date/pair updates in place instead of creating duplicate rows,
so it's safe to re-run cron manually without corrupting history.
"""
import logging
import pandas as pd

from db import get_connection

logger = logging.getLogger("fx_pipeline.load")


def get_latest_rates(pairs: list) -> dict:
    """Returns {currency_pair: most_recent_rate} for the given pairs, from the DB."""
    conn = get_connection()
    try:
        result = {}
        for pair in pairs:
            row = conn.execute(
                "SELECT rate FROM fx_rates WHERE currency_pair = ? "
                "ORDER BY date DESC, loaded_at DESC LIMIT 1",
                (pair,),
            ).fetchone()
            if row:
                result[pair] = row[0]
        return result
    finally:
        conn.close()


def load_rates(df: pd.DataFrame) -> int:
    """
    Upserts each row of df into fx_rates. Returns number of rows written.
    Uses INSERT ... ON CONFLICT to stay idempotent on (date, currency_pair).
    """
    conn = get_connection()
    written = 0
    try:
        for _, row in df.iterrows():
            conn.execute(
                """
                INSERT INTO fx_rates (date, currency_pair, rate, source, loaded_at, pct_change, is_anomaly)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, currency_pair) DO UPDATE SET
                    rate = excluded.rate,
                    source = excluded.source,
                    loaded_at = excluded.loaded_at,
                    pct_change = excluded.pct_change,
                    is_anomaly = excluded.is_anomaly
                """,
                (
                    row["date"], row["currency_pair"], row["rate"],
                    row["source"], row["loaded_at"], row["pct_change"], row["is_anomaly"],
                ),
            )
            written += 1
        conn.commit()
        logger.info(f"Loaded {written} rows into fx_rates")
        return written
    finally:
        conn.close()
