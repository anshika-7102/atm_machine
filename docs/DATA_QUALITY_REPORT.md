# Data Quality Report: Tinkoff ATM Dataset

## 1. Executive Summary

This data quality report documents the automated, reproducible cleaning and aggregation pipeline executed on the Tinkoff ATM dataset. The primary objectives of this stage were to audit data integrity, resolve duplicate logs, standardize schema conventions, understand financial transaction semantics, assess time-series continuity, and construct a daily ATM cash demand dataset suitable for time-series forecasting.

| Metric | Transaction Dataset | Daily Demand Dataset |
| :--- | :--- | :--- |
| **Original Records** | 1,048,575 | N/A (Derived) |
| **Cleaned / Final Records** | 1,037,286 | 8,461 |
| **Columns** | 5 | 9 |
| **Unique ATMs** | 20 | 20 |
| **Date Range** | 2017-06-09 to 2018-09-30 | 2017-06-09 to 2018-09-30 |
| **Calendar Span** | 479 days | 479 days |
| **Exact Duplicates Removed** | 11,289 (1.077%) | 0 duplicate (ATM, Date) pairs |
| **Missing Values (Before / After)** | 0 / 0 | 0 / 0 |

---

## 2. Dataset Dimensions & Schema Audit

### 2.1 Raw vs. Cleaned Dimensions
- **Original Raw Dimensions**: 1,048,575 rows × 5 columns
- **Cleaned Dimensions**: 1,037,286 rows × 5 columns
- **Duplicates Dropped**: 11,289 rows (keeping the first occurrence)
- **Columns Removed**: None (0). All original features (`datetime`, `atm_id`, `operation_type`, `client_id`, `operation_value`) are preserved.

### 2.2 Schema & Data Type Transformations
- `datetime`: Converted from string (`object`) to native ISO `datetime64[ns]` and standardized format `YYYY-MM-DD`.
- `atm_id`: Validated as integer (`int64`). All 20 ATMs have positive, valid numerical identifiers.
- `operation_type`: Validated as integer (`int64`).
- `client_id`: Validated as integer (`int64`).
- `operation_value`: Stored as high-precision 64-bit float (`float64`).

---

## 3. Missing Values & Imputation Analysis

### 3.1 Missing Value Counts
| Column | Missing Before Cleaning | Missing After Cleaning | Action Taken |
| :--- | :--- | :--- | :--- |
| `datetime` | 0 | 0 | Parsed to datetime. No nulls or impossible calendar dates found. |
| `atm_id` | 0 | 0 | Validated. All IDs belong to active fleet. |
| `operation_type` | 0 | 0 | Validated against operation dictionary. |
| `client_id` | 0 | 0 | Validated. Min client ID: 6. |
| `operation_value` | 0 | 0 | Verified complete. No blind zero-filling required. |

---

## 4. Duplicate Records & Multi-Transaction Investigation

### 4.1 Exact Duplicate Records
- **Identified**: 11,289 exact duplicates (1.077% of raw rows).
- **Cause**: Logging artifact or multi-buffer export from terminal logs where the exact same timestamp, ATM, client, operation type, and amount were exported multiple times.
- **Action**: Removed exact duplicates using `df.drop_duplicates(keep='first')`.

### 4.2 Legitimate Multi-Transactions
- **Identified**: 119,208 records where the same `client_id` engaged with the same `atm_id` on the same `datetime` with different operation types or different values.
- **Cause**: Normal customer banking behavior (e.g., a customer making an initial withdrawal, followed by a second withdrawal or balance check, or cash deposit).
- **Action**: Retained in full. None were removed.

---

## 5. Domain Validation & Value Semantics

### 5.1 ATM Identifiers
- Total Unique ATMs: 20
- Active ATM IDs: `[74, 85, 86, 87, 88, 90, 91, 93, 94, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106]`
- Invalid/Negative ATM IDs: 0

### 5.2 Transaction Types Breakdown
| Operation Type | Transaction Count | Pct of Cleaned Data | Sign Distribution | Description |
| :---: | :---: | :---: | :---: | :--- |
| `0` | 833,522 | 80.36% | Positive & Negative | Standard card cash withdrawals & cash deposits |
| `4` | 104,807 | 10.10% | Strictly Positive | Cash withdrawals / dispensing operations |
| `1` | 56,746 | 5.47% | Positive & Negative | Interbank / Partner card transactions |
| `5` | 29,712 | 2.86% | Positive & Negative | Large denomination cash exchanges / deposits |
| `6` | 10,040 | 0.97% | Strictly Positive | Small utility / mobile payments / fee deductions |
| `2` | 2,459 | 0.24% | Strictly Negative | Specific account debits / reversals |

### 5.3 Monetary Values & Sign Convention
- **Positive Values (`operation_value > 0`)**: 668,902 records.
  - Represents **Cash Outflow from ATM / Cash Dispensed to Customer** (ATM Cash Demand).
- **Negative Values (`operation_value < 0`)**: 368,384 records.
  - Represents **Cash Inflow to ATM / Cash Deposited by Customer** (ATM Cash Recycling).
  - Decision: Negative values were **NOT deleted**. Deleting negative amounts would misrepresent modern cash-recycling ATM dynamics.
- **Zero Values (`operation_value == 0`)**: 0 records. None exist in the dataset.
- **Normalization Factor**: The raw amounts are anonymized by a scaling factor where `0.02941808030921` corresponds to 100 Russian Rubles (`1 unit = ~34 Rubles`). The theoretical maximum transaction cap is `294.1808030921` (corresponding to 10,000 units or 1,000,000 Rubles), which occurs exactly 20 times at the upper bound and 76 times at the lower bound.

---

## 6. Outlier Analysis

### 6.1 Transaction-Level Outliers
- **Interquartile Range (IQR) Method**:
  - Lower Bound: `-8.8254` | Upper Bound: `12.3556`
  - Outliers Detected: 197,583 (19.05%)
- **Z-Score Method (|z| > 3)**:
  - Outliers Detected: 20,001 (1.93%)
- **Decision**: All outliers were retained. High-value transactions reflect authentic, large-scale customer withdrawals (e.g., payroll distributions, business deposits) that fall within valid terminal limits.

### 6.2 Daily Demand Outliers
- **Demand IQR Outliers**: 230 days (heavy holiday or peak-demand days)
- **Demand Z-score Outliers (|z| > 3)**: 129 days

---

## 7. Time Series Continuity & Time Grid Construction

### 7.1 Calendar Continuity
- Overall network calendar span: 2017-06-09 to 2018-09-30 (479 days).
- While the full fleet reached steady-state deployment by mid-August 2017, individual ATMs experienced isolated calendar days without transaction logs (e.g., terminal outages, bank holidays, maintenance).
- Across all 20 ATMs, there are **109 calendar gap days**.

### 7.2 Zero-Demand Periods
- In the aggregated daily demand dataset:
  - **109 days** had no recorded transactions across the machine (terminal downtime or holiday closure). These are filled with `demand = 0.0` and flagged with `is_active_day = False`.
  - **14 days** had active deposit transactions but **zero cash withdrawals** (`demand = 0.0` with `transaction_count > 0` and `is_active_day = True`).
  - Total zero-demand records (`demand == 0.0`): **123 days**.
  - Negative demand records (`demand < 0.0`): **0** (Gross withdrawal demand is strictly non-negative).

---

## 8. Data Dictionaries

### 8.1 Cleaned Transaction Dataset (`data/processed/tinkoff_cleaned.csv`)
| Column Name | Data Type | Description | Domain / Example |
| :--- | :--- | :--- | :--- |
| `datetime` | `string` (ISO date) | Transaction date | `2017-06-09` to `2018-09-30` |
| `atm_id` | `int64` | Unique ATM terminal identifier | 20 unique IDs (e.g., 74, 85, 106) |
| `operation_type`| `int64` | Transaction channel / operation category code | `0, 1, 2, 4, 5, 6` |
| `client_id` | `int64` | Anonymized unique customer identifier | Positive integers (`6` to `3,425,710`) |
| `operation_value`| `float64` | Normalized monetary amount (positive: cash withdrawal, negative: cash deposit) | `[-294.180803, 294.180803]` |

### 8.2 Daily Demand Dataset (`data/processed/atm_demand_daily.csv`)
| Column Name | Data Type | Description | Domain / Example |
| :--- | :--- | :--- | :--- |
| `atm_id` | `int64` | Unique ATM terminal identifier | 20 unique IDs |
| `date` | `string` (ISO date) | Calendar date | `2017-06-09` to `2018-09-30` |
| `demand` | `float64` | **Target Variable**: Gross cash withdrawal demand (total cash dispensed by ATM) | `[0.0, 4988.306206]` (Mean: 576.47) |
| `deposit_amount`| `float64` | Total cash deposited / recycled into ATM on that date | `[0.0, 2833.255315]` |
| `net_demand` | `float64` | Net cash outflow (`demand - deposit_amount`) | `[-1925.2957, 3711.2673]` |
| `transaction_count`| `int64` | Total number of financial operations on that date | `[0, 521]` |
| `withdrawal_count` | `int64` | Number of cash withdrawal transactions | `[0, 396]` |
| `deposit_count` | `int64` | Number of cash deposit transactions | `[0, 201]` |
| `is_active_day` | `bool` | Flag indicating whether ATM was actively logging (`True`) or calendar gap filled (`False`) | `True, False` |

---

## 9. Cleaning Decisions Summary

1. **Preservation of Raw Data**: Raw data in `data/raw/` (and original `tinkoffatm/`) remained completely untouched.
2. **Exact Duplicates Dropped**: Exactly 11,289 redundant rows were removed to prevent distortion of transaction volume.
3. **Legitimate Multi-Transactions Retained**: Customers performing multiple legitimate operations on the same date were kept intact.
4. **Preservation of Negative Values**: Negative amounts reflect cash deposits in modern recycling ATMs. Rather than deleting them, they were separated into withdrawal demand and deposit volume.
5. **No Synthetic Value Invention**: No artificial balances, replenishment events, or stockout events were fabricated.
6. **Continuous Time-Series Grid**: Inactive days were represented with zero demand and explicitly flagged (`is_active_day = False`) to guarantee uniform spacing required for time-series forecasting lag features.

---

## 10. Remaining Limitations & Edge Cases

1. **Excel Row Truncation in Source File**: The raw file `train_kaggle.csv` contains exactly 1,048,575 rows (equal to $2^{20} - 1$, the exact limit of Microsoft Excel exports). Transactions appear to have been sorted by `client_id` before export, meaning high-numbered client transactions from mid-2018 onwards may be partially truncated.
2. **Lack of Sub-Daily Timestamps**: Timestamps in the raw dataset provide only date (`YYYY-MM-DD`) precision without hour, minute, or second. Intraday (hourly) demand forecasting is therefore not mathematically feasible from this dataset; daily aggregation is the optimal and appropriate resolution.
3. **Anonymized Currency Units**: Monetary amounts are normalized by Tinkoff organizers by multiplying Russian Rubles by ~`0.00029418`. Converting to nominal Rubles requires dividing values by `0.02941808030921` (which yields 100-Rubles units).
4. **Unobserved Machine States**: The dataset does not record machine hardware breakdowns, cash-out (stockout) events, or replenishment schedules. Periods of zero demand may represent either zero customer foot traffic or mechanical downtime.
