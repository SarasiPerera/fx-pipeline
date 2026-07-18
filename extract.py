"""
Extract step: hit the ExchangeRate-API open endpoint and return the raw
USD-based rates dict. Retries with exponential backoff on failure -
this is the bit that turns "a script that breaks the day the API hiccups"
into something that reads as engineering.
"""
import time
import logging
import requests

from config import API_BASE_URL, API_TIMEOUT_SECONDS, MAX_RETRIES, RETRY_BACKOFF_SECONDS

logger = logging.getLogger("fx_pipeline.extract")


class ExtractError(Exception):
    """Raised when the API can't be reached or returns bad data after all retries."""
    pass


def fetch_rates() -> dict:
    """
    Calls the API and returns the parsed JSON payload.
    Retries MAX_RETRIES times with exponential backoff before giving up.
    """
    last_exception = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Fetching rates from API (attempt {attempt}/{MAX_RETRIES})")
            resp = requests.get(API_BASE_URL, timeout=API_TIMEOUT_SECONDS)
            resp.raise_for_status()
            payload = resp.json()

            if payload.get("result") != "success":
                raise ExtractError(f"API returned non-success result: {payload.get('result')}")

            if "rates" not in payload:
                raise ExtractError("API response missing 'rates' key")

            logger.info("Successfully fetched rates from API")
            return payload

        except (requests.RequestException, ExtractError, ValueError) as e:
            last_exception = e
            logger.warning(f"Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                sleep_time = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.info(f"Retrying in {sleep_time}s...")
                time.sleep(sleep_time)

    logger.error(f"All {MAX_RETRIES} attempts failed. Last error: {last_exception}")
    raise ExtractError(f"Failed to fetch rates after {MAX_RETRIES} attempts: {last_exception}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = fetch_rates()
    print(f"Base: {data.get('base_code')}, LKR rate: {data['rates'].get('LKR')}")
