# Sri Lanka FX Rate ETL Pipeline & Dashboard

An automated pipeline that pulls daily USD/LKR, GBP/LKR, and EUR/LKR
exchange rates, validates and flags anomalies, loads them into SQLite,
and visualizes trends in a Streamlit dashboard.

```
[ExchangeRate-API] -> [extract.py] -> [transform.py] -> [load.py: SQLite]
                                                              |
                                                    [cron: daily @ 09:00]
                                                              |
                                                  [dashboard.py: Streamlit]
```

## Project layout

```
fx_pipeline/
├── config.py          # all settings in one place (paths, currencies, thresholds)
├── db.py               # SQLite schema + connection helper
├── extract.py          # API call with retry/backoff
├── transform.py        # cross-rate derivation, validation, anomaly flagging
├── load.py              # idempotent upsert into SQLite
├── etl.py                # orchestrates extract -> transform -> load; what cron runs
├── dashboard.py       # Streamlit UI, reads from the DB
├── run_pipeline.sh    # cron-friendly wrapper (activates venv, runs etl.py)
├── tests/
│   └── test_transform.py   # unit tests for the validation/anomaly logic
├── data/fx_rates.db    # created on first run
├── logs/pipeline.log   # rotating log file, created on first run
└── requirements.txt
```

## Setup

```bash
cd fx_pipeline
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run it

**One-off pipeline run** (extract → transform → load):
```bash
python3 etl.py
```
This creates `data/fx_rates.db` on first run and appends a row per
currency pair per day. Re-running the same day updates that day's row
in place (idempotent — safe to re-run).

**Run the test suite:**
```bash
pytest tests/ -v
```

**Launch the dashboard:**
```bash
streamlit run dashboard.py
```
Opens at `http://localhost:8501`. Shows latest rates, a trend line
chart, a day-over-day % change bar chart, and a filterable data table
with anomaly flags.

## Scheduling with cron (Linux/Mac)

1. Make the wrapper executable (already done, but if you `git clone` fresh):
   ```bash
   chmod +x run_pipeline.sh
   ```
2. Open your crontab:
   ```bash
   crontab -e
   ```
3. Add a line to run daily at 9:00 AM (adjust the path):
   ```
   0 9 * * * /full/path/to/fx_pipeline/run_pipeline.sh >> /full/path/to/fx_pipeline/logs/cron.log 2>&1
   ```
4. Verify it's registered:
   ```bash
   crontab -l
   ```

The wrapper script itself also writes structured logs (with rotation)
to `logs/pipeline.log` via Python's `logging` module — the `cron.log`
redirect above is just a safety net to catch anything cron-level
(e.g. the script failing to even start).

### Windows Task Scheduler (alternative)
Create a Basic Task that runs daily, with:
- **Program:** `C:\path\to\fx_pipeline\venv\Scripts\python.exe`
- **Arguments:** `etl.py`
- **Start in:** `C:\path\to\fx_pipeline`

## How it works

1. **Extract** (`extract.py`) — calls the open ExchangeRate-API endpoint
   (`open.er-api.com`, USD-based, no key needed). Retries up to 3 times
   with exponential backoff (2s, 4s, 8s) on network/API failure.
2. **Transform** (`transform.py`) — the API only gives USD-based rates,
   so GBP/LKR and EUR/LKR are derived as cross rates
   (`GBP/LKR = LKR_per_USD / GBP_per_USD`). Rows with missing, non-numeric,
   or non-positive rates are dropped rather than loaded. Each row's
   day-over-day `pct_change` is computed against the last stored value
   for that pair, and flagged `is_anomaly = 1` if it moves more than
   ±5% (configurable via `ANOMALY_THRESHOLD_PCT` in `config.py`).
3. **Load** (`load.py`) — upserts into SQLite on `(date, currency_pair)`,
   so re-running the same day never creates duplicates.
4. **Schedule** — cron/Task Scheduler runs `run_pipeline.sh` /
   `etl.py` daily so history accumulates automatically.
5. **Visualize** (`dashboard.py`) — Streamlit reads directly from the
   DB (read-only) and renders trend/volatility views.

## Extending this project

- **Postgres:** swap `db.py`'s `get_connection()` for a `psycopg2`/`SQLAlchemy`
  connection — nothing else in the pipeline references SQLite directly.
- **CBSL scraping:** for a "harder ETL" version, replace `extract.py`'s
  API call with an HTML parse of CBSL's daily indicative rates page
  (BeautifulSoup/lxml). Keep the same `transform.py`/`load.py` contract
  (a dict of `{currency: rate}` in, going into `_derive_pairs`/`clean_and_validate`)
  so the rest of the pipeline doesn't change.
- **Airflow:** wrap `etl.py`'s `run()` function as a single PythonOperator
  task in a daily DAG if you want that keyword on the CV instead of cron.

## Tech stack

Python, Pandas, SQLite, cron, Streamlit, REST APIs, pytest
