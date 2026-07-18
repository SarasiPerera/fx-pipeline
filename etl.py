"""
Main entry point for the pipeline. This is the script cron calls daily.

Usage:
    python3 etl.py

Exit code 0 = success, 1 = failure (so cron/monitoring can detect failures).
"""
import logging
import sys
from logging.handlers import RotatingFileHandler

from config import LOG_PATH, LOG_DIR, TARGET_PAIRS
import os

from db import init_db
from extract import fetch_rates, ExtractError
from transform import clean_and_validate, flag_anomalies
from load import get_latest_rates, load_rates


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("fx_pipeline")
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    return logger


def run():
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("Starting FX pipeline run")

    try:
        init_db()

        # Extract
        payload = fetch_rates()

        # Transform
        df = clean_and_validate(payload)
        previous_rates = get_latest_rates(TARGET_PAIRS)
        df = flag_anomalies(df, previous_rates)

        # Load
        rows_written = load_rates(df)

        anomalies = df[df["is_anomaly"] == 1]
        if not anomalies.empty:
            logger.warning(f"{len(anomalies)} anomaly(ies) flagged this run:\n{anomalies.to_string(index=False)}")

        logger.info(f"Pipeline run complete. {rows_written} rows written.")
        return 0

    except ExtractError as e:
        logger.error(f"Pipeline FAILED at extract step: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Pipeline FAILED with unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(run())
