"""
Pydantic Schemas for FastAPI REST API endpoints.
Defines strict request/response data contracts matching Synopsis specifications.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    role: str
    user_role: str
    username: str


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserProfile(BaseModel):
    username: str
    full_name: str
    email: str
    role: str
    is_active: bool


# --- ATM Schemas ---
class ATMItem(BaseModel):
    atm_id: int
    atm_name: str
    city: str
    address: str
    latitude: float
    longitude: float
    location_type: str
    current_cash: float
    max_cash_capacity: float
    min_safety_stock: float
    capacity_utilization_pct: float
    risk_level: str
    last_updated: str


class ATMDetail(ATMItem):
    avg_daily_demand: float
    max_daily_demand: float
    is_cash_recycler: bool
    status: str


# --- Forecast Schemas ---
class DailyForecastItem(BaseModel):
    day_ahead: int
    date: str
    day_name: str
    predicted_demand: float
    lower_bound_90pct: float
    upper_bound_90pct: float


class ForecastResponse(BaseModel):
    atm_id: int
    forecast_generated_at: str
    horizon_days: int
    total_predicted_demand: float
    average_daily_demand: float
    daily_forecasts: List[DailyForecastItem]


# --- Risk Schemas ---
class RiskResponse(BaseModel):
    atm_id: int
    atm_name: str
    city: str
    current_cash: float
    min_safety_stock: float
    planning_window_days: int
    forecasted_demand: float
    cash_out_probability: float
    risk_level: str
    days_until_cashout: Optional[int] = None
    risk_explanation: str


# --- Replenishment Schemas ---
class ReplenishmentResponse(BaseModel):
    atm_id: int
    atm_name: str
    city: str
    location_type: str
    current_cash: float
    max_cash_capacity: float
    min_safety_stock: float
    forecasted_demand: float
    recommended_refill: float
    new_projected_cash: float
    risk_level: str
    priority: str
    urgency_score: int
    recommendation_reason: str


class ReplenishmentApprovalRequest(BaseModel):
    atm_id: int
    approved_amount: float
    notes: Optional[str] = "Approved by Operations Manager"


# --- Dashboard KPI & Alert Schemas ---
class DashboardSummaryResponse(BaseModel):
    total_atms: int
    total_cash_in_network: float
    network_cash_capacity: float
    network_utilization_pct: float
    forecasted_24h_network_demand: float
    high_risk_atms_count: int
    medium_risk_atms_count: int
    low_risk_atms_count: int
    pending_refill_orders: int
    total_replenishment_needed: float
    system_status: str


class AlertItem(BaseModel):
    alert_id: str
    atm_id: int
    atm_name: str
    severity: str
    message: str
    action_required: str


class HealthCheckResponse(BaseModel):
    status: str
    app_name: str
    version: str
    model_loaded: bool
    atms_active: int
