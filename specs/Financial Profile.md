# Flow 5: Financial Profile (Evergreen Metrics)

## Overview

The Financial Profile is the evergreen counterpart to the Insight Feed (Flow 4). Where the Insight Feed surfaces *episodic* events — "what changed?" — the Financial Profile answers "what is always true about my financial life?" It is a set of standing metrics, recomputed from the full ledger after every import, presented as the insights module on the **View Important** page.

Profile metrics have no lifecycle: they cannot be dismissed, they do not accumulate as rows in a feed, and they never go stale in place — each request reflects the current state of the ledger. They are computed views, not stored events.

Phase 1 ships six metrics:

1. Committed Monthly Spend
2. Average Monthly Burn
3. Average Monthly Income
4. Fixed vs. Discretionary Baseline
5. Savings Rate
6. Fees & Interest Paid

---

## Design Principles

**Computed, not stored.** Metrics are derived on request from the transaction ledger via `services/analytics.py` (the single source of truth for ledger math). No new event tables; results may be cached per import job, but the cache is an optimization, not a system of record.

**Ground everything in data.** Every metric exposes the transaction IDs (or merchant groups) behind it, so the UI can offer a drill-down identical to the Insight Feed's supporting-transactions pattern.

**Be honest about uncertainty.** Each metric carries a confidence score and label using the same thresholds as the Insight Feed (≥ 0.80 High, 0.55–0.79 Medium, < 0.55 Low). A savings rate computed from unconfirmed income candidates must say so.

**Respect the user's context.** Transfers are excluded from all spend and income computations. Refunds, cashback, and rewards credits are excluded from income. Only complete calendar months enter trailing averages — a partial current month distorts every metric on this page.

**Prefer durable framing.** These numbers are checked repeatedly. Present trailing averages and structural splits, not single-month snapshots, so the page reads the same way on the 3rd of the month as on the 30th.

---

## Shared Computation Rules

- **Ledger scope:** all non-duplicate, non-ambiguous transactions across all import jobs, loaded via `load_ledger`.
- **Transfer exclusion:** transactions matched by the transfer detector (Flow 4, type 9) or `_NOT_INCOME` transfer patterns are excluded from both spend and income.
- **Complete months only:** a month enters a trailing window only if the ledger contains transactions spanning it and the month is fully elapsed. The current partial month is never included in averages; it may be shown separately as "month to date."
- **Cadence normalization:** recurring amounts are normalized to monthly equivalents — weekly × 4.33, biweekly × 2.17, quarterly ÷ 3, annual ÷ 12.
- **Recurring detection reuse:** metrics 1 and 4 consume the same merchant-grouping and cadence logic as Recurring Charge Detected (Flow 4, type 4). That logic should be factored into a shared helper rather than duplicated.
- **Income computation reuse:** metrics 3 and 5 share one monthly-income computation (confirmed income per complete month, candidate fallback, transfer/refund exclusion) — implemented once in the profile engine.

---

## Metrics

### 1. Committed Monthly Spend

**Description:** The total the user is structurally committed to paying each month across all detected recurring charges — with the annualized figure, which is the number that motivates action.

**Computation:**
- Run recurring-charge detection across the full ledger (≥ 2 consecutive periods, amounts within 10%, debits only).
- Normalize each commitment to a monthly equivalent (see cadence normalization).
- Sum monthly equivalents → `committed_monthly_total`; × 12 → `committed_annualized_total`.
- For each commitment, project the next expected charge date from the observed cadence and most recent occurrence.
- A commitment leaves the list after it misses two consecutive expected periods (likely cancelled).

**Confidence Factors:**
- ≥ 3 months of ledger data → +0.30
- All commitments individually High confidence per Flow 4 rules → +0.30
- ≥ 3 distinct recurring merchants → +0.20
- No cadence ambiguity (no merchant with conflicting cadence signals) → +0.20

**Example:**
> **Committed monthly spend: $412/month ($4,944/year)**
> You have 14 active recurring commitments, from Netflix ($17.99) to car insurance ($148). The three largest account for 61% of the total. Confidence: High

**Payload:**
```json
{
  "committed_monthly_total": 412.37,
  "committed_annualized_total": 4948.44,
  "commitment_count": 14,
  "commitments": [
    {
      "merchant": "Adobe Creative Cloud",
      "cadence": "monthly",
      "amount_per_period": 59.99,
      "monthly_equivalent": 59.99,
      "next_expected_charge": "2026-09-03",
      "occurrences_detected": 6,
      "supporting_transaction_ids": [101, 145, 189, 240, 288, 331]
    }
  ]
}
```

---

### 2. Average Monthly Burn

**Description:** What a normal month costs the user — the reference point against which any single month's spending is judged.

**Computation:**
- Sum total debits (transfers excluded) per complete month.
- `burn_3mo` = mean of the trailing 3 complete months; `burn_6mo` = mean of the trailing 6 complete months (omit if fewer than 6 complete months exist).
- Also report `month_to_date` for the current partial month, clearly labeled, never blended into the averages.
- Require at least 1 complete month; confidence scales with history.

**Confidence Factors:**
- ≥ 3 complete months → +0.35
- ≥ 6 complete months → +0.15
- Transfers correctly excluded → +0.25
- Month-over-month variance in the window < 25% → +0.25

**Example:**
> **Average monthly burn: $5,240**
> Over the last 3 complete months you've spent an average of $5,240/month. Your 6-month average is $5,050, so recent months are running slightly hot. August to date: $3,180. Confidence: High

**Payload:**
```json
{
  "burn_3mo": 5240.00,
  "burn_6mo": 5050.00,
  "month_to_date": 3180.00,
  "months_in_window": 3,
  "monthly_series": [
    {"month": "2026-05", "total_debits": 4980.00},
    {"month": "2026-06", "total_debits": 5310.00},
    {"month": "2026-07", "total_debits": 5430.00}
  ]
}
```

---

### 3. Average Monthly Income

**Description:** What a normal month earns the user — the income-side counterpart to Average Monthly Burn, with a breakdown of where the money comes from and how stable it is.

**Computation:**
- Sum confirmed income (`income_confirmed = true`) per complete month, with transfers, refunds, cashback, and rewards excluded per the shared rules.
- `income_3mo` = mean of the trailing 3 complete qualifying months; `income_6mo` = mean of the trailing 6 (omit if fewer exist). Only months with confirmed income qualify.
- Also report `month_to_date` for the current partial month, clearly labeled, never blended into the averages.
- Break the window totals down by income category (salary / interest / rental / gig / other) and by source: group income transactions by normalized payer name, reusing the merchant-normalization helper.
- For each source, report observed cadence (e.g., biweekly payroll) and a stability flag — `stable` when the source appears in every qualifying month with amounts within 15%, `variable` otherwise.
- If no confirmed income exists at all, fall back to `is_income_candidate = true` totals, reduce confidence by 0.20, and flag the fallback in the payload (same convention as Savings Rate, which shares this computation).

**Confidence Factors:**
- Uses confirmed income exclusively → +0.35
- ≥ 3 qualifying complete months → +0.25
- Income sources consistent across the window (same payer names) → +0.20
- Transfers and refunds correctly excluded → +0.20

**Example:**
> **Average monthly income: $6,600**
> Over the last 3 complete months you've earned an average of $6,600/month in confirmed income — $6,200 from Contoso payroll (biweekly, stable) and about $400/month from interest and gig income. August to date: $3,300. Confidence: High

**Payload:**
```json
{
  "income_3mo": 6600.00,
  "income_6mo": 6450.00,
  "month_to_date": 3300.00,
  "months_in_window": 3,
  "used_income_fallback": false,
  "by_category": [
    {"income_category": "salary", "monthly_avg": 6200.00},
    {"income_category": "interest", "monthly_avg": 250.00},
    {"income_category": "gig", "monthly_avg": 150.00}
  ],
  "sources": [
    {
      "source": "Contoso Payroll",
      "income_category": "salary",
      "cadence": "biweekly",
      "monthly_avg": 6200.00,
      "stability": "stable",
      "supporting_transaction_ids": [12, 55, 98, 141, 187, 230]
    }
  ],
  "monthly_series": [
    {"month": "2026-05", "confirmed_income": 6600.00},
    {"month": "2026-06", "confirmed_income": 6600.00},
    {"month": "2026-07", "confirmed_income": 6600.00}
  ]
}
```

---

### 4. Fixed vs. Discretionary Baseline

**Description:** The share of monthly spend that is structurally committed versus chosen. The fixed total is the user's *burn-rate floor* — the minimum a month costs them.

**Computation:**
- **Fixed** = (a) all recurring commitments from metric 1, plus (b) debits matching fixed-obligation patterns even when cadence detection hasn't confirmed them: mortgage, rent, loan/lease payment, utilities (electric, gas, water, internet, phone), insurance premiums, tuition/childcare.
- **Discretionary** = all remaining debits (transfers excluded).
- Compute the split against the trailing-3-complete-month average (metric 2 window), not a single month.
- `burn_rate_floor` = average monthly fixed total.
- Pattern lists live alongside the income classifier's regex lists as `_FIXED_OBLIGATION` in a new `services/profile_engine.py` (or extension of `income_classifier.py` conventions).

**Confidence Factors:**
- ≥ 3 complete months → +0.30
- Fixed set includes a detected housing payment (rent/mortgage) → +0.25
- ≥ 80% of fixed total comes from High-confidence recurring detections or explicit pattern matches → +0.25
- Category data available (not predominantly Uncategorized) → +0.20

**Example:**
> **Your baseline: 58% fixed, 42% discretionary**
> Of your $5,240 average monthly spend, $3,040 is structurally committed (rent, utilities, insurance, subscriptions). Your burn-rate floor is $3,040 — the minimum a month costs you even with zero discretionary spending. Confidence: Medium

**Payload:**
```json
{
  "fixed_monthly_avg": 3040.00,
  "discretionary_monthly_avg": 2200.00,
  "fixed_pct": 58.0,
  "burn_rate_floor": 3040.00,
  "fixed_breakdown": [
    {"group": "Housing", "monthly_avg": 1850.00},
    {"group": "Utilities", "monthly_avg": 320.00},
    {"group": "Insurance", "monthly_avg": 458.00},
    {"group": "Subscriptions", "monthly_avg": 412.00}
  ]
}
```

---

### 5. Savings Rate

**Description:** The share of income the user keeps — (income − spend) / income — as a trailing average. The single number users most want and least often compute for themselves.

**Computation:**
- For each complete month with confirmed income: `net = confirmed_income − total_debits` (transfers excluded from both sides); `rate = net / confirmed_income`.
- `savings_rate_3mo` = trailing 3-month aggregate: `Σ net / Σ income` over the window (aggregate ratio, not mean of ratios, so large months weigh appropriately).
- Only months with confirmed income enter the window. If no confirmed income exists at all, fall back to `is_income_candidate = true` totals and reduce confidence by 0.20, with the fallback flagged in the payload.
- The monthly-income figures are the same values computed for Average Monthly Income (metric 3) — one shared computation, two presentations.
- A negative rate is reported as-is (it is the Cashflow Risk story told structurally); do not floor at zero.

**Confidence Factors:**
- Uses confirmed income exclusively → +0.35
- ≥ 3 qualifying complete months → +0.25
- Income sources consistent across the window (same payroll merchants) → +0.20
- Transfers correctly excluded → +0.20

**Example:**
> **Savings rate: 14%**
> Over the last 3 complete months you earned $19,800 in confirmed income and spent $17,030, keeping $2,770 — a 14% savings rate. Confidence: High

**Payload:**
```json
{
  "savings_rate_3mo": 0.14,
  "window_income_total": 19800.00,
  "window_spend_total": 17030.00,
  "window_net_total": 2770.00,
  "months_in_window": 3,
  "used_income_fallback": false,
  "monthly_series": [
    {"month": "2026-05", "income": 6600.00, "spend": 5560.00, "rate": 0.158}
  ]
}
```

---

### 6. Fees & Interest Paid

**Description:** Pure leakage — money paid to financial institutions for nothing. Running totals of bank fees, penalty fees, and interest/finance charges. Users systematically underestimate this number.

**Computation:**
- Classify debit transactions with a new `_FEE_INTEREST` pattern set: overdraft, NSF, monthly service/maintenance fee, ATM fee, wire/transfer fee, foreign transaction fee, late fee/late payment charge, annual fee, interest charge, finance charge, cash advance fee.
- Sub-classify into `bank_fees`, `penalty_fees` (overdraft, NSF, late), `interest`, and `card_fees` (annual, foreign transaction, cash advance).
- Report YTD total, trailing-12-month total (when history allows), and breakdown by sub-type with supporting transactions.
- Zero is a first-class result: "$0 in fees this year" is worth displaying.
- Pattern list lives with the other classifier lists; regression tests follow the income-classification suite conventions.

**Confidence Factors:**
- All matches from explicit fee/interest keywords (no fuzzy matches) → +0.40
- ≥ 6 months of ledger data → +0.25
- No ambiguous matches (e.g., merchant names containing "fee") → +0.20
- Descriptions decrypt and normalize cleanly → +0.15

**Example:**
> **Fees & interest paid: $187 this year**
> You've paid $187 in fees and interest YTD: $95 in credit card interest, $70 in overdraft fees, and $22 in ATM fees. The overdraft fees all occurred in weeks your checking balance ran low late in the pay cycle. Confidence: High

**Payload:**
```json
{
  "ytd_total": 187.00,
  "trailing_12mo_total": 214.00,
  "breakdown": [
    {"sub_type": "interest", "ytd_total": 95.00, "transaction_count": 4},
    {"sub_type": "penalty_fees", "ytd_total": 70.00, "transaction_count": 2},
    {"sub_type": "bank_fees", "ytd_total": 22.00, "transaction_count": 5}
  ],
  "supporting_transaction_ids": [88, 91, 140, 152, 201, 260, 274, 301, 315, 350, 366]
}
```

---

## Backend Architecture

- **`services/profile_engine.py`** — new module owning the six metric computations and the `_FIXED_OBLIGATION` and `_FEE_INTEREST` pattern lists. Consumes `load_ledger` and `resolve_period` from `services/analytics.py`; never re-implements ledger math.
- **Shared recurring detection** — the merchant-normalization and cadence logic specced in Flow 4 (type 4) is factored into a helper both the Insight Feed detector and metrics 1/4 call.
- **Caching** — results may be cached keyed on the latest `import_job_id`; any completed import invalidates. Synchronous computation is acceptable for Phase 1 (same posture as insight generation).
- **Chat integration (later phase)** — profile metrics become candidate tools in the `analytics.py` tool roster so `/api/chat` can answer "what's my savings rate?" from the same source of truth. Out of scope for this flow's initial implementation.

---

## API Contract

### Get Financial Profile

```
GET /api/financial-profile
```

Returns all six metrics in one response. Metrics that cannot be computed (insufficient data) return `"status": "insufficient_data"` with a `requirement` string instead of a payload — the endpoint never 404s because one metric lacks history.

**Response:**
```json
{
  "computed_at": "2026-08-23T18:40:00Z",
  "ledger_months_available": 6,
  "metrics": {
    "committed_monthly_spend": {
      "status": "ok",
      "confidence": 0.86,
      "confidence_label": "high",
      "headline": "Committed monthly spend: $412/month ($4,944/year)",
      "narrative": "You have 14 active recurring commitments...",
      "payload": { }
    },
    "average_monthly_burn": { },
    "average_monthly_income": { },
    "fixed_vs_discretionary": { },
    "savings_rate": { },
    "fees_and_interest": {
      "status": "insufficient_data",
      "requirement": "Import at least 1 complete month of statements."
    }
  }
}
```

No dismiss endpoint, no per-metric IDs — these are views, not events.

---

## Frontend: View Important Page — Financial Profile Module

**Placement:** the insights module at the top of the View Important page, above the episodic Insight Feed entries.

**Layout:** a row/grid of six stat tiles, each with:

- Metric name and headline number (e.g., "$412/mo" with "$4,944/yr" as the secondary figure)
- One-line narrative
- Confidence chip (same component as Insight Feed cards)
- Expand affordance → drill-down panel with the payload detail (commitment list, monthly series, fee breakdown) and linked supporting transactions

**Insufficient-data state:** a tile in `insufficient_data` renders greyed with its `requirement` string ("Import at least 3 complete months to unlock savings rate") rather than hiding — showing users what more data buys them.

**No dismiss control.** Tiles are permanent fixtures of the page.

---

## Minimum Data Requirements

| Metric | Minimum to compute | Full confidence |
|---|---|---|
| Committed Monthly Spend | 2 complete months | 3+ months, 3+ merchants |
| Average Monthly Burn | 1 complete month | 6 complete months |
| Average Monthly Income | 1 complete month with confirmed income | 3 qualifying months, stable sources |
| Fixed vs. Discretionary | 2 complete months | 3+ months with housing detected |
| Savings Rate | 1 complete month with confirmed income | 3 qualifying months |
| Fees & Interest Paid | any data (zero is a valid result) | 6+ months |

---

## Testing

- Unit tests per metric in `tests/test_profile_engine.py`, following the analytics-suite conventions (fast, no network).
- `_FEE_INTEREST` and `_FIXED_OBLIGATION` pattern lists get regression coverage against the real-statement ground truth, mirroring the income-classification suite.
- Run the analytics + profile suites before committing changes to `services/profile_engine.py` or `services/analytics.py`.

---

## Non-Goals for This Flow

- Subscription price-increase tracking (separate spec — natural follow-on to metric 1)
- Upcoming-bills calendar and annual-charge radar (later phase; builds on metric 1's `next_expected_charge`)
- Budget targets or user-set thresholds against these metrics
- Forecasting (projected end-of-month burn, runway)
- Peer benchmarking ("your savings rate vs. similar households")
- Exposure of profile metrics as chat tools (noted above; later phase)
- Historical trend charts beyond the embedded monthly series
