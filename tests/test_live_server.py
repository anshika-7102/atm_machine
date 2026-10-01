"""
Live End-to-End Server Verification Script.
Tests all endpoints against the live running FastAPI server on http://localhost:8000.
"""

import requests

BASE_URL = "http://localhost:8000"


def run_live_tests():
    print("=" * 60)
    print("LIVE SERVER END-TO-END VERIFICATION")
    print("=" * 60)

    # 1. Health check
    print("\n[1/8] Checking Health Endpoint...")
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    print(f"  [OK] Health: {r.json()}")

    # 2. React UI Dashboard
    print("\n[2/8] Checking React Dashboard SPA Mount...")
    r = requests.get(f"{BASE_URL}/dashboard/")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert "id=\"root\"" in r.text or "ATM Cash Demand" in r.text
    print(f"  [OK] Dashboard HTML rendered successfully ({len(r.text)} bytes)")

    # 3. Authentication
    print("\n[3/8] Testing Authentication (/api/v1/auth/login)...")
    r = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"username": "manager", "password": "password123"},
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]
    role = r.json()["role"]
    print(f"  [OK] Authenticated as: {r.json()['username']} (Role: {role})")
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Dashboard Summary
    print("\n[4/8] Fetching Fleet Portfolio KPIs (/api/v1/dashboard/summary)...")
    r = requests.get(f"{BASE_URL}/api/v1/dashboard/summary")
    assert r.status_code == 200
    summary = r.json()
    print(f"  [OK] Total Fleet Terminals: {summary['total_atms']}")
    print(f"  [OK] Network Cash in Circulation: {summary['total_cash_in_network']:,.1f} units")
    print(f"  [OK] Forecasted 24h Network Demand: {summary['forecasted_24h_network_demand']:,.1f} units")
    print(f"  [OK] Pending Replenishment Orders: {summary['pending_refill_orders']}")

    # 5. XGBoost Multi-Step Forecast
    print("\n[5/8] Testing XGBoost 7-Day Demand Forecast (/api/v1/forecast/74)...")
    r = requests.get(f"{BASE_URL}/api/v1/forecast/74?days=7")
    assert r.status_code == 200
    fc = r.json()
    print(f"  [OK] Forecast generated for ATM #{fc['atm_id']}")
    print(f"  [OK] Total 7-Day Predicted Demand: {fc['total_predicted_demand']:,.1f} units (~{fc['total_predicted_demand']*34:,.0f} Rubles)")
    for day in fc["daily_forecasts"][:3]:
        print(f"     -> Day +{day['day_ahead']} ({day['date']}, {day['day_name']}): {day['predicted_demand']:.1f} units [90% Range: {day['lower_bound_90pct']:.1f} - {day['upper_bound_90pct']:.1f}]")

    # 6. Risk Engine
    print("\n[6/8] Testing Cash-Out Risk Assessment (/api/v1/risk/74)...")
    r = requests.get(f"{BASE_URL}/api/v1/risk/74?days=3")
    assert r.status_code == 200
    risk = r.json()
    print(f"  [OK] Terminal Risk Level: {risk['risk_level']}")
    print(f"  [OK] Cash-Out Stockout Probability: {risk['cash_out_probability']*100:.1f}%")
    print(f"  [OK] Current Cash Balance: {risk['current_cash']:,.1f} units")
    print(f"  [OK] Days Until Terminal Empty: {risk['days_until_cashout']}")

    # 7. Replenishment Queue
    print("\n[7/8] Testing CIT Replenishment Dispatch Queue (/api/v1/replenishment/queue)...")
    r = requests.get(f"{BASE_URL}/api/v1/replenishment/queue")
    assert r.status_code == 200
    queue = r.json()
    print(f"  [OK] Dispatch Queue Length: {len(queue)} ATMs")
    top = queue[0]
    print(f"  [OK] Top Priority Dispatch: ATM #{top['atm_id']} ({top['atm_name']}) in {top['city']}")
    print(f"     -> Urgency Score: {top['urgency_score']}")
    print(f"     -> Recommended Refill: +{top['recommended_refill']:,.1f} units (~{top['recommended_refill']*34:,.0f} Rubles)")

    # 8. CIT Dispatch Approval (RBAC)
    print("\n[8/8] Testing CIT Van Dispatch Approval (/api/v1/replenishment/approve)...")
    r = requests.post(
        f"{BASE_URL}/api/v1/replenishment/approve",
        headers=headers,
        json={
            "atm_id": top["atm_id"],
            "approved_amount": top["recommended_refill"],
            "notes": "Verified by Automated E2E Test Suite",
        },
    )
    assert r.status_code == 200
    approval = r.json()
    print(f"  [OK] Order Status: {approval['status']}")
    print(f"  [OK] CIT Dispatch Confirmation: {approval['message']}")

    print("\n" + "=" * 60)
    print("SUCCESS: ALL 8 LIVE END-TO-END TESTS PASSED CLEANLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_live_tests()
