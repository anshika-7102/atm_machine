"""
ATM Cash Demand Predictor: Machine Learning & Time-Series Training Pipeline.
Standalone script mirror of notebooks/atm_demand_kaggle_training.ipynb.
"""

import os
import sys
import glob
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    lgb = None

warnings.filterwarnings('ignore')

print("="*70)
print("1. ENVIRONMENT & DATA INGESTION")
print("="*70)

possible_paths = [
    "/kaggle/input/atm-cash-demand-enriched-dataset/atm_demand_enriched.csv",
    "/kaggle/input/*/atm_demand_enriched.csv",
    "data/processed/atm_demand_enriched.csv",
    "../data/processed/atm_demand_enriched.csv",
    "data/kaggle_bundle/atm_demand_enriched.csv",
]

data_path = None
for p in possible_paths:
    matched = glob.glob(p)
    if matched:
        data_path = matched[0]
        break

if data_path is None:
    raise FileNotFoundError("Could not locate atm_demand_enriched.csv.")

print(f"Loaded Dataset from: {data_path}")
df = pd.read_csv(data_path)
print(f"Dataset Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
print(f"Unique ATMs: {df['atm_id'].nunique()}")
print(f"Date Range: {df['date'].min()} to {df['date'].max()}")

print("\n" + "="*70)
print("2. FEATURE ENGINEERING (LAGS & ROLLING STATS)")
print("="*70)

df['date'] = pd.to_datetime(df['date'])
df = df.sort_values(by=['atm_id', 'date']).reset_index(drop=True)

# Generate Lag Features per ATM
lag_days = [1, 2, 3, 7, 14, 21, 28]
for lag in lag_days:
    df[f'lag_{lag}'] = df.groupby('atm_id')['demand'].shift(lag)

# Generate Rolling Statistics (using shifted series to avoid target leakage)
for window in [3, 7, 14, 30]:
    shifted = df.groupby('atm_id')['demand'].shift(1)
    df[f'rolling_mean_{window}'] = shifted.groupby(df['atm_id']).rolling(window=window, min_periods=window).mean().reset_index(drop=True)
    df[f'rolling_std_{window}'] = shifted.groupby(df['atm_id']).rolling(window=window, min_periods=window).std().reset_index(drop=True)

# Interaction / Momentum features
df['demand_ratio_7'] = df['lag_1'] / (df['rolling_mean_7'] + 1e-4)
df['demand_diff_1_7'] = df['lag_1'] - df['lag_7']
df['demand_diff_7_14'] = df['lag_7'] - df['lag_14']

# Cyclical encoding
df['sin_dow'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
df['cos_dow'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
df['sin_month'] = np.sin(2 * np.pi * df['month'] / 12)
df['cos_month'] = np.cos(2 * np.pi * df['month'] / 12)

# Convert categorical variables to integer codes
cat_cols = ['location_type', 'city', 'weather_condition', 'risk_level']
for col in cat_cols:
    if col in df.columns:
        df[f'{col}_encoded'] = pd.factorize(df[col])[0]

# Convert booleans to int
for col in df.select_dtypes(include='bool').columns:
    df[col] = df[col].astype(int)

# Drop warmup rows
df_model = df.dropna(subset=['lag_28', 'rolling_mean_30']).copy()
print(f"Shape after feature engineering: {df_model.shape}")
print(f"Date range: {df_model['date'].min().strftime('%Y-%m-%d')} to {df_model['date'].max().strftime('%Y-%m-%d')}")

print("\n" + "="*70)
print("3. TIME-BASED TRAIN / VAL / TEST SPLIT")
print("="*70)

exclude_cols = [
    'demand', 'net_demand', 'deposit_amount', 'transaction_count',
    'withdrawal_count', 'deposit_count'
]
feature_cols = [
    c for c in df_model.select_dtypes(include=np.number).columns 
    if c not in exclude_cols
]
print(f"Total modeling features: {len(feature_cols)}")
print("Sample features:", feature_cols[:10])

train_mask = df_model['date'] <= '2018-06-30'
val_mask = (df_model['date'] >= '2018-07-01') & (df_model['date'] <= '2018-08-15')
test_mask = df_model['date'] >= '2018-08-16'

X_train = df_model.loc[train_mask, feature_cols]
y_train = df_model.loc[train_mask, 'demand']

X_val = df_model.loc[val_mask, feature_cols]
y_val = df_model.loc[val_mask, 'demand']

X_test = df_model.loc[test_mask, feature_cols]
y_test = df_model.loc[test_mask, 'demand']

print(f"Train Set: {len(X_train):,} rows")
print(f"Val Set:   {len(X_val):,} rows")
print(f"Test Set:  {len(X_test):,} rows")

def calculate_metrics(y_true, y_pred, model_name="Model"):
    y_true = np.array(y_true)
    y_pred = np.maximum(np.array(y_pred), 0.0)
    
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    
    total_demand = np.sum(y_true)
    wape = (np.sum(np.abs(y_true - y_pred)) / total_demand) * 100 if total_demand > 0 else 0.0
    
    nonzero_mask = y_true > 1.0
    mape = np.mean(np.abs((y_true[nonzero_mask] - y_pred[nonzero_mask]) / y_true[nonzero_mask])) * 100 if np.any(nonzero_mask) else 0.0
    accuracy = max(0.0, 100.0 - wape)
    
    return {
        "Model": model_name,
        "MAE": round(mae, 2),
        "RMSE": round(rmse, 2),
        "WAPE (%)": round(wape, 2),
        "MAPE (%)": round(mape, 2),
        "Forecast Accuracy (%)": round(accuracy, 2)
    }

leaderboard = []

print("\n" + "="*70)
print("4. BASELINE BENCHMARK MODELS")
print("="*70)

# Naive Persistence (Lag 1)
y_pred_naive = X_test['lag_1']
leaderboard.append(calculate_metrics(y_test, y_pred_naive, "Baseline: Naive (t-1)"))

# Seasonal Naive (Lag 7)
y_pred_snaive = X_test['lag_7']
leaderboard.append(calculate_metrics(y_test, y_pred_snaive, "Baseline: Seasonal Naive (t-7)"))

# 7-Day Moving Average
y_pred_ma7 = X_test['rolling_mean_7']
leaderboard.append(calculate_metrics(y_test, y_pred_ma7, "Baseline: 7-Day Moving Avg"))

print(pd.DataFrame(leaderboard).to_string(index=False))

print("\n" + "="*70)
print("5. MACHINE LEARNING MODELS TRAINING")
print("="*70)

# Random Forest
print("Training Random Forest...")
rf_model = RandomForestRegressor(n_estimators=150, max_depth=12, min_samples_split=4, random_state=42, n_jobs=-1)
rf_model.fit(X_train, y_train)
y_pred_rf = rf_model.predict(X_test)
leaderboard.append(calculate_metrics(y_test, y_pred_rf, "Random Forest"))

# LightGBM
if HAS_LIGHTGBM:
    print("Training LightGBM...")
    lgb_model = lgb.LGBMRegressor(
        n_estimators=500, learning_rate=0.03, num_leaves=31, max_depth=8,
        subsample=0.8, colsample_bytree=0.8, random_state=42, verbose=-1
    )
    lgb_model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
    )
    y_pred_lgb = lgb_model.predict(X_test)
    leaderboard.append(calculate_metrics(y_test, y_pred_lgb, "LightGBM"))
else:
    print("LightGBM not installed locally (pre-installed on Kaggle). Skipping LightGBM local run.")

# XGBoost
print("Training XGBoost Regressor...")
xgb_model = xgb.XGBRegressor(
    n_estimators=600, learning_rate=0.025, max_depth=6, subsample=0.85,
    colsample_bytree=0.85, gamma=0.1, random_state=42, n_jobs=-1, early_stopping_rounds=35
)
xgb_model.fit(
    X_train, y_train,
    eval_set=[(X_train, y_train), (X_val, y_val)],
    verbose=False
)
y_pred_xgb = xgb_model.predict(X_test)
leaderboard.append(calculate_metrics(y_test, y_pred_xgb, "XGBoost (Tuned)"))

print("\n" + "="*70)
print("6. FINAL EVALUATION LEADERBOARD")
print("="*70)
leaderboard_df = pd.DataFrame(leaderboard).sort_values(by="MAE").reset_index(drop=True)
print(leaderboard_df.to_string(index=False))

print("\n" + "="*70)
print("7. EXPORTING PRODUCTION ARTIFACTS")
print("="*70)
output_dir = Path("/kaggle/working") if Path("/kaggle/working").exists() else Path("models")
output_dir.mkdir(parents=True, exist_ok=True)

# 1. Model
model_save_path = output_dir / "best_forecasting_model.joblib"
joblib.dump(xgb_model, model_save_path)
print(f"Saved model: {model_save_path}")

# 2. Features
features_save_path = output_dir / "feature_columns.json"
with open(features_save_path, "w") as f:
    json.dump(feature_cols, f, indent=2)
print(f"Saved feature columns: {features_save_path}")

# 3. Metrics
metrics_save_path = output_dir / "model_metrics.json"
leaderboard_df.to_json(metrics_save_path, orient="records", indent=2)
print(f"Saved metrics: {metrics_save_path}")

# 4. Predictions
test_results = df_model.loc[test_mask, ['atm_id', 'date', 'demand']].copy()
test_results['predicted_demand'] = np.maximum(y_pred_xgb, 0.0).round(2)
pred_save_path = output_dir / "test_predictions.csv"
test_results.to_csv(pred_save_path, index=False)
print(f"Saved predictions: {pred_save_path}")

print("\n=== Pipeline Successfully Finished ===")
