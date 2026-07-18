"""
Unit tests for transform.py. Run with: pytest tests/ -v

These target the pure logic (cross-rate math, validation, anomaly
detection) rather than the network call, so they run instantly and
don't depend on the API being up.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from transform import clean_and_validate, flag_anomalies, _derive_pairs


SAMPLE_PAYLOAD = {
    "result": "success",
    "time_last_update_utc": "Fri, 10 Jul 2026 00:00:00 +0000",
    "base_code": "USD",
    "rates": {"LKR": 298.5, "GBP": 0.783, "EUR": 0.921},
}


def test_derive_pairs_computes_correct_crosses():
    pairs = _derive_pairs(SAMPLE_PAYLOAD["rates"])
    assert pairs["USD/LKR"] == 298.5
    assert pairs["GBP/LKR"] == pytest.approx(298.5 / 0.783)
    assert pairs["EUR/LKR"] == pytest.approx(298.5 / 0.921)


def test_derive_pairs_raises_on_missing_currency():
    with pytest.raises(ValueError):
        _derive_pairs({"LKR": 298.5, "GBP": 0.783})  # missing EUR


def test_clean_and_validate_returns_three_rows():
    df = clean_and_validate(SAMPLE_PAYLOAD)
    assert len(df) == 3
    assert set(df["currency_pair"]) == {"USD/LKR", "GBP/LKR", "EUR/LKR"}
    assert all(df["rate"] > 0)


def test_clean_and_validate_skips_negative_rate():
    # A negative GBP quote should only poison GBP/LKR (its cross-rate uses
    # GBP as the denominator) - USD/LKR and EUR/LKR stay valid and get loaded.
    bad_payload = {
        **SAMPLE_PAYLOAD,
        "rates": {"LKR": 298.5, "GBP": -0.783, "EUR": 0.921},
    }
    df = clean_and_validate(bad_payload)
    assert "GBP/LKR" not in set(df["currency_pair"])
    assert set(df["currency_pair"]) == {"USD/LKR", "EUR/LKR"}


def test_clean_and_validate_raises_when_all_rates_invalid():
    bad_payload = {
        **SAMPLE_PAYLOAD,
        "rates": {"LKR": -1, "GBP": 0.783, "EUR": 0.921},
    }
    # Negative LKR poisons every cross-rate (LKR is the shared numerator),
    # so nothing survives validation and the batch is correctly rejected
    # rather than silently loading garbage.
    with pytest.raises(ValueError):
        clean_and_validate(bad_payload)


def test_flag_anomalies_flags_large_moves():
    df = clean_and_validate(SAMPLE_PAYLOAD)
    previous_rates = {"USD/LKR": 270.0, "GBP/LKR": 400.0, "EUR/LKR": 350.0}  # big jump vs USD/LKR
    result = flag_anomalies(df, previous_rates)
    usd_row = result[result["currency_pair"] == "USD/LKR"].iloc[0]
    assert usd_row["is_anomaly"] == 1
    assert usd_row["pct_change"] > 5.0


def test_flag_anomalies_does_not_flag_small_moves():
    df = clean_and_validate(SAMPLE_PAYLOAD)
    previous_rates = {"USD/LKR": 298.0, "GBP/LKR": 381.0, "EUR/LKR": 324.0}  # tiny moves
    result = flag_anomalies(df, previous_rates)
    assert result["is_anomaly"].sum() == 0


def test_flag_anomalies_handles_no_previous_data():
    df = clean_and_validate(SAMPLE_PAYLOAD)
    result = flag_anomalies(df, previous_rates={})
    assert result["is_anomaly"].sum() == 0
    assert result["pct_change"].isna().all()
