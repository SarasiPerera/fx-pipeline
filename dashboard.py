"""
Streamlit dashboard for the FX pipeline.
Run with: streamlit run dashboard.py
Reads read-only from the SQLite DB the pipeline writes to - the
dashboard never touches the API or writes to the DB itself.
"""
import pandas as pd
import streamlit as st

from config import DB_PATH, TARGET_PAIRS
from db import get_connection

st.set_page_config(page_title="Sri Lanka FX Dashboard", page_icon="💱", layout="wide")


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT date, currency_pair, rate, pct_change, is_anomaly, loaded_at "
            "FROM fx_rates ORDER BY date",
            conn,
        )
        df["date"] = pd.to_datetime(df["date"])
        return df
    finally:
        conn.close()


st.title("💱 Sri Lanka FX Rate Dashboard")
st.caption(f"Tracking {', '.join(TARGET_PAIRS)} · source data in `{DB_PATH}`")

df = load_data()

if df.empty:
    st.warning(
        "No data yet. Run `python3 etl.py` at least once (or wait for the "
        "scheduled cron job) to populate the database."
    )
    st.stop()

# --- Sidebar filters ---
st.sidebar.header("Filters")
pairs_available = sorted(df["currency_pair"].unique())
selected_pairs = st.sidebar.multiselect("Currency pairs", pairs_available, default=pairs_available)

min_date, max_date = df["date"].min(), df["date"].max()
date_range = st.sidebar.date_input(
    "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)

filtered = df[df["currency_pair"].isin(selected_pairs)]
if len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    filtered = filtered[(filtered["date"] >= start) & (filtered["date"] <= end)]

# --- Top-level metrics: latest rate + day-over-day change per pair ---
st.subheader("Latest rates")
cols = st.columns(len(pairs_available))
for i, pair in enumerate(pairs_available):
    pair_df = df[df["currency_pair"] == pair].sort_values("date")
    if pair_df.empty:
        continue
    latest = pair_df.iloc[-1]
    delta = None if pd.isna(latest["pct_change"]) else f"{latest['pct_change']:.2f}%"
    cols[i].metric(label=pair, value=f"{latest['rate']:.2f}", delta=delta)

# --- Anomaly banner ---
recent_anomalies = filtered[filtered["is_anomaly"] == 1].sort_values("date", ascending=False)
if not recent_anomalies.empty:
    st.warning(
        f"⚠️ {len(recent_anomalies)} anomaly-flagged reading(s) in the selected range "
        f"(>5% day-over-day move). See table below."
    )

# --- Trend chart ---
st.subheader("Rate trend over time")
pivot = filtered.pivot_table(index="date", columns="currency_pair", values="rate")
st.line_chart(pivot)

# --- Day-over-day % change chart ---
st.subheader("Day-over-day % change")
pivot_pct = filtered.pivot_table(index="date", columns="currency_pair", values="pct_change")
st.bar_chart(pivot_pct)

# --- Raw data / anomaly table ---
st.subheader("Data table")
show_only_anomalies = st.checkbox("Show only anomaly-flagged rows")
table_df = recent_anomalies if show_only_anomalies else filtered.sort_values("date", ascending=False)
st.dataframe(
    table_df[["date", "currency_pair", "rate", "pct_change", "is_anomaly"]],
    use_container_width=True,
    hide_index=True,
)

st.caption("Anomaly = |day-over-day % change| > 5%, per config.py's ANOMALY_THRESHOLD_PCT")
