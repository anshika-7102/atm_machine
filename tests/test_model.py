"""Unit tests for ModelTrainer and DemandPredictor."""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from src.models.train import ModelTrainer
from src.models.predict import DemandPredictor


def test_calculate_metrics():
    trainer = ModelTrainer()
    y_true = np.array([100.0, 200.0, 300.0, 400.0])
    y_pred = np.array([110.0, 190.0, 310.0, 390.0])
    
    metrics = trainer.calculate_metrics(y_true, y_pred, "TestModel")
    assert metrics["MAE"] == 10.0
    assert metrics["WAPE (%)"] == 4.0
    assert metrics["Forecast Accuracy (%)"] == 96.0


def test_production_artifacts_exist():
    models_dir = Path("models")
    docs_dir = Path("docs")

    assert (models_dir / "best_forecasting_model.joblib").exists()
    assert (models_dir / "feature_columns.json").exists()
    assert (models_dir / "model_metrics.json").exists()
    assert (models_dir / "test_predictions.csv").exists()
    assert (docs_dir / "MODEL_EVALUATION_REPORT.md").exists()
    assert (docs_dir / "forecast_vs_actual_samples.png").exists()
    assert (docs_dir / "feature_importance.png").exists()


def test_demand_predictor_inference():
    predictor = DemandPredictor()
    forecast = predictor.forecast_atm(atm_id=74, days_ahead=7)

    assert forecast["atm_id"] == 74
    assert forecast["horizon_days"] == 7
    assert len(forecast["daily_forecasts"]) == 7
    assert forecast["total_predicted_demand"] > 0

    first_day = forecast["daily_forecasts"][0]
    assert "date" in first_day
    assert "predicted_demand" in first_day
    assert first_day["predicted_demand"] >= 0
    assert first_day["upper_bound_90pct"] >= first_day["predicted_demand"]
