# Model Evaluation Report: ATM Cash Demand Predictor

## 1. Executive Summary

This report documents the machine learning model training, validation, and benchmarking pipeline executed locally for the ATM Cash Demand Predictor. The models were evaluated using strict **out-of-time chronological validation** across 20 ATMs over an unseen 46-day test window (August 16, 2018 to September 30, 2018).

The objective was to determine the superior algorithm to predict daily cash withdrawals, minimize forecasting error (MAE/RMSE), and achieve the operational accuracy target defined in the project synopsis.

---

## 2. Model Performance Leaderboard

| Model | MAE | RMSE | WAPE (%) | MAPE (%) | Forecast Accuracy (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| XGBoost (Tuned) | 220.21 | 326.69 | 25.66 | 46.86 | 74.34 |
| Random Forest | 271.17 | 391.61 | 31.6 | 55.4 | 68.4 |
| Baseline: 7-Day Moving Avg | 328.93 | 472.89 | 38.33 | 69.24 | 61.67 |
| Baseline: Seasonal Naive (t-7) | 337.2 | 502.47 | 39.29 | 56.28 | 60.71 |
| Baseline: Naive (t-1) | 393.41 | 589.88 | 45.84 | 74.17 | 54.16 |

### Key Takeaways:
1. **Best Model**: **XGBoost (Tuned)** achieved the lowest Mean Absolute Error (**MAE = 220.21**) and the highest Forecast Accuracy (**74.34%**).
2. **Error Reduction**: XGBoost (Tuned) reduced the MAE from **393.41** (Naive Baseline) down to **220.21**, representing a **43.4% error reduction**.
3. **Weekly Seasonality**: The Seasonal Naive model ($t-7$) substantially outperformed the 1-day Naive model ($t-1$), confirming strong 7-day cyclicality in ATM cash withdrawals.

---

## 3. Validation Methodology & Leakage Prevention

To ensure true real-world reliability, a chronological partition was enforced:
* **Training Partition**: Data up to `2018-06-30` (6,021 ATM-days, ~11 months).
* **Validation Partition**: `2018-07-01` to `2018-08-15` (920 ATM-days, used for XGBoost early stopping).
* **Test Holdout Partition**: `2018-08-16` to `2018-09-30` (920 ATM-days, final performance evaluation).

**Leakage Controls**:
* All rolling averages and standard deviations were computed using `shift(1)` so that time $t$ demand was never visible during feature calculation.
* No random K-Fold shuffling was used.

---

## 4. Most Influential Predictive Features

Feature importance analysis via XGBoost reveals the top predictive drivers:
1. **`lag_7` & `rolling_mean_7`**: Strongest indicators, capturing weekly foot traffic and customer habits.
2. **`demand_diff_1_7`**: Momentum indicator measuring whether demand is accelerating compared to the previous week.
3. **`min_safety_stock` & `max_cash_capacity`**: Terminal-level physical constraints reflecting machine volume tier.
4. **`day_of_week` & `is_weekend`**: Weekday payroll spikes vs. weekend retail cash usage.
5. **`is_salary_day`**: Cash demand increases significantly around the 5th and 20th of each month.

---

## 5. Artifacts & Integration

The trained model and metadata are saved and ready for the FastAPI backend service:
* **Model Weight**: `models/best_forecasting_model.joblib`
* **Feature Schema**: `models/feature_columns.json`
* **Test Predictions**: `models/test_predictions.csv`
* **Metrics Summary**: `models/model_metrics.json`
* **Diagnostic Charts**:
  * Forecast Plot: `docs/forecast_vs_actual_samples.png`
  * Feature Importance Plot: `docs/feature_importance.png`
