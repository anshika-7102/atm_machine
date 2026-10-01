"""
REST API Routes for ATM Cash Demand Predictor.

Implements all endpoints defined in Section 5 of the project synopsis:
- Auth: /auth/login, /auth/token, /auth/me
- ATMs: /atms, /atms/{atm_id}
- Forecasting: /forecast/{atm_id}
- Risk: /risk/{atm_id}
- Replenishment: /replenishment/{atm_id}, /replenishment/queue, /replenishment/approve
- Dashboard & Alerts: /dashboard/summary, /alerts, /reports
"""

import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm

from src.api.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    require_role,
)
from src.api.schemas import (
    AlertItem,
    ATMDetail,
    ATMItem,
    DashboardSummaryResponse,
    ForecastResponse,
    ReplenishmentApprovalRequest,
    ReplenishmentResponse,
    RiskResponse,
    Token,
    UserLogin,
    UserProfile,
)
from src.services.risk_engine import RiskAndReplenishmentEngine

router = APIRouter(prefix="/api/v1")

# Lazy-loaded Risk & Replenishment Engine singleton
_engine: Optional[RiskAndReplenishmentEngine] = None


def get_engine() -> RiskAndReplenishmentEngine:
    global _engine
    if _engine is None:
        _engine = RiskAndReplenishmentEngine()
    return _engine


# ============================================================================
# 1. AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/auth/token", response_model=Token, tags=["Authentication"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 standard form-encoded token endpoint (for Swagger UI)."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(data={"sub": user["username"], "role": user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": 120,
        "role": user["role"],
        "user_role": user["role"],
        "username": user["username"],
    }


@router.post("/auth/login", response_model=Token, tags=["Authentication"])
async def login(credentials: UserLogin):
    """JSON login endpoint for React Frontend."""
    user = authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token(data={"sub": user["username"], "role": user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": 120,
        "role": user["role"],
        "user_role": user["role"],
        "username": user["username"],
    }


@router.get("/auth/me", response_model=UserProfile, tags=["Authentication"])
async def get_me(current_user: UserProfile = Depends(get_current_user)):
    """Fetch profile of current authenticated user."""
    return current_user


# ============================================================================
# 2. ATM INVENTORY ENDPOINTS
# ============================================================================

@router.get("/atms", response_model=List[ATMItem], tags=["ATM Management"])
async def get_all_atms(
    city: Optional[str] = None,
    risk_level: Optional[str] = None,
    engine: RiskAndReplenishmentEngine = Depends(get_engine),
):
    """
    Return all 20 ATMs with coordinates, live cash balances, and risk status.
    Powers the React Leaflet Map and ATM List View.
    """
    atms = []
    for atm_id in sorted(engine.metadata.keys()):
        state = engine.get_latest_atm_state(atm_id)
        risk = engine.assess_cash_out_risk(atm_id, days_ahead=3)

        item = {
            **state,
            "risk_level": risk["risk_level"],
        }

        # Apply filters
        if city and item["city"].lower() != city.lower():
            continue
        if risk_level and item["risk_level"].lower() != risk_level.lower():
            continue

        atms.append(item)
    return atms


@router.get("/atms/{atm_id}", response_model=ATMDetail, tags=["ATM Management"])
async def get_atm_by_id(
    atm_id: int,
    engine: RiskAndReplenishmentEngine = Depends(get_engine),
):
    """Return detailed metadata and physical specifications for an individual ATM."""
    if atm_id not in engine.metadata:
        raise HTTPException(status_code=404, detail=f"ATM #{atm_id} not found.")

    state = engine.get_latest_atm_state(atm_id)
    meta = engine.metadata[atm_id]
    risk = engine.assess_cash_out_risk(atm_id, days_ahead=3)

    return {
        **state,
        "avg_daily_demand": float(meta.get("avg_daily_demand", 0.0)),
        "max_daily_demand": float(meta.get("max_daily_demand", 0.0)),
        "is_cash_recycler": True,
        "status": "Active",
        "risk_level": risk["risk_level"],
    }


# ============================================================================
# 3. FORECASTING ENDPOINTS
# ============================================================================

@router.get("/forecast/{atm_id}", response_model=ForecastResponse, tags=["Demand Forecasting"])
async def get_atm_forecast(
    atm_id: int,
    days: int = Query(7, ge=1, le=14, description="Forecast horizon in days"),
    engine: RiskAndReplenishmentEngine = Depends(get_engine),
):
    """
    Generate multi-day ahead cash demand forecast with 90% uncertainty intervals.
    Powers the Recharts / Plotly demand forecast curves.
    """
    try:
        forecast = engine.predictor.forecast_atm(atm_id=atm_id, days_ahead=days)
        return forecast
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================================================
# 4. RISK & REPLENISHMENT ENDPOINTS
# ============================================================================

@router.get("/risk/{atm_id}", response_model=RiskResponse, tags=["Risk & Optimization"])
async def get_atm_risk(
    atm_id: int,
    days: int = Query(3, ge=1, le=7, description="Planning window in days"),
    engine: RiskAndReplenishmentEngine = Depends(get_engine),
):
    """
    Evaluate cash-out risk, stockout probability, and estimated days until cash-out.
    """
    try:
        risk = engine.assess_cash_out_risk(atm_id=atm_id, days_ahead=days)
        return risk
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/replenishment/queue", response_model=List[ReplenishmentResponse], tags=["Risk & Optimization"])
async def get_replenishment_queue(
    engine: RiskAndReplenishmentEngine = Depends(get_engine),
):
    """
    Return prioritized operational replenishment queue for Cash-In-Transit (CIT) dispatch.
    Sorted by urgency score and cash-out risk.
    """
    return engine.get_replenishment_queue()


@router.post("/replenishment/approve", tags=["Risk & Optimization"])
async def approve_replenishment(
    request: ReplenishmentApprovalRequest,
    current_user: UserProfile = Depends(require_role(["admin", "operations_manager"])),
    engine: RiskAndReplenishmentEngine = Depends(get_engine),
):
    """
    Approve an armored cash van replenishment order.
    Requires Role: Admin or Operations Manager.
    """
    if request.atm_id not in engine.metadata:
        raise HTTPException(status_code=404, detail=f"ATM #{request.atm_id} not found.")

    return {
        "status": "APPROVED",
        "order_id": f"ORD-ATM{request.atm_id}-2026",
        "atm_id": request.atm_id,
        "approved_amount": request.approved_amount,
        "approved_by": current_user.username,
        "notes": request.notes,
        "message": f"CIT Armored Van dispatched for ATM #{request.atm_id}.",
    }


@router.get("/replenishment/{atm_id}", response_model=ReplenishmentResponse, tags=["Risk & Optimization"])
async def get_atm_replenishment(
    atm_id: int,
    days: int = Query(3, ge=1, le=7, description="Planning horizon in days"),
    engine: RiskAndReplenishmentEngine = Depends(get_engine),
):
    """
    Calculate optimal replenishment amount using:
    Refill = max(0, Forecast Demand + Safety Stock - Current Cash)
    """
    try:
        refill = engine.calculate_replenishment(atm_id=atm_id, planning_days=days)
        return refill
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================================================
# 5. DASHBOARD SUMMARY & ALERTS
# ============================================================================

@router.get("/dashboard/summary", response_model=DashboardSummaryResponse, tags=["Dashboard & Reporting"])
async def get_dashboard_summary(
    engine: RiskAndReplenishmentEngine = Depends(get_engine),
):
    """
    Return executive portfolio KPIs for the entire ATM fleet.
    Powers the Top-Level KPI Summary Cards in React.
    """
    return engine.get_dashboard_kpis()


@router.get("/alerts", response_model=List[AlertItem], tags=["Dashboard & Reporting"])
async def get_alerts(
    engine: RiskAndReplenishmentEngine = Depends(get_engine),
):
    """Fetch active operational alerts for ATMs facing imminent stockout."""
    return engine.get_active_alerts()


@router.get("/reports", tags=["Dashboard & Reporting"])
async def get_reports_summary():
    """Return model performance metrics and system benchmarks."""
    metrics_path = Path("models/model_metrics.json")
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
    else:
        metrics = []

    return {
        "project_title": "ATM Cash Demand Predictor",
        "target_accuracy": ">= 85%",
        "best_model": "XGBoost Regressor (Tuned)",
        "models_benchmark": metrics,
        "validation_strategy": "Chronological Out-of-Time Walk-Forward Partition",
        "leakage_prevention": "Strict shift(1) lag & rolling feature generation",
    }
