"""
Inference & Prediction Service for ATM Cash Demand Predictor.

Provides fast, on-demand multi-horizon demand forecasting (1-day, 3-day, 7-day):
- Loads serialized production model (best_forecasting_model.joblib).
- Generates recursive or multi-step forecasts per ATM terminal.
- Computes 90% confidence prediction intervals (uncertainty bounds).
- Serves the downstream FastAPI REST endpoints and React Dashboard.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import joblib
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("DemandPredictor")


class DemandPredictor:
    """Production inference engine for ATM cash demand forecasting."""

    def __init__(
        self,
        model_path: str = "models/best_forecasting_model.joblib",
        features_path: str = "models/feature_columns.json",
        dataset_path: str = "data/processed/atm_features_engineered.csv",
    ):
        self.model_path = Path(model_path)
        self.features_path = Path(features_path)
        self.dataset_path = Path(dataset_path)

        if not self.model_path.exists():
            raise FileNotFoundError(f"Trained model not found at {self.model_path}. Run train.py first!")
        if not self.features_path.exists():
            raise FileNotFoundError(f"Feature schema not found at {self.features_path}.")

        self.model = joblib.load(self.model_path)
        with open(self.features_path, "r", encoding="utf-8") as f:
            self.feature_cols = json.load(f)

        logger.info(
            "Initialized DemandPredictor with model %s and %d features.",
            self.model_path.name,
            len(self.feature_cols),
        )

    def forecast_atm(self, atm_id: int, days_ahead: int = 7) -> Dict[str, Any]:
        """
        Generate multi-day ahead demand forecast for a given ATM.

        Args:
            atm_id: Unique ATM identifier.
            days_ahead: Number of days to forecast (1 to 14, default: 7).

        Returns:
            Dict containing ATM forecast array, summary totals, and uncertainty bounds.
        """
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found at {self.dataset_path}")

        df = pd.read_csv(self.dataset_path)
        atm_data = df[df["atm_id"] == atm_id].sort_values("date").reset_index(drop=True)

        if len(atm_data) == 0:
            raise ValueError(f"ATM ID {atm_id} not found in historical data.")

        last_row = atm_data.iloc[-1]
        last_date = pd.to_datetime(last_row["date"])

        # Base residual uncertainty estimate (RMSE proxy ~ 15-20% standard error)
        std_error = float(atm_data["demand"].std()) * 0.35

        forecasts = []
        total_predicted = 0.0

        for i in range(1, days_ahead + 1):
            target_date = last_date + pd.Timedelta(days=i)
            dow = target_date.weekday()

            # Construct feature vector based on most recent historical state
            row_features = last_row[self.feature_cols].copy()
            # Update date-specific features
            if "day_of_week" in row_features:
                row_features["day_of_week"] = dow
            if "is_weekend" in row_features:
                row_features["is_weekend"] = 1 if dow >= 5 else 0
            if "sin_dow" in row_features:
                row_features["sin_dow"] = np.sin(2 * np.pi * dow / 7)
            if "cos_dow" in row_features:
                row_features["cos_dow"] = np.cos(2 * np.pi * dow / 7)

            X_input = pd.DataFrame([row_features])[self.feature_cols]
            pred_val = float(np.maximum(self.model.predict(X_input)[0], 0.0))
            pred_val = round(pred_val, 2)
            total_predicted += pred_val

            # Expanding uncertainty bounds over horizon
            horizon_factor = np.sqrt(i)
            lower_bound = round(max(0.0, pred_val - 1.645 * std_error * horizon_factor), 2)
            upper_bound = round(pred_val + 1.645 * std_error * horizon_factor, 2)

            forecasts.append(
                {
                    "day_ahead": i,
                    "date": target_date.strftime("%Y-%m-%d"),
                    "day_name": target_date.strftime("%A"),
                    "predicted_demand": pred_val,
                    "lower_bound_90pct": lower_bound,
                    "upper_bound_90pct": upper_bound,
                }
            )

        result = {
            "atm_id": int(atm_id),
            "forecast_generated_at": last_date.strftime("%Y-%m-%d"),
            "horizon_days": days_ahead,
            "total_predicted_demand": round(total_predicted, 2),
            "average_daily_demand": round(total_predicted / days_ahead, 2),
            "daily_forecasts": forecasts,
        }
        return result


def main():
    parser = argparse.ArgumentParser(description="Generate ATM Demand Forecast")
    parser.add_argument("--atm-id", type=int, default=74, help="ATM terminal ID (default: 74)")
    parser.add_argument("--days", type=int, default=7, help="Forecast horizon in days (default: 7)")
    args = parser.parse_args()

    predictor = DemandPredictor()
    forecast = predictor.forecast_atm(atm_id=args.atm_id, days_ahead=args.days)
    print(json.dumps(forecast, indent=2))


if __name__ == "__main__":
    main()
