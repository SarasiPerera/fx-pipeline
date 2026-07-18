"""
Transform step: turn the raw USD-based API payload into a clean,
validated DataFrame of {date, currency_pair, rate, source, loaded_at}
rows, with day-over-day % change and an anomaly flag vs the last
value already stored in the DB.
"""
import logging
from datetime import datetime, timezone

import pandas as pd

from config import TARGET_PAIRS, SOURCE_NAME, ANOMALY_THRESHOLD_PCT

logger = logging.getLogger("fx_pipeline.transform")


def _derive_pairs(raw_rates: dict) -> dict:
    """
    The API gives USD -> X rates. We want X/LKR pairs.
    USD/LKR is direct. GBP/LKR and EUR/LKR are cross rates:
        GBP/LKR = (LKR per USD) / (GBP per USD)
    """
    required = {"LKR", "GBP", "EUR"}
    missing = required - raw_rates.keys()
    if missing:
        raise ValueError(f"API response missing currencies: {missing}")

    lkr_per_usd = raw_rates["LKR"]
    gbp_per_usd = raw_rates["GBP"]
    eur_per_usd = raw_rates["EUR"]

    return {
        "USD/LKR": lkr_per_usd,
        "GBP/LKR": lkr_per_usd / gbp_per_usd,
        "EUR/LKR": lkr_per_usd / eur_per_usd,
    }


def clean_and_validate(payload: dict) -> pd.DataFrame:
    """
    Validates the raw API payload and returns a tidy DataFrame:
    columns = [date, currency_pair, rate, source, loaded_at]
    Rows with missing/non-numeric/non-positive rates are dropped (with a warning),
    rather than silently written to the DB.
    """
    raw_rates = payload.get("rates", {})
    pairs = _derive_pairs(raw_rates)

    # API gives an update date - use it as the effective 'date' for the row.
    # Fall back to today (UTC) if the field is missing/unparseable.
    date_str = payload.get("time_last_update_utc")
    try:
        effective_date = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z").date().isoformat()
    except (TypeError, ValueError):
        logger.warning("Could not parse 'time_last_update_utc'; falling back to today's UTC date")
        effective_date = datetime.now(timezone.utc).date().isoformat()

    loaded_at = datetime.now(timezone.utc).isoformat()

    rows = []
    for pair in TARGET_PAIRS:
        rate = pairs.get(pair)

        # --- validation ---
        if rate is None:
            logger.warning(f"Skipping {pair}: no rate returned")
            continue
        if not isinstance(rate, (int, float)) or rate != rate:  # NaN check
            logger.warning(f"Skipping {pair}: non-numeric rate ({rate})")
            continue
        if rate <= 0:
            logger.warning(f"Skipping {pair}: non-positive rate ({rate})")
            continue

        rows.append({
            "date": effective_date,
            "currency_pair": pair,
            "rate": round(float(rate), 4),
            "source": SOURCE_NAME,
            "loaded_at": loaded_at,
        })

    if not rows:
        raise ValueError("No valid rate rows survived validation - refusing to load an empty batch")

    return pd.DataFrame(rows)


def flag_anomalies(df: pd.DataFrame, previous_rates: dict) -> pd.DataFrame:
    """
    previous_rates: dict of {currency_pair: last_known_rate} pulled from the DB.
    Adds 'pct_change' and 'is_anomaly' columns.
    A row is an anomaly if it moves more than ANOMALY_THRESHOLD_PCT vs
    the previous day's stored rate for that pair.
    """
    df = df.copy()
    pct_changes = []
    anomaly_flags = []

    for _, row in df.iterrows():
        prev = previous_rates.get(row["currency_pair"])
        if prev is None or prev == 0:
            pct_changes.append(None)
            anomaly_flags.append(0)
            continue

        pct_change = ((row["rate"] - prev) / prev) * 100
        is_anomaly = 1 if abs(pct_change) > ANOMALY_THRESHOLD_PCT else 0

        if is_anomaly:
            logger.warning(
                f"Anomaly flagged: {row['currency_pair']} moved {pct_change:.2f}% "
                f"({prev} -> {row['rate']})"
            )

        pct_changes.append(round(pct_change, 4))
        anomaly_flags.append(is_anomaly)

    df["pct_change"] = pct_changes
    df["is_anomaly"] = anomaly_flags
    return df
