"""
Central configuration for the FX pipeline.
Keeping this separate means cron jobs, the dashboard, and tests
all agree on the same paths/settings instead of hardcoding them everywhere.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- API ---
# ExchangeRate-API open-access endpoint. No key required.
# Base currency is USD; we derive LKR/GBP/EUR crosses from it.
API_BASE_URL = "https://open.er-api.com/v6/latest/USD"
API_TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2  # doubles each retry: 2s, 4s, 8s

# --- Currency pairs we track (all vs LKR) ---
TARGET_PAIRS = ["USD/LKR", "GBP/LKR", "EUR/LKR"]
SOURCE_NAME = "exchangerate-api.com"

# --- Storage ---
DB_PATH = os.path.join(BASE_DIR, "data", "fx_rates.db")

# --- Logging ---
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_PATH = os.path.join(LOG_DIR, "pipeline.log")

# --- Data quality ---
# Flag a rate as a potential anomaly if it moves more than this % vs
# the previous stored value for the same pair.
ANOMALY_THRESHOLD_PCT = 5.0
