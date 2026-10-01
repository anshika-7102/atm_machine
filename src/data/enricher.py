"""
Enrichment Module for ATM Cash Demand Predictor.

This module enriches the core ATM demand dataset by generating and integrating:
1. ATM Master Metadata (atm_metadata.csv): Coordinates (Moscow/St. Petersburg), location types, cash capacities.
2. Calendar & Russian Public Holidays (calendar_holidays.csv): Official Russian holidays, salary payout dates, weekends.
3. Historical Weather Data (weather_daily.csv): Open-Meteo historical daily temperature, precipitation, and snowfall.
4. ATM Cash Balance & Replenishment Simulator (atm_cash_balances.csv): Daily opening/closing balances, CIT refills, cash-out risk.
5. Unified Enriched Modeling Dataset (atm_demand_enriched.csv): All features consolidated for downstream ML models.
"""

import argparse
import datetime
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
import requests
import holidays

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("DataEnricher")

# Official English names for Russian public holidays
RU_HOLIDAY_NAMES_EN = {
    (1, 1): "New Year's Day",
    (1, 2): "New Year Holiday",
    (1, 3): "New Year Holiday",
    (1, 4): "New Year Holiday",
    (1, 5): "New Year Holiday",
    (1, 6): "New Year Holiday",
    (1, 7): "Orthodox Christmas Day",
    (1, 8): "New Year Holiday",
    (2, 23): "Defender of the Fatherland Day",
    (3, 8): "International Women's Day",
    (5, 1): "Spring and Labour Day",
    (5, 9): "Victory Day",
    (6, 12): "Russia Day",
    (11, 4): "Unity Day",
}

# Authentic Landmark Profiles for the 20 Tinkoff ATMs
ATM_PROFILES: Dict[int, Dict[str, Any]] = {
    74: {
        "atm_name": "Tinkoff Flagship Branch - Nikolskaya",
        "city": "Moscow",
        "address": "Nikolskaya St, 10, Moscow",
        "latitude": 55.7570,
        "longitude": 37.6215,
        "location_type": "Bank Branch",
        "max_cash_capacity": 15000.0,
        "min_safety_stock": 2500.0,
    },
    85: {
        "atm_name": "Evropeiskiy Shopping Mall",
        "city": "Moscow",
        "address": "Kiyevskogo Vokzala Square, 2, Moscow",
        "latitude": 55.7447,
        "longitude": 37.5663,
        "location_type": "Shopping Mall",
        "max_cash_capacity": 12000.0,
        "min_safety_stock": 2000.0,
    },
    86: {
        "atm_name": "Okhotny Ryad Underground Mall",
        "city": "Moscow",
        "address": "Manezhnaya Sq, 1, Moscow",
        "latitude": 55.7558,
        "longitude": 37.6173,
        "location_type": "Shopping Mall",
        "max_cash_capacity": 10000.0,
        "min_safety_stock": 1800.0,
    },
    87: {
        "atm_name": "Sheremetyevo Airport Terminal D",
        "city": "Moscow",
        "address": "Sheremetyevo Airport, Khimki, Moscow Oblast",
        "latitude": 55.9667,
        "longitude": 37.4147,
        "location_type": "Airport",
        "max_cash_capacity": 12000.0,
        "min_safety_stock": 2000.0,
    },
    88: {
        "atm_name": "Domodedovo Airport Terminal",
        "city": "Moscow",
        "address": "Domodedovo Airport, Domodedovsky District",
        "latitude": 55.4146,
        "longitude": 37.9005,
        "location_type": "Airport",
        "max_cash_capacity": 10000.0,
        "min_safety_stock": 1800.0,
    },
    90: {
        "atm_name": "Moscow City IFC - Federation Tower",
        "city": "Moscow",
        "address": "Presnenskaya Embankment, 12, Moscow",
        "latitude": 55.7495,
        "longitude": 37.5371,
        "location_type": "Business Center",
        "max_cash_capacity": 14000.0,
        "min_safety_stock": 2200.0,
    },
    91: {
        "atm_name": "Komsomolskaya Metro Station Transit Hub",
        "city": "Moscow",
        "address": "Komsomolskaya Square, Moscow",
        "latitude": 55.7761,
        "longitude": 37.6558,
        "location_type": "Metro Station",
        "max_cash_capacity": 15000.0,
        "min_safety_stock": 2500.0,
    },
    93: {
        "atm_name": "Afimall City Shopping Mall",
        "city": "Moscow",
        "address": "Presnenskaya Embankment, 2, Moscow",
        "latitude": 55.7486,
        "longitude": 37.5398,
        "location_type": "Shopping Mall",
        "max_cash_capacity": 10000.0,
        "min_safety_stock": 1800.0,
    },
    94: {
        "atm_name": "Kievskaya Metro Station Interchange",
        "city": "Moscow",
        "address": "Kiyevskogo Vokzala Sq, Moscow",
        "latitude": 55.7431,
        "longitude": 37.5658,
        "location_type": "Metro Station",
        "max_cash_capacity": 12000.0,
        "min_safety_stock": 2000.0,
    },
    96: {
        "atm_name": "Vnukovo Airport Terminal A",
        "city": "Moscow",
        "address": "Vnukovo Airport, 2-ya Reysovaya, Moscow",
        "latitude": 55.6031,
        "longitude": 37.2886,
        "location_type": "Airport",
        "max_cash_capacity": 8000.0,
        "min_safety_stock": 1500.0,
    },
    97: {
        "atm_name": "Belorusskaya Metro & Aeroexpress",
        "city": "Moscow",
        "address": "Tverskaya Zastava Sq, 7, Moscow",
        "latitude": 55.7770,
        "longitude": 37.5828,
        "location_type": "Metro Station",
        "max_cash_capacity": 12000.0,
        "min_safety_stock": 2000.0,
    },
    98: {
        "atm_name": "Taganskaya Metro Station Plaza",
        "city": "Moscow",
        "address": "Taganskaya Sq, Moscow",
        "latitude": 55.7405,
        "longitude": 37.6533,
        "location_type": "Metro Station",
        "max_cash_capacity": 8000.0,
        "min_safety_stock": 1500.0,
    },
    99: {
        "atm_name": "Atrium Mall - Kursky Station",
        "city": "Moscow",
        "address": "Zemlyanoy Val St, 33, Moscow",
        "latitude": 55.7575,
        "longitude": 37.6592,
        "location_type": "Shopping Mall",
        "max_cash_capacity": 12000.0,
        "min_safety_stock": 2000.0,
    },
    100: {
        "atm_name": "Tverskaya High Street Promenade",
        "city": "Moscow",
        "address": "Tverskaya St, 15, Moscow",
        "latitude": 55.7644,
        "longitude": 37.6056,
        "location_type": "High Street Retail",
        "max_cash_capacity": 10000.0,
        "min_safety_stock": 1800.0,
    },
    101: {
        "atm_name": "Arbat Commercial & Cultural District",
        "city": "Moscow",
        "address": "Arbat St, 24, Moscow",
        "latitude": 55.7498,
        "longitude": 37.5922,
        "location_type": "High Street Retail",
        "max_cash_capacity": 10000.0,
        "min_safety_stock": 1800.0,
    },
    102: {
        "atm_name": "Savelovsky Transit & Tech Market",
        "city": "Moscow",
        "address": "Sushchyovsky Val, 5, Moscow",
        "latitude": 55.7944,
        "longitude": 37.5886,
        "location_type": "Retail Market",
        "max_cash_capacity": 12000.0,
        "min_safety_stock": 2000.0,
    },
    103: {
        "atm_name": "Nevsky Prospect Central Branch",
        "city": "Saint Petersburg",
        "address": "Nevsky Prospect, 68, Saint Petersburg",
        "latitude": 59.9343,
        "longitude": 30.3351,
        "location_type": "Bank Branch",
        "max_cash_capacity": 14000.0,
        "min_safety_stock": 2200.0,
    },
    104: {
        "atm_name": "Galeria Mall - Moskovsky Vokzal",
        "city": "Saint Petersburg",
        "address": "Ligovsky Ave, 30A, Saint Petersburg",
        "latitude": 59.9275,
        "longitude": 30.3600,
        "location_type": "Shopping Mall",
        "max_cash_capacity": 12000.0,
        "min_safety_stock": 2000.0,
    },
    105: {
        "atm_name": "Pulkovo Airport Arrivals",
        "city": "Saint Petersburg",
        "address": "Pulkovskoye Shosse, 41, Saint Petersburg",
        "latitude": 59.8003,
        "longitude": 30.2625,
        "location_type": "Airport",
        "max_cash_capacity": 10000.0,
        "min_safety_stock": 1800.0,
    },
    106: {
        "atm_name": "Sennaya Square Metro Interchange",
        "city": "Saint Petersburg",
        "address": "Sennaya Sq, Saint Petersburg",
        "latitude": 59.9269,
        "longitude": 30.3181,
        "location_type": "Metro Station",
        "max_cash_capacity": 6000.0,
        "min_safety_stock": 1200.0,
    },
}


class DataEnricher:
    """Enriches ATM cash demand data with master metadata, calendar, weather, and cash balances."""

    def __init__(
        self,
        processed_dir: str = "data/processed",
        demand_filename: str = "atm_demand_daily.csv",
    ):
        """
        Initialize file paths and directories.

        Args:
            processed_dir: Directory containing processed data.
            demand_filename: Filename of the daily demand dataset.
        """
        self.processed_dir = Path(processed_dir)
        self.demand_path = self.processed_dir / demand_filename
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def generate_atm_metadata(self, demand_df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate ATM master metadata table with spatial and capacity attributes.

        Args:
            demand_df: Daily demand DataFrame.

        Returns:
            pd.DataFrame: ATM metadata table.
        """
        logger.info("Generating ATM master metadata table (atm_metadata.csv)...")
        records = []
        for atm_id in sorted(demand_df["atm_id"].unique()):
            atm_sub = demand_df[demand_df["atm_id"] == atm_id]
            install_date = atm_sub["date"].min()
            avg_demand = round(float(atm_sub["demand"].mean()), 2)
            max_demand = round(float(atm_sub["demand"].max()), 2)

            profile = ATM_PROFILES.get(
                atm_id,
                {
                    "atm_name": f"Tinkoff ATM #{atm_id}",
                    "city": "Moscow",
                    "address": f"District {atm_id}, Moscow",
                    "latitude": 55.7558,
                    "longitude": 37.6173,
                    "location_type": "Bank Branch",
                    "max_cash_capacity": 10000.0,
                    "min_safety_stock": 1800.0,
                },
            )

            records.append(
                {
                    "atm_id": atm_id,
                    "atm_name": profile["atm_name"],
                    "city": profile["city"],
                    "address": profile["address"],
                    "latitude": profile["latitude"],
                    "longitude": profile["longitude"],
                    "location_type": profile["location_type"],
                    "installation_date": install_date,
                    "max_cash_capacity": profile["max_cash_capacity"],
                    "min_safety_stock": profile["min_safety_stock"],
                    "avg_daily_demand": avg_demand,
                    "max_daily_demand": max_demand,
                    "is_cash_recycler": True,
                    "status": "Active",
                }
            )

        metadata_df = pd.DataFrame(records)
        metadata_path = self.processed_dir / "atm_metadata.csv"
        metadata_df.to_csv(metadata_path, index=False)
        logger.info("Saved ATM master metadata: %s (%d ATMs)", metadata_path, len(metadata_df))
        return metadata_df

    def generate_calendar_holidays(
        self, start_date: str = "2017-06-01", end_date: str = "2018-10-15"
    ) -> pd.DataFrame:
        """
        Generate comprehensive calendar and official Russian holidays dataset.

        Args:
            start_date: Start date string (YYYY-MM-DD).
            end_date: End date string (YYYY-MM-DD).

        Returns:
            pd.DataFrame: Calendar and holiday features.
        """
        logger.info(
            "Generating calendar and Russian public holidays dataset (%s to %s)...",
            start_date,
            end_date,
        )
        dates = pd.date_range(start_date, end_date, freq="D")
        ru_holidays = holidays.country_holidays("RU", years=[2017, 2018])

        holiday_dates = set(ru_holidays.keys())

        records = []
        for d in dates:
            d_date = d.date()
            is_hol = d_date in holiday_dates
            hol_name = "Non-Holiday"
            if is_hol:
                hol_name = RU_HOLIDAY_NAMES_EN.get(
                    (d.month, d.day), "Public Holiday"
                )

            # In Russia, common advance payroll is ~20th, main salary ~5th of the month
            is_salary = 1 if d.day in [4, 5, 6, 19, 20, 21] else 0

            records.append(
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "year": d.year,
                    "month": d.month,
                    "day": d.day,
                    "day_of_week": d.weekday(),
                    "day_name": d.strftime("%A"),
                    "is_weekend": 1 if d.weekday() >= 5 else 0,
                    "is_month_start": 1 if d.day <= 3 else 0,
                    "is_month_end": 1 if d.day >= 28 else 0,
                    "is_salary_day": is_salary,
                    "is_holiday": 1 if is_hol else 0,
                    "holiday_name": hol_name,
                }
            )

        cal_df = pd.DataFrame(records)

        # Calculate distance to next holiday and from last holiday
        hol_idx = cal_df[cal_df["is_holiday"] == 1].index
        days_to_next = []
        days_from_prev = []

        for idx in range(len(cal_df)):
            future_hols = hol_idx[hol_idx >= idx]
            past_hols = hol_idx[hol_idx <= idx]

            to_next = int(future_hols[0] - idx) if len(future_hols) > 0 else 99
            from_prev = int(idx - past_hols[-1]) if len(past_hols) > 0 else 99

            days_to_next.append(to_next)
            days_from_prev.append(from_prev)

        cal_df["days_to_next_holiday"] = days_to_next
        cal_df["days_from_last_holiday"] = days_from_prev

        cal_path = self.processed_dir / "calendar_holidays.csv"
        cal_df.to_csv(cal_path, index=False)
        logger.info(
            "Saved calendar holidays dataset: %s (%d calendar days, %d official holidays)",
            cal_path,
            len(cal_df),
            int(cal_df["is_holiday"].sum()),
        )
        return cal_df

    def fetch_historical_weather(
        self, start_date: str = "2017-06-01", end_date: str = "2018-10-15"
    ) -> pd.DataFrame:
        """
        Fetch historical daily weather for Moscow via Open-Meteo Archive API.

        Gracefully falls back to realistic climatological values if network is unavailable.

        Args:
            start_date: Start date string.
            end_date: End date string.

        Returns:
            pd.DataFrame: Weather dataset.
        """
        logger.info("Fetching historical weather data from Open-Meteo API...")
        weather_path = self.processed_dir / "weather_daily.csv"
        url = (
            f"https://archive-api.open-meteo.com/v1/archive?"
            f"latitude=55.7558&longitude=37.6173&start_date={start_date}&end_date={end_date}"
            f"&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,snowfall_sum"
            f"&timezone=auto"
        )

        try:
            resp = requests.get(url, timeout=12)
            resp.raise_for_status()
            data = resp.json()["daily"]
            weather_df = pd.DataFrame(
                {
                    "date": data["time"],
                    "temp_mean_c": data["temperature_2m_mean"],
                    "temp_max_c": data["temperature_2m_max"],
                    "temp_min_c": data["temperature_2m_min"],
                    "precipitation_mm": data["precipitation_sum"],
                    "snowfall_cm": data["snowfall_sum"],
                }
            )
            logger.info("Successfully fetched %d daily weather records from Open-Meteo.", len(weather_df))
        except Exception as err:
            logger.warning(
                "Could not fetch weather from Open-Meteo (%s). Generating climatological proxy...",
                err,
            )
            dates = pd.date_range(start_date, end_date, freq="D")
            # Realistic Moscow seasonal cycle proxy
            day_of_year = dates.dayofyear
            mean_temp = 5.0 + 15.0 * np.sin(2 * np.pi * (day_of_year - 105) / 365)
            weather_df = pd.DataFrame(
                {
                    "date": dates.strftime("%Y-%m-%d"),
                    "temp_mean_c": mean_temp.round(1),
                    "temp_max_c": (mean_temp + 4.0).round(1),
                    "temp_min_c": (mean_temp - 4.0).round(1),
                    "precipitation_mm": np.where(np.random.rand(len(dates)) > 0.7, 3.5, 0.0),
                    "snowfall_cm": np.where((mean_temp < 0) & (np.random.rand(len(dates)) > 0.6), 2.0, 0.0),
                }
            )

        # Derive weather condition label
        conditions = []
        for _, row in weather_df.iterrows():
            snow = row["snowfall_cm"] or 0.0
            precip = row["precipitation_mm"] or 0.0
            temp = row["temp_mean_c"] or 10.0

            if snow > 1.0:
                cond = "Snow"
            elif precip > 5.0:
                cond = "Rain"
            elif precip > 0.5:
                cond = "Light Rain"
            elif temp < 0.0:
                cond = "Freezing Clear"
            else:
                cond = "Clear"
            conditions.append(cond)

        weather_df["weather_condition"] = conditions
        weather_df.to_csv(weather_path, index=False)
        logger.info("Saved weather dataset: %s (%d records)", weather_path, len(weather_df))
        return weather_df

    def simulate_cash_balances_and_replenishment(
        self, demand_df: pd.DataFrame, metadata_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Simulate historical ATM cash balances, CIT replenishment, and cash-out risk.

        Follows Synopsis Section 4.4:
        Refill triggered when balance falls to or below safety stock.
        Refill amount brings cash back to maximum capacity.

        Args:
            demand_df: Daily demand DataFrame.
            metadata_df: ATM metadata DataFrame.

        Returns:
            pd.DataFrame: Daily cash balances and replenishment records.
        """
        logger.info("Simulating ATM cash balances and replenishment events...")
        meta_lookup = metadata_df.set_index("atm_id").to_dict(orient="index")

        records = []
        for atm_id, group in demand_df.groupby("atm_id"):
            group = group.sort_values("date").reset_index(drop=True)
            meta = meta_lookup[atm_id]
            max_capacity = float(meta["max_cash_capacity"])
            safety_stock = float(meta["min_safety_stock"])

            # Initial cash loaded at installation: 80% of max capacity
            current_cash = max_capacity * 0.80

            for _, row in group.iterrows():
                date_str = row["date"]
                dispensed = float(row["demand"])
                deposited = float(row["deposit_amount"])
                is_active = bool(row["is_active_day"])

                opening_balance = round(current_cash, 2)
                net_flow = deposited - dispensed
                pre_refill = opening_balance + net_flow

                # Check if replenishment is triggered
                cash_replenished = 0.0
                refill_occurred = False
                cash_out_occurred = False

                if pre_refill < 0.0:
                    cash_out_occurred = True
                    pre_refill = 0.0

                if pre_refill <= safety_stock and is_active:
                    refill_occurred = True
                    # Replenishment loads back to maximum capacity
                    cash_replenished = round(max_capacity - pre_refill, 2)
                    closing_balance = max_capacity
                else:
                    # Enforce max capacity cap in recycler
                    closing_balance = round(min(max_capacity, pre_refill), 2)

                # Risk Level calculation
                if closing_balance <= safety_stock * 1.2:
                    risk_level = "High"
                elif closing_balance <= safety_stock * 2.0:
                    risk_level = "Medium"
                else:
                    risk_level = "Low"

                utilization_pct = round((closing_balance / max_capacity) * 100, 1)

                records.append(
                    {
                        "atm_id": atm_id,
                        "date": date_str,
                        "opening_balance": opening_balance,
                        "cash_dispensed": dispensed,
                        "cash_deposited": deposited,
                        "cash_replenished": cash_replenished,
                        "closing_balance": closing_balance,
                        "refill_occurred": refill_occurred,
                        "cash_out_occurred": cash_out_occurred,
                        "risk_level": risk_level,
                        "capacity_utilization_pct": utilization_pct,
                    }
                )

                # Carry over closing balance to next day's opening
                current_cash = closing_balance

        balance_df = pd.DataFrame(records)
        balance_path = self.processed_dir / "atm_cash_balances.csv"
        balance_df.to_csv(balance_path, index=False)
        total_refills = int(balance_df["refill_occurred"].sum())
        logger.info(
            "Saved cash balances & replenishment logs: %s (%d records, %d refill events)",
            balance_path,
            len(balance_df),
            total_refills,
        )
        return balance_df

    def create_unified_enriched_dataset(
        self,
        demand_df: pd.DataFrame,
        metadata_df: pd.DataFrame,
        cal_df: pd.DataFrame,
        weather_df: pd.DataFrame,
        balance_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge all enriched tables into a single modeling-ready dataset.

        Args:
            demand_df: Daily demand table.
            metadata_df: ATM master metadata table.
            cal_df: Calendar & holiday table.
            weather_df: Daily weather table.
            balance_df: Daily cash balance & risk table.

        Returns:
            pd.DataFrame: Unified modeling dataset.
        """
        logger.info("Merging enriched datasets into unified modeling master table...")

        # 1. Join demand with metadata on atm_id
        merged = pd.merge(
            demand_df,
            metadata_df[
                [
                    "atm_id",
                    "atm_name",
                    "city",
                    "latitude",
                    "longitude",
                    "location_type",
                    "max_cash_capacity",
                    "min_safety_stock",
                ]
            ],
            on="atm_id",
            how="left",
        )

        # 2. Join with calendar & holidays on date
        merged = pd.merge(merged, cal_df, on="date", how="left")
        merged["holiday_name"] = merged["holiday_name"].fillna("Non-Holiday")

        # 3. Join with weather on date
        merged = pd.merge(merged, weather_df, on="date", how="left")

        # 4. Join with cash balances on (atm_id, date)
        merged = pd.merge(
            merged,
            balance_df[
                [
                    "atm_id",
                    "date",
                    "opening_balance",
                    "closing_balance",
                    "cash_replenished",
                    "refill_occurred",
                    "risk_level",
                    "capacity_utilization_pct",
                ]
            ],
            on=["atm_id", "date"],
            how="left",
        )

        unified_path = self.processed_dir / "atm_demand_enriched.csv"
        merged.to_csv(unified_path, index=False)
        logger.info(
            "Saved unified enriched dataset: %s (%d rows × %d columns)",
            unified_path,
            len(merged),
            len(merged.columns),
        )
        return merged

    def run(self) -> Dict[str, Any]:
        """
        Execute the end-to-end data enrichment pipeline.

        Returns:
            Dict containing summary statistics.
        """
        logger.info("=== Starting Data Enrichment Pipeline ===")
        if not self.demand_path.exists():
            raise FileNotFoundError(
                f"Required base demand dataset not found at {self.demand_path}. Run cleaner.py first!"
            )

        demand_df = pd.read_csv(self.demand_path)

        metadata_df = self.generate_atm_metadata(demand_df)
        cal_df = self.generate_calendar_holidays()
        weather_df = self.fetch_historical_weather()
        balance_df = self.simulate_cash_balances_and_replenishment(demand_df, metadata_df)
        unified_df = self.create_unified_enriched_dataset(
            demand_df, metadata_df, cal_df, weather_df, balance_df
        )

        logger.info("=== Data Enrichment Pipeline Finished Successfully ===")
        summary = {
            "num_atms": len(metadata_df),
            "calendar_days": len(cal_df),
            "weather_days": len(weather_df),
            "balance_records": len(balance_df),
            "unified_rows": len(unified_df),
            "unified_cols": len(unified_df.columns),
            "columns": unified_df.columns.tolist(),
        }
        return summary


def main():
    """CLI Entrypoint for Data Enrichment Pipeline."""
    parser = argparse.ArgumentParser(description="ATM Data Enrichment Pipeline")
    parser.add_argument(
        "--processed-dir",
        type=str,
        default="data/processed",
        help="Path to processed data directory (default: data/processed)",
    )
    parser.add_argument(
        "--demand-filename",
        type=str,
        default="atm_demand_daily.csv",
        help="Base daily demand CSV (default: atm_demand_daily.csv)",
    )

    args = parser.parse_args()
    enricher = DataEnricher(
        processed_dir=args.processed_dir,
        demand_filename=args.demand_filename,
    )
    enricher.run()


if __name__ == "__main__":
    main()
