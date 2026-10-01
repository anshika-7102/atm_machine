"""Unit and integration tests for TinkoffDataCleaner."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import shutil

from src.data.cleaner import TinkoffDataCleaner


@pytest.fixture
def sample_raw_df():
    """Create a synthetic sample DataFrame matching Tinkoff raw schema."""
    data = {
        "datetime": [
            "2017-08-01",
            "2017-08-01",  # exact duplicate of row 0
            "2017-08-01",  # same client & atm, different amount
            "2017-08-02",  # deposit
            "2017-08-03",  # withdrawal
        ],
        "atm_id": [74, 74, 74, 74, 85],
        "operation_type": [0, 0, 0, 0, 4],
        "client_id": [100, 100, 100, 101, 102],
        "operation_value": [5.0, 5.0, 10.0, -15.0, 20.0],
    }
    return pd.DataFrame(data)


@pytest.fixture
def temp_environment(sample_raw_df):
    """Set up temporary directories and raw CSV file."""
    temp_dir = tempfile.mkdtemp()
    raw_dir = Path(temp_dir) / "raw"
    processed_dir = Path(temp_dir) / "processed"
    docs_dir = Path(temp_dir) / "docs"

    raw_dir.mkdir(parents=True)
    raw_csv = raw_dir / "test_raw.csv"
    sample_raw_df.to_csv(raw_csv, index=False)

    yield {
        "raw_dir": str(raw_dir),
        "processed_dir": str(processed_dir),
        "docs_dir": str(docs_dir),
        "raw_filename": "test_raw.csv",
    }

    shutil.rmtree(temp_dir)


def test_standardize_columns(sample_raw_df):
    cleaner = TinkoffDataCleaner()
    df_messy = sample_raw_df.rename(columns={"datetime": " DateTime ", "atm_id": "ATM ID"})
    standardized = cleaner.standardize_columns(df_messy)
    assert "datetime" in standardized.columns
    assert "atm_id" in standardized.columns


def test_detect_and_remove_duplicates(sample_raw_df):
    cleaner = TinkoffDataCleaner()
    cleaned = cleaner.detect_and_remove_duplicates(sample_raw_df)
    # Row 0 and row 1 were exact duplicates; row count should decrease by 1
    assert len(cleaned) == len(sample_raw_df) - 1
    assert cleaner.metrics["duplicate_rows_removed"] == 1


def test_investigate_possible_duplicates(sample_raw_df):
    cleaner = TinkoffDataCleaner()
    cleaned = cleaner.detect_and_remove_duplicates(sample_raw_df)
    stats = cleaner.investigate_possible_duplicates(cleaned)
    assert stats["multi_transaction_rows"] == 2


def test_demand_aggregation_logic(sample_raw_df):
    cleaner = TinkoffDataCleaner()
    cleaned = cleaner.detect_and_remove_duplicates(sample_raw_df)
    cleaned["datetime"] = pd.to_datetime(cleaned["datetime"])

    demand_df = cleaner.create_demand_dataset(cleaned)
    # Check required columns
    required_cols = [
        "atm_id",
        "date",
        "demand",
        "deposit_amount",
        "transaction_count",
        "withdrawal_count",
        "deposit_count",
        "net_demand",
        "is_active_day",
    ]
    for col in required_cols:
        assert col in demand_df.columns

    # No negative demand
    assert (demand_df["demand"] < 0).sum() == 0
    # No duplicate ATM and Date pairs
    assert demand_df.duplicated(subset=["atm_id", "date"]).sum() == 0

    # ATM 74 on 2017-08-01: withdrawals 5.0 + 10.0 = 15.0
    row_74_0801 = demand_df[(demand_df["atm_id"] == 74) & (demand_df["date"] == "2017-08-01")]
    assert len(row_74_0801) == 1
    assert row_74_0801.iloc[0]["demand"] == 15.0
    assert row_74_0801.iloc[0]["withdrawal_count"] == 2

    # ATM 74 on 2017-08-02: deposit -15.0 -> demand = 0.0, deposit_amount = 15.0, net_demand = -15.0
    row_74_0802 = demand_df[(demand_df["atm_id"] == 74) & (demand_df["date"] == "2017-08-02")]
    assert len(row_74_0802) == 1
    assert row_74_0802.iloc[0]["demand"] == 0.0
    assert row_74_0802.iloc[0]["deposit_amount"] == 15.0
    assert row_74_0802.iloc[0]["net_demand"] == -15.0


def test_full_pipeline_execution(temp_environment):
    cleaner = TinkoffDataCleaner(**temp_environment)
    metrics = cleaner.run()

    processed_dir = Path(temp_environment["processed_dir"])
    docs_dir = Path(temp_environment["docs_dir"])

    assert (processed_dir / "tinkoff_cleaned.csv").exists()
    assert (processed_dir / "atm_demand_daily.csv").exists()
    assert (docs_dir / "DATA_QUALITY_REPORT.md").exists()
    assert metrics["cleaned_rows"] == 4
    assert metrics["duplicate_rows_removed"] == 1


def test_cleaner_production_outputs():
    """Verify production outputs generated on real Tinkoff dataset."""
    clean_csv = Path("data/processed/tinkoff_cleaned.csv")
    demand_csv = Path("data/processed/atm_demand_daily.csv")
    report_md = Path("docs/DATA_QUALITY_REPORT.md")

    assert clean_csv.exists()
    assert demand_csv.exists()
    assert report_md.exists()

    df_clean = pd.read_csv(clean_csv)
    assert len(df_clean) == 1037286
    assert df_clean["datetime"].is_monotonic_increasing

    df_demand = pd.read_csv(demand_csv)
    assert len(df_demand) == 8461
    assert (df_demand["demand"] < 0).sum() == 0
    assert df_demand.duplicated(subset=["atm_id", "date"]).sum() == 0
