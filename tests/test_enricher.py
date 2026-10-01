"""Unit tests for DataEnricher module."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from src.data.enricher import DataEnricher, ATM_PROFILES


@pytest.fixture
def sample_demand_df():
    """Create a minimal daily demand DataFrame for testing."""
    records = []
    for atm_id in [74, 85]:
        dates = pd.date_range("2017-08-01", "2017-08-10", freq="D").strftime("%Y-%m-%d")
        for d in dates:
            records.append(
                {
                    "atm_id": atm_id,
                    "date": d,
                    "demand": 500.0,
                    "deposit_amount": 200.0,
                    "transaction_count": 50,
                    "withdrawal_count": 35,
                    "deposit_count": 15,
                    "net_demand": 300.0,
                    "is_active_day": True,
                }
            )
    return pd.DataFrame(records)


def test_atm_metadata_generation(sample_demand_df, tmp_path):
    enricher = DataEnricher(processed_dir=str(tmp_path))
    meta_df = enricher.generate_atm_metadata(sample_demand_df)

    assert len(meta_df) == 2
    assert "latitude" in meta_df.columns
    assert "longitude" in meta_df.columns
    assert "max_cash_capacity" in meta_df.columns
    assert meta_df.iloc[0]["atm_id"] == 74
    assert meta_df.iloc[0]["city"] == "Moscow"


def test_calendar_holidays_generation(tmp_path):
    enricher = DataEnricher(processed_dir=str(tmp_path))
    cal_df = enricher.generate_calendar_holidays("2017-06-01", "2017-06-15")

    assert len(cal_df) == 15
    assert "is_holiday" in cal_df.columns
    assert "is_weekend" in cal_df.columns
    assert "days_to_next_holiday" in cal_df.columns
    # June 12 is Russia Day
    russia_day = cal_df[cal_df["date"] == "2017-06-12"]
    assert russia_day.iloc[0]["is_holiday"] == 1
    assert "Russia Day" in russia_day.iloc[0]["holiday_name"]


def test_cash_balances_and_replenishment(sample_demand_df, tmp_path):
    enricher = DataEnricher(processed_dir=str(tmp_path))
    meta_df = enricher.generate_atm_metadata(sample_demand_df)
    balance_df = enricher.simulate_cash_balances_and_replenishment(sample_demand_df, meta_df)

    assert len(balance_df) == len(sample_demand_df)
    assert "opening_balance" in balance_df.columns
    assert "closing_balance" in balance_df.columns
    assert "risk_level" in balance_df.columns
    assert set(balance_df["risk_level"].unique()).issubset({"Low", "Medium", "High"})


def test_production_enriched_files_exist():
    """Verify that production enriched datasets exist and have valid structure."""
    processed_dir = Path("data/processed")
    assert (processed_dir / "atm_metadata.csv").exists()
    assert (processed_dir / "calendar_holidays.csv").exists()
    assert (processed_dir / "weather_daily.csv").exists()
    assert (processed_dir / "atm_cash_balances.csv").exists()
    assert (processed_dir / "atm_demand_enriched.csv").exists()

    df_enriched = pd.read_csv(processed_dir / "atm_demand_enriched.csv")
    assert len(df_enriched) == 8461
    assert df_enriched["atm_id"].nunique() == 20
    assert "demand" in df_enriched.columns
    assert "latitude" in df_enriched.columns
    assert "temp_mean_c" in df_enriched.columns
    assert "closing_balance" in df_enriched.columns
