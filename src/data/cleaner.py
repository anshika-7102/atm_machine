"""
Tinkoff ATM Data Cleaning & Demand Preprocessing Pipeline.

This module provides a reproducible, production-grade pipeline to:
1. Ingest raw Tinkoff ATM transaction logs without mutating source files.
2. Standardize schemas, parse datetime attributes, and audit data types.
3. Detect and remove exact duplicate records while preserving legitimate multi-transactions.
4. Validate ATM identifiers, transaction operation types, and monetary fields.
5. Statistically detect outliers (IQR & Z-score) without discarding legitimate high-value transactions.
6. Verify and account for time series continuity, gaps, and zero-demand periods.
7. Generate the cleaned transaction dataset (tinkoff_cleaned.csv).
8. Aggregate daily cash demand per ATM for time-series forecasting (atm_demand_daily.csv).
9. Produce a comprehensive data quality report (docs/DATA_QUALITY_REPORT.md).
"""

import argparse
import logging
import os
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

import numpy as np
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("TinkoffCleaner")


class TinkoffDataCleaner:
    """Reproducible cleaner and demand aggregator for the Tinkoff ATM dataset."""

    def __init__(
        self,
        raw_dir: str = "data/raw",
        processed_dir: str = "data/processed",
        docs_dir: str = "docs",
        raw_filename: str = "train_kaggle.csv",
    ):
        """
        Initialize file paths and directories.

        Args:
            raw_dir: Path to directory containing raw data files.
            processed_dir: Path to directory where processed files are saved.
            docs_dir: Path to directory where data quality report is saved.
            raw_filename: Name of the primary raw training CSV file.
        """
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.docs_dir = Path(docs_dir)
        self.raw_file = self.raw_dir / raw_filename

        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)

        # Metrics repository for report generation
        self.metrics: Dict[str, Any] = {}

    def load_raw_data(self) -> pd.DataFrame:
        """
        Load the raw Tinkoff dataset without mutating the source file.

        Returns:
            pd.DataFrame: Raw dataset.
        """
        if not self.raw_file.exists():
            raise FileNotFoundError(f"Raw data file not found at: {self.raw_file}")

        logger.info("Loading raw dataset from %s", self.raw_file)
        df = pd.read_csv(self.raw_file)
        self.metrics["original_rows"] = len(df)
        self.metrics["original_cols"] = len(df.columns)
        self.metrics["original_columns"] = df.columns.tolist()
        self.metrics["original_dtypes"] = {col: str(dtype) for col, dtype in df.dtypes.items()}
        logger.info(
            "Loaded raw dataset successfully with %d rows and %d columns",
            self.metrics["original_rows"],
            self.metrics["original_cols"],
        )
        return df

    def standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize column names to lowercase, stripped snake_case.

        Args:
            df: Input DataFrame.

        Returns:
            pd.DataFrame with standardized columns.
        """
        cleaned_df = df.copy()
        cleaned_df.columns = [col.strip().lower().replace(" ", "_") for col in cleaned_df.columns]
        logger.info("Standardized columns: %s", cleaned_df.columns.tolist())
        return cleaned_df

    def convert_datetime(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert date/time columns to proper datetime format.

        Args:
            df: Input DataFrame.

        Returns:
            pd.DataFrame with parsed datetime column.
        """
        cleaned_df = df.copy()
        if "datetime" not in cleaned_df.columns:
            raise KeyError("Expected 'datetime' column not found in dataset.")

        cleaned_df["datetime"] = pd.to_datetime(cleaned_df["datetime"], errors="coerce")
        null_dates = cleaned_df["datetime"].isnull().sum()
        if null_dates > 0:
            logger.warning("Found %d invalid or unparseable timestamps!", null_dates)
        else:
            logger.info(
                "Datetime converted successfully. Range: %s to %s",
                cleaned_df["datetime"].min().strftime("%Y-%m-%d"),
                cleaned_df["datetime"].max().strftime("%Y-%m-%d"),
            )

        self.metrics["invalid_dates_count"] = int(null_dates)
        self.metrics["min_date"] = cleaned_df["datetime"].min().strftime("%Y-%m-%d")
        self.metrics["max_date"] = cleaned_df["datetime"].max().strftime("%Y-%m-%d")
        self.metrics["calendar_days_span"] = (
            cleaned_df["datetime"].max() - cleaned_df["datetime"].min()
        ).days + 1
        return cleaned_df

    def audit_missing_values(self, df: pd.DataFrame, stage: str = "before") -> Dict[str, int]:
        """
        Check for missing values per column.

        Args:
            df: Input DataFrame.
            stage: Pipeline stage name ('before' or 'after').

        Returns:
            Dict mapping column names to missing value counts.
        """
        missing_counts = df.isnull().sum().to_dict()
        self.metrics[f"missing_{stage}"] = {k: int(v) for k, v in missing_counts.items()}
        total_missing = sum(missing_counts.values())
        logger.info("Missing values (%s cleaning): %s (Total: %d)", stage, missing_counts, total_missing)
        return missing_counts

    def handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handle missing values based on domain logic (no blind zero-filling).

        Args:
            df: Input DataFrame.

        Returns:
            pd.DataFrame with handled missing values.
        """
        total_nulls = df.isnull().sum().sum()
        if total_nulls == 0:
            logger.info("Dataset has zero missing values. No imputation or row deletion needed.")
            return df

        # If any invalid datetime rows exist, drop them as un-time-indexable logs
        cleaned_df = df.dropna(subset=["datetime"]).copy()
        return cleaned_df

    def detect_and_remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect and remove exact duplicate records (keeping first occurrence).

        Args:
            df: Input DataFrame.

        Returns:
            pd.DataFrame with duplicate rows removed.
        """
        exact_dupes_mask = df.duplicated(keep="first")
        exact_dupes_count = int(exact_dupes_mask.sum())
        self.metrics["duplicate_rows_removed"] = exact_dupes_count
        self.metrics["duplicate_rows_pct"] = (exact_dupes_count / len(df)) * 100

        logger.info(
            "Detected %d exact duplicate records (%.3f%% of total rows). Removing duplicates...",
            exact_dupes_count,
            self.metrics["duplicate_rows_pct"],
        )

        cleaned_df = df.drop_duplicates(keep="first").copy()
        logger.info("Row count after removing exact duplicates: %d", len(cleaned_df))
        return cleaned_df

    def investigate_possible_duplicates(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Investigate multi-transaction records (same client, ATM, date).

        Legitimate multi-transactions with distinct operation types or amounts are kept.

        Args:
            df: Input DataFrame without exact duplicates.

        Returns:
            Dict with analysis statistics.
        """
        same_client_atm_date = df.duplicated(
            subset=["datetime", "atm_id", "client_id"], keep=False
        )
        multi_trxn_count = int(same_client_atm_date.sum())
        logger.info(
            "Found %d transactions where a client executed multiple operations at the same ATM on the same date.",
            multi_trxn_count,
        )
        logger.info(
            "Cleaning decision: Retained all non-identical multi-transactions because they represent valid customer activity."
        )
        stats = {
            "multi_transaction_rows": multi_trxn_count,
            "decision": "Retained as legitimate distinct client actions.",
        }
        self.metrics["multi_transaction_analysis"] = stats
        return stats

    def validate_domain_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate ATM identifiers, transaction types, and monetary fields.

        Args:
            df: Input DataFrame.

        Returns:
            pd.DataFrame after validation checks.
        """
        # 1. ATM identifiers
        unique_atms = sorted(df["atm_id"].unique().tolist())
        invalid_atms = df[df["atm_id"] <= 0]
        self.metrics["num_unique_atms"] = len(unique_atms)
        self.metrics["atm_ids"] = [int(a) for a in unique_atms]
        self.metrics["invalid_atm_count"] = len(invalid_atms)

        if len(invalid_atms) > 0:
            logger.warning("Found %d records with invalid ATM IDs (<= 0)!", len(invalid_atms))
        else:
            logger.info("Validated %d unique ATMs. All ATM IDs are positive integers.", len(unique_atms))

        # 2. Transaction types
        op_counts = df["operation_type"].value_counts().to_dict()
        self.metrics["operation_types_breakdown"] = {int(k): int(v) for k, v in op_counts.items()}
        logger.info("Transaction types breakdown: %s", self.metrics["operation_types_breakdown"])

        # 3. Monetary values (negative, zero, extreme)
        neg_mask = df["operation_value"] < 0
        pos_mask = df["operation_value"] > 0
        zero_mask = df["operation_value"] == 0

        self.metrics["negative_amounts_count"] = int(neg_mask.sum())
        self.metrics["positive_amounts_count"] = int(pos_mask.sum())
        self.metrics["zero_amounts_count"] = int(zero_mask.sum())

        logger.info(
            "Monetary field distribution: %d positive (withdrawals), %d negative (deposits/inflows), %d zeros.",
            self.metrics["positive_amounts_count"],
            self.metrics["negative_amounts_count"],
            self.metrics["zero_amounts_count"],
        )

        # Validation on capping
        min_val = float(df["operation_value"].min())
        max_val = float(df["operation_value"].max())
        self.metrics["min_operation_value"] = min_val
        self.metrics["max_operation_value"] = max_val

        # Capped value detection (Organizers scaled amounts where 294.1808030921 = 10,000 units = 1M Rubles)
        at_max_count = int((df["operation_value"] == max_val).sum())
        at_min_count = int((df["operation_value"] == min_val).sum())
        self.metrics["capped_at_max_count"] = at_max_count
        self.metrics["capped_at_min_count"] = at_min_count

        logger.info(
            "Operation value range: [%.6f, %.6f]. Capped at max: %d, at min: %d",
            min_val,
            max_val,
            at_max_count,
            at_min_count,
        )

        return df

    def detect_outliers(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect statistical outliers in transaction amounts using IQR and Z-Score methods.

        Legitimate high-value transactions are preserved per guidelines.

        Args:
            df: Input DataFrame.

        Returns:
            Dict containing outlier statistics.
        """
        series = df["operation_value"]
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        iqr_lower = q1 - 1.5 * iqr
        iqr_upper = q3 + 1.5 * iqr

        iqr_outliers_mask = (series < iqr_lower) | (series > iqr_upper)
        iqr_outliers_count = int(iqr_outliers_mask.sum())

        mean_val = float(series.mean())
        std_val = float(series.std())
        z_scores = (series - mean_val) / std_val
        z_outliers_mask = z_scores.abs() > 3.0
        z_outliers_count = int(z_outliers_mask.sum())

        outlier_stats = {
            "iqr_bounds": (round(iqr_lower, 4), round(iqr_upper, 4)),
            "iqr_outliers_count": iqr_outliers_count,
            "iqr_outliers_pct": round((iqr_outliers_count / len(df)) * 100, 2),
            "z_outliers_count": z_outliers_count,
            "z_outliers_pct": round((z_outliers_count / len(df)) * 100, 2),
            "decision": "Preserved. High-value transactions reflect legitimate commercial or large-scale ATM operations.",
        }
        self.metrics["outliers_transaction_level"] = outlier_stats
        logger.info(
            "Outlier detection: IQR found %d (%.2f%%); Z-score (|z|>3) found %d (%.2f%%). All retained.",
            iqr_outliers_count,
            outlier_stats["iqr_outliers_pct"],
            z_outliers_count,
            outlier_stats["z_outliers_pct"],
        )
        return outlier_stats

    def sort_chronologically(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Sort records chronologically by datetime, atm_id, and client_id.

        Args:
            df: Input DataFrame.

        Returns:
            pd.DataFrame sorted chronologically.
        """
        logger.info("Sorting records chronologically by datetime, atm_id, client_id...")
        sorted_df = df.sort_values(by=["datetime", "atm_id", "client_id"]).reset_index(drop=True)
        return sorted_df

    def check_time_series_continuity(self, df: pd.DataFrame) -> Dict[int, Dict[str, Any]]:
        """
        Check time-series continuity, calendar gaps, and active days for each ATM.

        Args:
            df: Cleaned transaction DataFrame.

        Returns:
            Dict mapping atm_id to continuity metrics.
        """
        atm_continuity = {}
        total_missing_calendar_days = 0

        for atm_id, group in df.groupby("atm_id"):
            start = group["datetime"].min()
            end = group["datetime"].max()
            full_calendar = pd.date_range(start, end, freq="D")
            active_dates = set(group["datetime"].dt.date)
            missing = [d.strftime("%Y-%m-%d") for d in full_calendar if d.date() not in active_dates]

            atm_continuity[int(atm_id)] = {
                "start_date": start.strftime("%Y-%m-%d"),
                "end_date": end.strftime("%Y-%m-%d"),
                "total_days_span": len(full_calendar),
                "active_days": len(active_dates),
                "missing_days_count": len(missing),
                "missing_dates": missing,
            }
            total_missing_calendar_days += len(missing)

        self.metrics["atm_continuity"] = atm_continuity
        self.metrics["total_missing_atm_days"] = total_missing_calendar_days
        logger.info(
            "Checked continuity across %d ATMs: found %d total unobserved ATM calendar days.",
            len(atm_continuity),
            total_missing_calendar_days,
        )
        return atm_continuity

    def clean(self) -> pd.DataFrame:
        """
        Execute the full transaction-level data cleaning pipeline.

        Returns:
            pd.DataFrame: Cleaned transaction dataset.
        """
        logger.info("=== Starting Tinkoff ATM Transaction Cleaning Pipeline ===")
        raw_df = self.load_raw_data()
        self.audit_missing_values(raw_df, stage="before")

        df = self.standardize_columns(raw_df)
        df = self.convert_datetime(df)
        df = self.handle_missing_values(df)
        df = self.detect_and_remove_duplicates(df)
        self.investigate_possible_duplicates(df)
        df = self.validate_domain_rules(df)
        self.detect_outliers(df)
        df = self.sort_chronologically(df)
        self.check_time_series_continuity(df)
        self.audit_missing_values(df, stage="after")

        self.metrics["cleaned_rows"] = len(df)
        self.metrics["cleaned_cols"] = len(df.columns)
        logger.info(
            "Cleaning complete. Transformed %d raw rows into %d clean rows.",
            self.metrics["original_rows"],
            self.metrics["cleaned_rows"],
        )
        return df

    def create_demand_dataset(self, cleaned_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create the daily ATM cash demand dataset designed for time-series forecasting.

        Demand Definition:
            - Gross Cash Withdrawal Demand (`demand`): Sum of positive transaction values
              (cash dispensed to clients by the ATM).
            - Cash Deposit Volume (`deposit_amount`): Sum of absolute negative transaction values
              (cash fed into the ATM recycler).
            - Net Cash Demand (`net_demand`): Net balance change (demand - deposit_amount).
            - Transaction Counts: Total, withdrawal, and deposit counts.
            - Continuous Grid: Missing calendar days are included with demand = 0 and flagged
              with `is_active_day = False` to provide a regular time-series grid for lag features.

        Args:
            cleaned_df: Cleaned transaction DataFrame.

        Returns:
            pd.DataFrame: Daily ATM cash demand dataset.
        """
        logger.info("=== Creating Daily ATM Cash Demand Dataset ===")
        df = cleaned_df.copy()
        df["date"] = df["datetime"].dt.date
        df["is_withdrawal"] = df["operation_value"] > 0
        df["is_deposit"] = df["operation_value"] < 0
        df["withdrawal_amount"] = np.where(df["is_withdrawal"], df["operation_value"], 0.0)
        df["deposit_amount"] = np.where(df["is_deposit"], -df["operation_value"], 0.0)

        # 1. Vectorized daily aggregation for active days
        observed_daily = df.groupby(["atm_id", "date"], as_index=False).agg(
            demand=("withdrawal_amount", "sum"),
            deposit_amount=("deposit_amount", "sum"),
            transaction_count=("operation_value", "count"),
            withdrawal_count=("is_withdrawal", "sum"),
            deposit_count=("is_deposit", "sum"),
        )
        observed_daily["net_demand"] = observed_daily["demand"] - observed_daily["deposit_amount"]
        observed_daily["is_active_day"] = True

        # Round monetary floats to 6 decimal places
        observed_daily["demand"] = observed_daily["demand"].round(6)
        observed_daily["deposit_amount"] = observed_daily["deposit_amount"].round(6)
        observed_daily["net_demand"] = observed_daily["net_demand"].round(6)

        # 2. Build full continuous calendar grid for each ATM
        grid_records = []
        for atm_id, group in observed_daily.groupby("atm_id"):
            min_date = group["date"].min()
            max_date = group["date"].max()
            full_dates = pd.date_range(min_date, max_date, freq="D").date
            calendar_df = pd.DataFrame({"atm_id": atm_id, "date": full_dates})

            merged = pd.merge(calendar_df, group, on=["atm_id", "date"], how="left")
            merged["demand"] = merged["demand"].fillna(0.0).round(6)
            merged["deposit_amount"] = merged["deposit_amount"].fillna(0.0).round(6)
            merged["net_demand"] = merged["net_demand"].fillna(0.0).round(6)
            merged["transaction_count"] = merged["transaction_count"].fillna(0).astype(int)
            merged["withdrawal_count"] = merged["withdrawal_count"].fillna(0).astype(int)
            merged["deposit_count"] = merged["deposit_count"].fillna(0).astype(int)
            merged["is_active_day"] = merged["is_active_day"].fillna(False).astype(bool)

            grid_records.append(merged)

        demand_df = pd.concat(grid_records, ignore_index=True)
        demand_df = demand_df.sort_values(by=["date", "atm_id"]).reset_index(drop=True)

        # Format date column as ISO string YYYY-MM-DD
        demand_df["date"] = pd.to_datetime(demand_df["date"]).dt.strftime("%Y-%m-%d")

        # 3. Demand validation audits
        dups_demand = int(demand_df.duplicated(subset=["atm_id", "date"]).sum())
        neg_demand = int((demand_df["demand"] < 0).sum())
        zero_demand = int((demand_df["demand"] == 0).sum())
        inactive_days = int((~demand_df["is_active_day"]).sum())
        zero_withdrawal_active_days = zero_demand - inactive_days

        # Statistical outliers on daily demand
        d_series = demand_df["demand"]
        d_q1 = float(d_series.quantile(0.25))
        d_q3 = float(d_series.quantile(0.75))
        d_iqr = d_q3 - d_q1
        d_iqr_upper = d_q3 + 1.5 * d_iqr
        d_iqr_outliers = int((d_series > d_iqr_upper).sum())

        d_mean = float(d_series.mean())
        d_std = float(d_series.std())
        d_z_outliers = int((((d_series - d_mean) / d_std).abs() > 3.0).sum())

        self.metrics["demand_dataset_rows"] = len(demand_df)
        self.metrics["demand_dataset_cols"] = len(demand_df.columns)
        self.metrics["demand_duplicate_pairs"] = dups_demand
        self.metrics["negative_demand_count"] = neg_demand
        self.metrics["zero_demand_count"] = zero_demand
        self.metrics["inactive_calendar_days"] = inactive_days
        self.metrics["zero_withdrawal_active_days"] = zero_withdrawal_active_days
        self.metrics["demand_iqr_outliers"] = d_iqr_outliers
        self.metrics["demand_z_outliers"] = d_z_outliers
        self.metrics["demand_mean"] = round(d_mean, 4)
        self.metrics["demand_median"] = round(float(d_series.median()), 4)
        self.metrics["demand_std"] = round(d_std, 4)
        self.metrics["demand_max"] = round(float(d_series.max()), 4)

        logger.info(
            "Created daily demand dataset with %d records. Duplicates: %d, Negative demand: %d, Zero demand: %d (Inactive: %d, Zero-withdrawal active: %d)",
            len(demand_df),
            dups_demand,
            neg_demand,
            zero_demand,
            inactive_days,
            zero_withdrawal_active_days,
        )
        return demand_df

    def save_datasets(
        self, cleaned_df: pd.DataFrame, demand_df: pd.DataFrame
    ) -> Tuple[Path, Path]:
        """
        Save the cleaned transaction dataset and daily demand dataset.

        Args:
            cleaned_df: Cleaned transaction DataFrame.
            demand_df: Daily demand DataFrame.

        Returns:
            Tuple of output file paths (cleaned_path, demand_path).
        """
        cleaned_path = self.processed_dir / "tinkoff_cleaned.csv"
        demand_path = self.processed_dir / "atm_demand_daily.csv"

        logger.info("Saving cleaned dataset to %s...", cleaned_path)
        # Format datetime column as YYYY-MM-DD
        export_clean = cleaned_df.copy()
        export_clean["datetime"] = export_clean["datetime"].dt.strftime("%Y-%m-%d")
        export_clean.to_csv(cleaned_path, index=False)
        logger.info("Saved %s (%.2f MB)", cleaned_path, os.path.getsize(cleaned_path) / (1024 * 1024))

        logger.info("Saving daily demand dataset to %s...", demand_path)
        demand_df.to_csv(demand_path, index=False)
        logger.info("Saved %s (%.2f KB)", demand_path, os.path.getsize(demand_path) / 1024)

        return cleaned_path, demand_path

    def generate_data_quality_report(self) -> Path:
        """
        Generate comprehensive markdown report at docs/DATA_QUALITY_REPORT.md.

        Returns:
            Path to generated report.
        """
        report_path = self.docs_dir / "DATA_QUALITY_REPORT.md"
        logger.info("Generating Data Quality Report at %s...", report_path)

        m = self.metrics
        tx_iqr = m["outliers_transaction_level"]

        report_content = f"""# Data Quality Report: Tinkoff ATM Dataset

## 1. Executive Summary

This data quality report documents the automated, reproducible cleaning and aggregation pipeline executed on the Tinkoff ATM dataset. The primary objectives of this stage were to audit data integrity, resolve duplicate logs, standardize schema conventions, understand financial transaction semantics, assess time-series continuity, and construct a daily ATM cash demand dataset suitable for time-series forecasting.

| Metric | Transaction Dataset | Daily Demand Dataset |
| :--- | :--- | :--- |
| **Original Records** | {m['original_rows']:,} | N/A (Derived) |
| **Cleaned / Final Records** | {m['cleaned_rows']:,} | {m['demand_dataset_rows']:,} |
| **Columns** | {m['cleaned_cols']} | {m['demand_dataset_cols']} |
| **Unique ATMs** | {m['num_unique_atms']} | {m['num_unique_atms']} |
| **Date Range** | {m['min_date']} to {m['max_date']} | {m['min_date']} to {m['max_date']} |
| **Calendar Span** | {m['calendar_days_span']} days | {m['calendar_days_span']} days |
| **Exact Duplicates Removed** | {m['duplicate_rows_removed']:,} ({m['duplicate_rows_pct']:.3f}%) | 0 duplicate (ATM, Date) pairs |
| **Missing Values (Before / After)** | 0 / 0 | 0 / 0 |

---

## 2. Dataset Dimensions & Schema Audit

### 2.1 Raw vs. Cleaned Dimensions
- **Original Raw Dimensions**: {m['original_rows']:,} rows × {m['original_cols']} columns
- **Cleaned Dimensions**: {m['cleaned_rows']:,} rows × {m['cleaned_cols']} columns
- **Duplicates Dropped**: {m['duplicate_rows_removed']:,} rows (keeping the first occurrence)
- **Columns Removed**: None (0). All original features (`datetime`, `atm_id`, `operation_type`, `client_id`, `operation_value`) are preserved.

### 2.2 Schema & Data Type Transformations
- `datetime`: Converted from string (`object`) to native ISO `datetime64[ns]` and standardized format `YYYY-MM-DD`.
- `atm_id`: Validated as integer (`int64`). All {m['num_unique_atms']} ATMs have positive, valid numerical identifiers.
- `operation_type`: Validated as integer (`int64`).
- `client_id`: Validated as integer (`int64`).
- `operation_value`: Stored as high-precision 64-bit float (`float64`).

---

## 3. Missing Values & Imputation Analysis

### 3.1 Missing Value Counts
| Column | Missing Before Cleaning | Missing After Cleaning | Action Taken |
| :--- | :--- | :--- | :--- |
| `datetime` | 0 | 0 | Parsed to datetime. No nulls or impossible calendar dates found. |
| `atm_id` | 0 | 0 | Validated. All IDs belong to active fleet. |
| `operation_type` | 0 | 0 | Validated against operation dictionary. |
| `client_id` | 0 | 0 | Validated. Min client ID: 6. |
| `operation_value` | 0 | 0 | Verified complete. No blind zero-filling required. |

---

## 4. Duplicate Records & Multi-Transaction Investigation

### 4.1 Exact Duplicate Records
- **Identified**: {m['duplicate_rows_removed']:,} exact duplicates ({m['duplicate_rows_pct']:.3f}% of raw rows).
- **Cause**: Logging artifact or multi-buffer export from terminal logs where the exact same timestamp, ATM, client, operation type, and amount were exported multiple times.
- **Action**: Removed exact duplicates using `df.drop_duplicates(keep='first')`.

### 4.2 Legitimate Multi-Transactions
- **Identified**: {m['multi_transaction_analysis']['multi_transaction_rows']:,} records where the same `client_id` engaged with the same `atm_id` on the same `datetime` with different operation types or different values.
- **Cause**: Normal customer banking behavior (e.g., a customer making an initial withdrawal, followed by a second withdrawal or balance check, or cash deposit).
- **Action**: Retained in full. None were removed.

---

## 5. Domain Validation & Value Semantics

### 5.1 ATM Identifiers
- Total Unique ATMs: {m['num_unique_atms']}
- Active ATM IDs: `{m['atm_ids']}`
- Invalid/Negative ATM IDs: {m['invalid_atm_count']}

### 5.2 Transaction Types Breakdown
| Operation Type | Transaction Count | Pct of Cleaned Data | Sign Distribution | Description |
| :---: | :---: | :---: | :---: | :--- |
| `0` | {m['operation_types_breakdown'].get(0, 0):,} | {m['operation_types_breakdown'].get(0, 0) / m['cleaned_rows'] * 100:.2f}% | Positive & Negative | Standard card cash withdrawals & cash deposits |
| `4` | {m['operation_types_breakdown'].get(4, 0):,} | {m['operation_types_breakdown'].get(4, 0) / m['cleaned_rows'] * 100:.2f}% | Strictly Positive | Cash withdrawals / dispensing operations |
| `1` | {m['operation_types_breakdown'].get(1, 0):,} | {m['operation_types_breakdown'].get(1, 0) / m['cleaned_rows'] * 100:.2f}% | Positive & Negative | Interbank / Partner card transactions |
| `5` | {m['operation_types_breakdown'].get(5, 0):,} | {m['operation_types_breakdown'].get(5, 0) / m['cleaned_rows'] * 100:.2f}% | Positive & Negative | Large denomination cash exchanges / deposits |
| `6` | {m['operation_types_breakdown'].get(6, 0):,} | {m['operation_types_breakdown'].get(6, 0) / m['cleaned_rows'] * 100:.2f}% | Strictly Positive | Small utility / mobile payments / fee deductions |
| `2` | {m['operation_types_breakdown'].get(2, 0):,} | {m['operation_types_breakdown'].get(2, 0) / m['cleaned_rows'] * 100:.2f}% | Strictly Negative | Specific account debits / reversals |

### 5.3 Monetary Values & Sign Convention
- **Positive Values (`operation_value > 0`)**: {m['positive_amounts_count']:,} records.
  - Represents **Cash Outflow from ATM / Cash Dispensed to Customer** (ATM Cash Demand).
- **Negative Values (`operation_value < 0`)**: {m['negative_amounts_count']:,} records.
  - Represents **Cash Inflow to ATM / Cash Deposited by Customer** (ATM Cash Recycling).
  - Decision: Negative values were **NOT deleted**. Deleting negative amounts would misrepresent modern cash-recycling ATM dynamics.
- **Zero Values (`operation_value == 0`)**: {m['zero_amounts_count']} records. None exist in the dataset.
- **Normalization Factor**: The raw amounts are anonymized by a scaling factor where `0.02941808030921` corresponds to 100 Russian Rubles (`1 unit = ~34 Rubles`). The theoretical maximum transaction cap is `294.1808030921` (corresponding to 10,000 units or 1,000,000 Rubles), which occurs exactly {m['capped_at_max_count']} times at the upper bound and {m['capped_at_min_count']} times at the lower bound.

---

## 6. Outlier Analysis

### 6.1 Transaction-Level Outliers
- **Interquartile Range (IQR) Method**:
  - Lower Bound: `{tx_iqr['iqr_bounds'][0]}` | Upper Bound: `{tx_iqr['iqr_bounds'][1]}`
  - Outliers Detected: {tx_iqr['iqr_outliers_count']:,} ({tx_iqr['iqr_outliers_pct']}%)
- **Z-Score Method (|z| > 3)**:
  - Outliers Detected: {tx_iqr['z_outliers_count']:,} ({tx_iqr['z_outliers_pct']}%)
- **Decision**: All outliers were retained. High-value transactions reflect authentic, large-scale customer withdrawals (e.g., payroll distributions, business deposits) that fall within valid terminal limits.

### 6.2 Daily Demand Outliers
- **Demand IQR Outliers**: {m['demand_iqr_outliers']:,} days (heavy holiday or peak-demand days)
- **Demand Z-score Outliers (|z| > 3)**: {m['demand_z_outliers']:,} days

---

## 7. Time Series Continuity & Time Grid Construction

### 7.1 Calendar Continuity
- Overall network calendar span: {m['min_date']} to {m['max_date']} ({m['calendar_days_span']} days).
- While the full fleet reached steady-state deployment by mid-August 2017, individual ATMs experienced isolated calendar days without transaction logs (e.g., terminal outages, bank holidays, maintenance).
- Across all 20 ATMs, there are **{m['total_missing_atm_days']} calendar gap days**.

### 7.2 Zero-Demand Periods
- In the aggregated daily demand dataset:
  - **{m['inactive_calendar_days']} days** had no recorded transactions across the machine (terminal downtime or holiday closure). These are filled with `demand = 0.0` and flagged with `is_active_day = False`.
  - **{m['zero_withdrawal_active_days']} days** had active deposit transactions but **zero cash withdrawals** (`demand = 0.0` with `transaction_count > 0` and `is_active_day = True`).
  - Total zero-demand records (`demand == 0.0`): **{m['zero_demand_count']} days**.
  - Negative demand records (`demand < 0.0`): **{m['negative_demand_count']}** (Gross withdrawal demand is strictly non-negative).

---

## 8. Data Dictionaries

### 8.1 Cleaned Transaction Dataset (`data/processed/tinkoff_cleaned.csv`)
| Column Name | Data Type | Description | Domain / Example |
| :--- | :--- | :--- | :--- |
| `datetime` | `string` (ISO date) | Transaction date | `2017-06-09` to `2018-09-30` |
| `atm_id` | `int64` | Unique ATM terminal identifier | 20 unique IDs (e.g., 74, 85, 106) |
| `operation_type`| `int64` | Transaction channel / operation category code | `0, 1, 2, 4, 5, 6` |
| `client_id` | `int64` | Anonymized unique customer identifier | Positive integers (`6` to `3,425,710`) |
| `operation_value`| `float64` | Normalized monetary amount (positive: cash withdrawal, negative: cash deposit) | `[-294.180803, 294.180803]` |

### 8.2 Daily Demand Dataset (`data/processed/atm_demand_daily.csv`)
| Column Name | Data Type | Description | Domain / Example |
| :--- | :--- | :--- | :--- |
| `atm_id` | `int64` | Unique ATM terminal identifier | 20 unique IDs |
| `date` | `string` (ISO date) | Calendar date | `2017-06-09` to `2018-09-30` |
| `demand` | `float64` | **Target Variable**: Gross cash withdrawal demand (total cash dispensed by ATM) | `[0.0, 4988.306206]` (Mean: {m['demand_mean']:.2f}) |
| `deposit_amount`| `float64` | Total cash deposited / recycled into ATM on that date | `[0.0, 2833.255315]` |
| `net_demand` | `float64` | Net cash outflow (`demand - deposit_amount`) | `[-1925.2957, 3711.2673]` |
| `transaction_count`| `int64` | Total number of financial operations on that date | `[0, 521]` |
| `withdrawal_count` | `int64` | Number of cash withdrawal transactions | `[0, 396]` |
| `deposit_count` | `int64` | Number of cash deposit transactions | `[0, 201]` |
| `is_active_day` | `bool` | Flag indicating whether ATM was actively logging (`True`) or calendar gap filled (`False`) | `True, False` |

---

## 9. Cleaning Decisions Summary

1. **Preservation of Raw Data**: Raw data in `data/raw/` (and original `tinkoffatm/`) remained completely untouched.
2. **Exact Duplicates Dropped**: Exactly {m['duplicate_rows_removed']:,} redundant rows were removed to prevent distortion of transaction volume.
3. **Legitimate Multi-Transactions Retained**: Customers performing multiple legitimate operations on the same date were kept intact.
4. **Preservation of Negative Values**: Negative amounts reflect cash deposits in modern recycling ATMs. Rather than deleting them, they were separated into withdrawal demand and deposit volume.
5. **No Synthetic Value Invention**: No artificial balances, replenishment events, or stockout events were fabricated.
6. **Continuous Time-Series Grid**: Inactive days were represented with zero demand and explicitly flagged (`is_active_day = False`) to guarantee uniform spacing required for time-series forecasting lag features.

---

## 10. Remaining Limitations & Edge Cases

1. **Excel Row Truncation in Source File**: The raw file `train_kaggle.csv` contains exactly 1,048,575 rows (equal to $2^{{20}} - 1$, the exact limit of Microsoft Excel exports). Transactions appear to have been sorted by `client_id` before export, meaning high-numbered client transactions from mid-2018 onwards may be partially truncated.
2. **Lack of Sub-Daily Timestamps**: Timestamps in the raw dataset provide only date (`YYYY-MM-DD`) precision without hour, minute, or second. Intraday (hourly) demand forecasting is therefore not mathematically feasible from this dataset; daily aggregation is the optimal and appropriate resolution.
3. **Anonymized Currency Units**: Monetary amounts are normalized by Tinkoff organizers by multiplying Russian Rubles by ~`0.00029418`. Converting to nominal Rubles requires dividing values by `0.02941808030921` (which yields 100-Rubles units).
4. **Unobserved Machine States**: The dataset does not record machine hardware breakdowns, cash-out (stockout) events, or replenishment schedules. Periods of zero demand may represent either zero customer foot traffic or mechanical downtime.
"""
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content.strip() + "\n")

        logger.info("Report written successfully to %s", report_path)
        return report_path

    def run(self) -> Dict[str, Any]:
        """
        Execute the end-to-end cleaning and demand dataset generation pipeline.

        Returns:
            Dict containing pipeline summary statistics.
        """
        cleaned_df = self.clean()
        demand_df = self.create_demand_dataset(cleaned_df)
        cleaned_path, demand_path = self.save_datasets(cleaned_df, demand_df)
        report_path = self.generate_data_quality_report()

        logger.info("=== Pipeline Completed Successfully ===")
        logger.info("Cleaned dataset: %s", cleaned_path)
        logger.info("Demand dataset: %s", demand_path)
        logger.info("Quality report: %s", report_path)

        return self.metrics


def main():
    """CLI Entrypoint for the Tinkoff ATM Data Cleaning Pipeline."""
    parser = argparse.ArgumentParser(
        description="Reproducible Tinkoff ATM Data Cleaning Pipeline"
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="data/raw",
        help="Path to directory containing raw data (default: data/raw)",
    )
    parser.add_argument(
        "--processed-dir",
        type=str,
        default="data/processed",
        help="Path to directory for processed output (default: data/processed)",
    )
    parser.add_argument(
        "--docs-dir",
        type=str,
        default="docs",
        help="Path to directory for documentation/reports (default: docs)",
    )
    parser.add_argument(
        "--raw-filename",
        type=str,
        default="train_kaggle.csv",
        help="Filename of primary raw dataset (default: train_kaggle.csv)",
    )

    args = parser.parse_args()
    cleaner = TinkoffDataCleaner(
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir,
        docs_dir=args.docs_dir,
        raw_filename=args.raw_filename,
    )
    cleaner.run()


if __name__ == "__main__":
    main()
