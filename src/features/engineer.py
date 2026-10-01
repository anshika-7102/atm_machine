"""
Feature Engineering Module for ATM Cash Demand Predictor.

Constructs high-signal predictive features without data leakage:
1. Historical Lags: t-1, t-2, t-3, t-7 (weekly seasonality), t-14, t-21, t-28.
2. Rolling Window Statistics: 3, 7, 14, 30 days moving average and volatility (std).
3. Momentum & Ratio Features: Short-term vs weekly trends.
4. Cyclical Temporal Encodings: Sine/Cosine of Day of Week and Month.
5. Categorical Encodings: Location type, city, weather conditions.
"""

import argparse
import logging
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("FeatureEngineer")


class FeatureEngineer:
    """Reproducible feature engineering pipeline for multi-ATM demand forecasting."""

    def __init__(
        self,
        input_path: str = "data/processed/atm_demand_enriched.csv",
        output_path: str = "data/processed/atm_features_engineered.csv",
    ):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.feature_columns: List[str] = []

    def load_data(self) -> pd.DataFrame:
        """Load enriched dataset and prepare datetime index."""
        if not self.input_path.exists():
            raise FileNotFoundError(f"Enriched dataset not found at: {self.input_path}")
        logger.info("Loading enriched data from %s...", self.input_path)
        df = pd.read_csv(self.input_path)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(by=["atm_id", "date"]).reset_index(drop=True)
        return df

    def create_lags(self, df: pd.DataFrame, lags: List[int] = [1, 2, 3, 7, 14, 21, 28]) -> pd.DataFrame:
        """Generate historical demand lags per ATM."""
        logger.info("Generating lag features %s...", lags)
        for lag in lags:
            df[f"lag_{lag}"] = df.groupby("atm_id")["demand"].shift(lag)
        return df

    def create_rolling_stats(self, df: pd.DataFrame, windows: List[int] = [3, 7, 14, 30]) -> pd.DataFrame:
        """
        Generate moving averages and standard deviations per ATM.
        Uses shifted series to guarantee zero target leakage.
        """
        logger.info("Generating rolling window statistics %s...", windows)
        for w in windows:
            shifted = df.groupby("atm_id")["demand"].shift(1)
            df[f"rolling_mean_{w}"] = (
                shifted.groupby(df["atm_id"])
                .rolling(window=w, min_periods=w)
                .mean()
                .reset_index(drop=True)
            )
            df[f"rolling_std_{w}"] = (
                shifted.groupby(df["atm_id"])
                .rolling(window=w, min_periods=w)
                .std()
                .reset_index(drop=True)
            )
        return df

    def create_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate demand momentum and ratio features."""
        logger.info("Generating momentum and ratio interactions...")
        df["demand_ratio_7"] = df["lag_1"] / (df["rolling_mean_7"] + 1e-4)
        df["demand_diff_1_7"] = df["lag_1"] - df["lag_7"]
        df["demand_diff_7_14"] = df["lag_7"] - df["lag_14"]
        return df

    def create_cyclical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Encode cyclical calendar attributes using sine/cosine transforms."""
        logger.info("Encoding cyclical calendar features (sin/cos)...")
        df["sin_dow"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
        df["cos_dow"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
        df["sin_month"] = np.sin(2 * np.pi * df["month"] / 12)
        df["cos_month"] = np.cos(2 * np.pi * df["month"] / 12)
        return df

    def encode_categoricals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert categorical features to numeric codes."""
        cat_cols = ["location_type", "city", "weather_condition", "risk_level"]
        for col in cat_cols:
            if col in df.columns:
                df[f"{col}_encoded"] = pd.factorize(df[col])[0]

        # Convert booleans to int
        for col in df.select_dtypes(include="bool").columns:
            df[col] = df[col].astype(int)

        return df

    def process(self) -> Tuple[pd.DataFrame, List[str]]:
        """Execute full feature engineering pipeline."""
        df = self.load_data()
        df = self.create_lags(df)
        df = self.create_rolling_stats(df)
        df = self.create_momentum_features(df)
        df = self.create_cyclical_features(df)
        df = self.encode_categoricals(df)

        # Drop warmup rows where lag_28 or rolling_mean_30 is NaN
        df_clean = df.dropna(subset=["lag_28", "rolling_mean_30"]).copy()

        # Identify numerical feature columns for model training
        exclude_cols = [
            "demand",
            "net_demand",
            "deposit_amount",
            "transaction_count",
            "withdrawal_count",
            "deposit_count",
            "date",
            "atm_name",
            "address",
            "holiday_name",
            "weather_condition",
            "location_type",
            "city",
            "risk_level",
            "installation_date",
            "status",
        ]
        self.feature_columns = [
            c
            for c in df_clean.select_dtypes(include=np.number).columns
            if c not in exclude_cols
        ]

        logger.info(
            "Feature engineering complete. Output shape: %s (%d modeling features)",
            df_clean.shape,
            len(self.feature_columns),
        )

        df_clean.to_csv(self.output_path, index=False)
        logger.info("Saved engineered dataset to: %s", self.output_path)
        return df_clean, self.feature_columns


def main():
    parser = argparse.ArgumentParser(description="ATM Demand Feature Engineering Pipeline")
    parser.add_argument(
        "--input",
        type=str,
        default="data/processed/atm_demand_enriched.csv",
        help="Input enriched dataset path",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/processed/atm_features_engineered.csv",
        help="Output engineered dataset path",
    )
    args = parser.parse_args()

    fe = FeatureEngineer(input_path=args.input, output_path=args.output)
    fe.process()


if __name__ == "__main__":
    main()
