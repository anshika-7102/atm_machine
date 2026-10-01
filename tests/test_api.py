"""
Integration and Unit Tests for the ATM Cash Demand Predictor REST API.
Verifies all FastAPI routes, JWT authentication, and risk engine responses.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root GET endpoint returns 200 and system metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "version" in data
    assert data["documentation"] == "/docs"


def test_health_check_endpoint():
    """Verify health check returns status healthy."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "atm-demand-predictor"


def test_auth_login_success():
    """Verify user can authenticate via /api/v1/auth/token form endpoint."""
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "admin"
    assert data["user_role"] == "admin"


def test_auth_login_json_success():
    """Verify user can authenticate via /api/v1/auth/login JSON endpoint."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "manager", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "operations_manager"


def test_auth_login_invalid_credentials():
    """Verify failed login on bad password."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_get_current_user_profile():
    """Verify /api/v1/auth/me returns authenticated user details."""
    login_res = client.post(
        "/api/v1/auth/token",
        data={"username": "analyst", "password": "password123"},
    )
    token = login_res.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["username"] == "analyst"
    assert user_data["role"] == "analyst"


def test_list_atms():
    """Verify /api/v1/atms returns ATM fleet list."""
    response = client.get("/api/v1/atms")
    assert response.status_code == 200
    atms = response.json()
    assert isinstance(atms, list)
    assert len(atms) >= 20
    assert "atm_id" in atms[0]
    assert "city" in atms[0]
    assert "latitude" in atms[0]
    assert "longitude" in atms[0]


def test_get_atm_detail_valid():
    """Verify /api/v1/atms/{atm_id} returns single ATM metadata."""
    response = client.get("/api/v1/atms/74")
    assert response.status_code == 200
    atm = response.json()
    assert atm["atm_id"] == 74
    assert atm["city"] in ["Moscow", "Saint Petersburg"]
    assert atm["max_cash_capacity"] > 0
    assert atm["min_safety_stock"] > 0


def test_get_atm_detail_not_found():
    """Verify /api/v1/atms/{atm_id} returns 404 for unknown ATM ID."""
    response = client.get("/api/v1/atms/999999")
    assert response.status_code == 404


def test_get_forecast():
    """Verify /api/v1/forecast/{atm_id} returns multi-step predictions."""
    response = client.get("/api/v1/forecast/74?days=7")
    assert response.status_code == 200
    forecast = response.json()
    assert forecast["atm_id"] == 74
    assert forecast["horizon_days"] == 7
    assert len(forecast["daily_forecasts"]) == 7
    first_day = forecast["daily_forecasts"][0]
    assert "predicted_demand" in first_day
    assert "lower_bound_90pct" in first_day
    assert "upper_bound_90pct" in first_day
    assert first_day["upper_bound_90pct"] >= first_day["predicted_demand"]
    assert first_day["lower_bound_90pct"] <= first_day["predicted_demand"]


def test_get_risk():
    """Verify /api/v1/risk/{atm_id} evaluates risk and hours to critical."""
    response = client.get("/api/v1/risk/74?days=3")
    assert response.status_code == 200
    risk = response.json()
    assert risk["atm_id"] == 74
    assert risk["risk_level"].upper() in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert 0.0 <= risk["cash_out_probability"] <= 1.0
    assert risk["current_cash"] >= 0


def test_get_replenishment():
    """Verify /api/v1/replenishment/{atm_id} computes optimal refill."""
    response = client.get("/api/v1/replenishment/74?days=3")
    assert response.status_code == 200
    refill = response.json()
    assert refill["atm_id"] == 74
    assert refill["recommended_refill"] >= 0
    assert refill["priority"] in ["Normal (Priority 3)", "Scheduled (Priority 2)", "Urgent (Priority 1)"]


def test_get_replenishment_queue():
    """Verify /api/v1/replenishment/queue returns sorted dispatch queue."""
    response = client.get("/api/v1/replenishment/queue")
    assert response.status_code == 200
    queue = response.json()
    assert isinstance(queue, list)
    assert len(queue) >= 20


def test_dashboard_summary():
    """Verify /api/v1/dashboard/summary returns executive metrics."""
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    summary = response.json()
    assert summary["total_atms"] >= 20
    assert summary["high_risk_atms_count"] >= 0
    assert summary["network_utilization_pct"] >= 0.0


def test_get_alerts():
    """Verify /api/v1/alerts returns list of operational alerts."""
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    alerts = response.json()
    assert isinstance(alerts, list)


def test_get_reports():
    """Verify /api/v1/reports returns model benchmarks."""
    response = client.get("/api/v1/reports")
    assert response.status_code == 200
    data = response.json()
    assert data["best_model"] == "XGBoost Regressor (Tuned)"
    assert "models_benchmark" in data


def test_replenishment_approval_rbac():
    """Verify RBAC on replenishment approval endpoint."""
    # 1. Analyst token should be forbidden (403)
    analyst_login = client.post(
        "/api/v1/auth/token",
        data={"username": "analyst", "password": "password123"},
    )
    analyst_token = analyst_login.json()["access_token"]

    fail_res = client.post(
        "/api/v1/replenishment/approve",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"atm_id": 74, "approved_amount": 50000.0, "notes": "Test refill"},
    )
    assert fail_res.status_code == 403

    # 2. Operations Manager token should succeed (200)
    manager_login = client.post(
        "/api/v1/auth/token",
        data={"username": "manager", "password": "password123"},
    )
    manager_token = manager_login.json()["access_token"]

    success_res = client.post(
        "/api/v1/replenishment/approve",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"atm_id": 74, "approved_amount": 50000.0, "notes": "Approved dispatch"},
    )
    assert success_res.status_code == 200
    data = success_res.json()
    assert data["status"] == "APPROVED"
    assert data["atm_id"] == 74
