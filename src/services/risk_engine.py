"""
Risk and Replenishment Optimization Service for ATM Cash Demand Predictor.

Implements Phase 4 business logic from the project synopsis:
1. Dynamic Cash-Out Probability & Risk Classification (Low, Medium, High).
2. Operational Replenishment Policy:
   Recommended Refill = max(0, Forecast Demand + Safety Stock - Current Cash)
   Subject to max ATM cassette cash capacity.
3. Prioritized Cash-In-Transit (CIT) Refill Queue.
4. Real-time Portfolio Health & Executive KPI Dashboard Metrics.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.models.predict import DemandPredictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("RiskEngine")


class RiskAndReplenishmentEngine:
    """Service for estimating ATM cash-out risk and optimizing replenishment schedules."""

    def __init__(
        self,
        metadata_path: str = "data/processed/atm_metadata.csv",
        balances_path: str = "data/processed/atm_cash_balances.csv",
        features_path: str = "data/processed/atm_features_engineered.csv",
    ):
        self.metadata_path = Path(metadata_path)
        self.balances_path = Path(balances_path)
        self.features_path = Path(features_path)

        if not self.metadata_path.exists():
            raise FileNotFoundError(f"ATM metadata file not found at: {self.metadata_path}")
        if not self.balances_path.exists():
            raise FileNotFoundError(f"Cash balances file not found at: {self.balances_path}")

        self.metadata = pd.read_csv(self.metadata_path).set_index("atm_id").to_dict(orient="index")
        self.balances_df = pd.read_csv(self.balances_path)
        self.predictor = DemandPredictor(dataset_path=str(self.features_path))

    def get_latest_atm_state(self, atm_id: int) -> Dict[str, Any]:
        """Fetch latest recorded state and physical attributes for an ATM."""
        if atm_id not in self.metadata:
            raise ValueError(f"ATM ID {atm_id} not found in master records.")

        meta = self.metadata[atm_id]
        atm_logs = self.balances_df[self.balances_df["atm_id"] == atm_id].sort_values("date")
        latest_log = atm_logs.iloc[-1]

        return {
            "atm_id": int(atm_id),
            "atm_name": meta["atm_name"],
            "city": meta["city"],
            "address": meta["address"],
            "latitude": float(meta["latitude"]),
            "longitude": float(meta["longitude"]),
            "location_type": meta["location_type"],
            "max_cash_capacity": float(meta["max_cash_capacity"]),
            "min_safety_stock": float(meta["min_safety_stock"]),
            "current_cash": float(latest_log["closing_balance"]),
            "capacity_utilization_pct": float(latest_log["capacity_utilization_pct"]),
            "last_updated": str(latest_log["date"]),
        }

    def assess_cash_out_risk(self, atm_id: int, days_ahead: int = 3) -> Dict[str, Any]:
        """
        Assess cash-out probability and risk severity for an ATM over the planning window.

        Args:
            atm_id: ATM Identifier.
            days_ahead: Risk assessment window in days (default: 3 days).

        Returns:
            Dict containing cash-out probability, risk level, projected runway, and explanation.
        """
        state = self.get_latest_atm_state(atm_id)
        current_cash = state["current_cash"]
        safety_stock = state["min_safety_stock"]

        # Generate multi-day demand forecast
        fc = self.predictor.forecast_atm(atm_id=atm_id, days_ahead=days_ahead)
        forecast_demand = fc["total_predicted_demand"]
        daily_forecasts = fc["daily_forecasts"]

        # Estimate demand volatility
        daily_std = float(state["min_safety_stock"]) * 0.25
        std_window = daily_std * np.sqrt(days_ahead)

        # Statistical probability of cash falling below zero before refill
        if std_window > 0:
            z_score = (current_cash - forecast_demand) / std_window
            # Survival probability of stockout P(Cash <= 0)
            stockout_prob = float(norm.cdf(-z_score))
        else:
            stockout_prob = 1.0 if current_cash < forecast_demand else 0.0

        stockout_prob = round(float(np.clip(stockout_prob, 0.0, 1.0)), 4)

        # Determine Days Until Cash-Out
        running_cash = current_cash
        days_until_cashout = None
        for day in daily_forecasts:
            running_cash -= day["predicted_demand"]
            if running_cash <= 0:
                days_until_cashout = day["day_ahead"]
                break

        # Risk Classification (Synopsis Section 4.3)
        if current_cash <= safety_stock or stockout_prob >= 0.40 or (days_until_cashout is not None and days_until_cashout <= 2):
            risk_level = "High"
            explanation = (
                f"CRITICAL: Current cash ({current_cash:.1f} units) is at or below safety buffer "
                f"({safety_stock:.1f} units). Expected demand of {forecast_demand:.1f} units poses an immediate cash-out risk."
            )
        elif current_cash <= safety_stock * 1.8 or stockout_prob >= 0.15:
            risk_level = "Medium"
            explanation = (
                f"ATTENTION: Cash reserves ({current_cash:.1f} units) are sufficient for immediate operations "
                f"but approaching safety threshold. Schedule replenishment within 48-72 hours."
            )
        else:
            risk_level = "Low"
            explanation = (
                f"HEALTHY: Adequate liquidity ({current_cash:.1f} units) covers expected {days_ahead}-day demand "
                f"({forecast_demand:.1f} units) with ample buffer above safety stock."
            )

        return {
            "atm_id": int(atm_id),
            "atm_name": state["atm_name"],
            "city": state["city"],
            "current_cash": current_cash,
            "min_safety_stock": safety_stock,
            "planning_window_days": days_ahead,
            "forecasted_demand": round(forecast_demand, 2),
            "cash_out_probability": stockout_prob,
            "risk_level": risk_level,
            "days_until_cashout": days_until_cashout,
            "risk_explanation": explanation,
        }

    def calculate_replenishment(self, atm_id: int, planning_days: int = 3) -> Dict[str, Any]:
        """
        Calculate recommended replenishment amount using Synopsis formula:
        Recommended Refill = max(0, Forecast Demand + Safety Stock - Current Cash)
        Subject to available cassette capacity.

        Args:
            atm_id: ATM Identifier.
            planning_days: Operational planning horizon (default: 3 days).

        Returns:
            Dict containing recommended refill amount, priority, and reason.
        """
        state = self.get_latest_atm_state(atm_id)
        current_cash = state["current_cash"]
        max_capacity = state["max_cash_capacity"]
        safety_stock = state["min_safety_stock"]

        risk_assessment = self.assess_cash_out_risk(atm_id, days_ahead=planning_days)
        forecast_demand = risk_assessment["forecasted_demand"]
        risk_level = risk_assessment["risk_level"]

        # Formula from Synopsis Section 4.4
        target_cash_required = forecast_demand + safety_stock
        raw_refill = max(0.0, target_cash_required - current_cash)

        # Enforce physical max capacity constraint
        available_headroom = max(0.0, max_capacity - current_cash)
        recommended_refill = min(raw_refill, available_headroom)
        recommended_refill = round(recommended_refill, 2)

        # Priority Level
        if risk_level == "High" and recommended_refill > 0:
            priority = "Urgent (Priority 1)"
            urgency_score = 95
        elif (risk_level == "Medium" or current_cash <= safety_stock * 2.0) and recommended_refill > 0:
            priority = "Scheduled (Priority 2)"
            urgency_score = 65
        else:
            priority = "Normal (Priority 3)"
            urgency_score = 25

        reason = (
            f"Target requirement is {target_cash_required:.1f} units (Forecast: {forecast_demand:.1f} + Safety: {safety_stock:.1f}). "
            f"Current cash is {current_cash:.1f} units. Recommended loading brings terminal to optimal buffer."
        )

        return {
            "atm_id": int(atm_id),
            "atm_name": state["atm_name"],
            "city": state["city"],
            "location_type": state["location_type"],
            "current_cash": current_cash,
            "max_cash_capacity": max_capacity,
            "min_safety_stock": safety_stock,
            "forecasted_demand": forecast_demand,
            "recommended_refill": recommended_refill,
            "new_projected_cash": round(current_cash + recommended_refill, 2),
            "risk_level": risk_level,
            "priority": priority,
            "urgency_score": urgency_score,
            "recommendation_reason": reason,
        }

    def get_replenishment_queue(self) -> List[Dict[str, Any]]:
        """
        Generate prioritized operational replenishment queue for Cash-In-Transit (CIT) vans.
        Sorted by Urgency Score descending.
        """
        queue = []
        for atm_id in sorted(self.metadata.keys()):
            order = self.calculate_replenishment(atm_id, planning_days=3)
            queue.append(order)

        # Sort by urgency score descending, then recommended_refill descending
        queue = sorted(queue, key=lambda x: (x["urgency_score"], x["recommended_refill"]), reverse=True)
        return queue

    def get_dashboard_kpis(self) -> Dict[str, Any]:
        """Calculate executive portfolio KPIs for the entire ATM network."""
        all_states = [self.get_latest_atm_state(atm_id) for atm_id in self.metadata.keys()]
        queue = self.get_replenishment_queue()

        total_atms = len(all_states)
        total_cash_in_network = sum(s["current_cash"] for s in all_states)
        total_capacity = sum(s["max_cash_capacity"] for s in all_states)
        network_utilization = round((total_cash_in_network / total_capacity) * 100, 1)

        # Calculate next 24h network demand
        total_24h_demand = 0.0
        for atm_id in self.metadata.keys():
            fc = self.predictor.forecast_atm(atm_id=atm_id, days_ahead=1)
            total_24h_demand += fc["total_predicted_demand"]

        high_risk_count = sum(1 for q in queue if q["risk_level"] == "High")
        medium_risk_count = sum(1 for q in queue if q["risk_level"] == "Medium")
        low_risk_count = sum(1 for q in queue if q["risk_level"] == "Low")
        pending_refills_count = sum(1 for q in queue if q["recommended_refill"] > 0)
        total_cash_needed = sum(q["recommended_refill"] for q in queue)

        return {
            "total_atms": total_atms,
            "total_cash_in_network": round(total_cash_in_network, 2),
            "network_cash_capacity": round(total_capacity, 2),
            "network_utilization_pct": network_utilization,
            "forecasted_24h_network_demand": round(total_24h_demand, 2),
            "high_risk_atms_count": high_risk_count,
            "medium_risk_atms_count": medium_risk_count,
            "low_risk_atms_count": low_risk_count,
            "pending_refill_orders": pending_refills_count,
            "total_replenishment_needed": round(total_cash_needed, 2),
            "system_status": "Attention Needed" if high_risk_count > 0 else "Optimal",
        }

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Fetch active operational alerts for ATM operations managers."""
        queue = self.get_replenishment_queue()
        alerts = []

        for item in queue:
            if item["risk_level"] == "High":
                alerts.append(
                    {
                        "alert_id": f"ALT-ATM{item['atm_id']}-HIGH",
                        "atm_id": item["atm_id"],
                        "atm_name": item["atm_name"],
                        "severity": "CRITICAL",
                        "message": f"Critical cash shortage risk: Terminal has {item['current_cash']:.1f} units remaining. Refill {item['recommended_refill']:.1f} units immediately.",
                        "action_required": "Dispatch Armored CIT Van (Priority 1)",
                    }
                )
            elif item["risk_level"] == "Medium" and item["recommended_refill"] > 0:
                alerts.append(
                    {
                        "alert_id": f"ALT-ATM{item['atm_id']}-MED",
                        "atm_id": item["atm_id"],
                        "atm_name": item["atm_name"],
                        "severity": "WARNING",
                        "message": f"Cash approaching threshold: Reserve is {item['current_cash']:.1f} units. Recommended refill is {item['recommended_refill']:.1f} units.",
                        "action_required": "Schedule Replenishment in Next Route",
                    }
                )

        return alerts
