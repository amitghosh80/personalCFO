# Flow 4: Insight Feed

## Overview

The Insight Feed is the intelligence layer of personalCFO. After transactions are imported and normalized (Flows 1–3), the system analyzes the unified transaction dataset and surfaces actionable financial insights automatically.

Insights are generated server-side, stored persistently, and presented to the user as a prioritized feed — ordered by severity and recency. Each insight is self-contained: it explains what happened, shows the evidence, states how confident the system is, and suggests a concrete next step.

The Insight Feed is not a dashboard of charts. It is a push-style alert surface, closer to a smart inbox than a reporting tool. The user should be able to scan it in 60 seconds and know what matters most about their finances.

---

## Design Principles

**Ground everything in data.** Every insight must link to specific transactions. Assertions without evidence are not surfaced.

**Be honest about uncertainty.** Confidence scores are shown to the user. Low-confidence insights are labeled as such rather than suppressed.

**Avoid insight fatigue.** De-duplicate and suppress near-identical insights. Prefer one high-quality insight over three redundant ones.

**Respect the user's context.** Transfers between accounts must be excluded from spending and income computations. Refunds, cashback, and rewards credits must be excluded from income.

**Make the next step obvious.** Every insight ends with a concrete suggested action — not "consider reviewing your finances."

---

## Insight Data Model

Each insight is stored as a record in a new `Insight` table.

| Field | Type | Notes |
|---|---|---|
| id | int (PK) | auto-increment |
| import_job_id | UUID (FK) | job that triggered generation |
| insight_type | enum | see Insight Types below |
| title | string | short, plain-English headline |
| explanation | string | 2–4 sentence narrative |
| severity | enum | `low` / `medium` / `high` |
| confidence | float | 0.0–1.0 |
| confidence_label | enum | `low` / `medium` / `high` |
| time_period_start | date | start of observation window |
| time_period_end | date | end of observation window |
| supporting_transaction_ids | JSON array of int | FK references to Transaction.id |
| suggested_next_step | string | one concrete action |
| is_dismissed | bool | user has dismissed this insight |
| created_at | datetime | generation timestamp |
| metadata | JSON | type-specific detail payload (see each type) |

### Confidence Label Thresholds

| Score | Label |
|---|---|
| ≥ 0.80 | High |
| 0.55–0.79 | Medium |
| < 0.55 | Low |

### Severity Assignment

Severity reflects urgency and financial impact, not confidence. A high-confidence observation about a small change is still `low` severity. The rules per insight type are defined in each section below.

---

## Insight Types

### 1. Spending Increase

**Description:** Spending in a category or overall is meaningfully higher in the current period than the historical baseline.

**Detection Logic:**
- Compute total debits per category (or overall) for the current month.
- Compare against the rolling 3-month average for the same scope.
- Trigger if current period exceeds baseline by ≥ 20%.
- Require at least 3 months of historical data. If fewer months are available, lower confidence accordingly.
- Exclude transfers and refunds from the calculation.

**Severity:**
- `low`: 20–34% increase, or absolute delta < $100
- `medium`: 35–74% increase, or absolute delta $100–$499
- `high`: ≥ 75% increase, or absolute delta ≥ $500

**Confidence Factors:**
- Full 3-month baseline available → +0.30
- Category auto-detected (not "Uncategorized") → +0.20
- ≥ 5 supporting transactions → +0.20
- Current month is complete (all days elapsed) → +0.15
- Transfers correctly excluded → +0.15

**Example:**
> **Dining spend increased 38% in April**
> You spent $1,240 on dining in April, compared with your 3-month average of $897. The increase was mainly driven by 5 transactions over $100. Confidence: High
> Suggested next step: Review the 5 large dining transactions to determine if any were one-time events.

**Metadata payload:**
```json
{
  "category": "Dining",
  "current_period_amount": 1240.00,
  "baseline_amount": 897.00,
  "pct_change": 38.2,
  "driver_transaction_count": 5
}
```

---

### 2. Spending Decrease

**Description:** Spending in a category or overall is meaningfully lower than the historical baseline — a positive signal worth acknowledging.

**Detection Logic:**
- Same computation as Spending Increase, but triggered when current period is ≥ 15% below baseline.
- Require at least 3 months of historical data.
- Only surface if the category had meaningful activity in the baseline period (average ≥ $50/month), to avoid surfacing noise from sparse categories.

**Severity:**
- Always `low` — a spending decrease is informational, not a risk signal.

**Confidence Factors:** Same structure as Spending Increase.

**Example:**
> **Subscriptions spending down 22% in May**
> You spent $148 on subscriptions in May vs. your $190 monthly average. This may reflect a recent cancellation. Confidence: Medium
> Suggested next step: Confirm this reduction is intentional — make sure you haven't lost access to a service you need.

**Metadata payload:**
```json
{
  "category": "Subscriptions",
  "current_period_amount": 148.00,
  "baseline_amount": 190.00,
  "pct_change": -22.1
}
```

---

### 3. Income Change

**Description:** Confirmed income in the current month is materially different from the prior period — either a drop (risk) or an increase (positive).

**Detection Logic:**
- Sum all transactions where `income_confirmed = true` for the current month.
- Compare against the average of the prior 2 confirmed-income months.
- Trigger if the delta exceeds ±15%.
- Only include confirmed income (not unreviewed candidates) to avoid false signals.
- If no confirmed income exists, fall back to `is_income_candidate = true` and reduce confidence by 0.20.

**Severity:**
- Income drop: `high` if > 30% drop, `medium` if 15–30% drop
- Income increase: `low` (informational)

**Confidence Factors:**
- Uses confirmed income (not candidates) → +0.35
- ≥ 2 months of prior income data → +0.25
- Income sources are consistent (same merchant/payroll names) → +0.20
- Current month is fully elapsed → +0.20

**Example:**
> **Income appears lower this month**
> Your confirmed income for April was $4,200, down from your $6,800 average over the prior 2 months. This may reflect a missed paycheck, a change in hours, or a one-time prior payment. Confidence: High
> Suggested next step: Review your April income transactions and confirm all income has been imported.

**Metadata payload:**
```json
{
  "current_income": 4200.00,
  "baseline_income": 6800.00,
  "pct_change": -38.2,
  "direction": "decrease"
}
```

---

### 4. Recurring Charge Detected

**Description:** A transaction pattern suggests a subscription or recurring charge — useful for tracking ongoing financial commitments.

**Detection Logic:**
- Group transactions by normalized merchant name (lowercased, stripped of date suffixes, order numbers).
- A recurring charge is detected when the same merchant appears in ≥ 2 consecutive months with amounts within 10% of each other.
- Detect cadences: monthly, weekly, annual. Annual is detected when a same-merchant charge appears exactly once per year for 2+ years, or matches a known annual billing pattern (e.g., Amazon Prime, Adobe annual).
- Classify as recurring only if `transaction_type = debit`.

**Severity:**
- `low`: recurring charge ≤ $20/month
- `medium`: $20–$100/month
- `high`: > $100/month

**Confidence Factors:**
- ≥ 3 consecutive occurrences → +0.35
- Amount variance < 5% → +0.25
- Merchant name matches known subscription list → +0.20
- Consistent day-of-month (within ±3 days) → +0.20

**Example:**
> **Recurring charge detected: Adobe Creative Cloud**
> Adobe Creative Cloud has charged $59.99 monthly for at least 4 months. Total committed: $239.96/year. Confidence: High
> Suggested next step: Verify this subscription is still in active use.

**Metadata payload:**
```json
{
  "merchant": "Adobe Creative Cloud",
  "cadence": "monthly",
  "amount_per_period": 59.99,
  "occurrences_detected": 4,
  "annualized_cost": 719.88
}
```

---

### 5. Possible Duplicate Charge

**Description:** Two or more charges to the same merchant for the same (or near-identical) amount within a short window — may indicate a billing error or unintentional double-charge.

**Detection Logic:**
- Within any 7-day window, find debit transactions to the same normalized merchant name where amounts are within 2% of each other.
- Exclude transactions already flagged as `is_duplicate = true` (import-level duplicates from different files — this insight targets same-file duplicates that were legitimately imported but may represent a billing error).
- Do not trigger for merchants known to have frequent same-amount repeat charges (grocery stores, transit, parking) — use a merchant exclusion list.

**Severity:**
- `low`: duplicate amount < $20
- `medium`: $20–$100
- `high`: > $100

**Confidence Factors:**
- Same exact amount → +0.40
- Same date → +0.30
- Merchant is not on high-frequency exclusion list → +0.20
- Amount > $50 → +0.10

**Example:**
> **Possible duplicate charge: Spotify**
> Spotify charged $9.99 twice on March 14 and March 15. This may be a billing error. Confidence: High
> Suggested next step: Check your Spotify billing history and contact support if both charges are confirmed.

**Metadata payload:**
```json
{
  "merchant": "Spotify",
  "amount": 9.99,
  "transaction_dates": ["2026-03-14", "2026-03-15"],
  "days_apart": 1
}
```

---

### 6. Large Unusual Expense

**Description:** A single transaction is unusually large relative to the user's typical spending behavior.

**Detection Logic:**
- Compute the user's median single-transaction debit amount across all historical data.
- Compute the 95th percentile of single-transaction debit amounts.
- Trigger when a new debit transaction exceeds the 95th percentile AND is > 2× the median.
- Require at least 30 prior transactions to establish a reliable baseline.
- Exclude transfers, mortgage/rent payments (these are expected to be large), and known recurring large bills.

**Severity:**
- `medium`: transaction is in 95th–98th percentile
- `high`: transaction is above 98th percentile

**Confidence Factors:**
- ≥ 30 prior transactions for baseline → +0.35
- Transaction is not a transfer → +0.25
- Transaction is not a known recurring bill → +0.25
- Amount exceeds 2× median → +0.15

**Example:**
> **Unusually large expense: $2,400 at Best Buy**
> This Best Buy charge on April 3 is more than 3× your typical transaction amount ($680 median). It may be an intentional large purchase. Confidence: High
> Suggested next step: Confirm this was an intended purchase and consider whether it should be categorized as a one-time capital expense.

**Metadata payload:**
```json
{
  "merchant": "Best Buy",
  "amount": 2400.00,
  "user_median_transaction": 680.00,
  "user_p95_transaction": 1100.00,
  "multiple_of_median": 3.53
}
```

---

### 7. Merchant/Category Spike

**Description:** Spending at a specific merchant — rather than an entire category — has spiked relative to that merchant's own historical baseline. Complements the broader category-level Spending Increase insight.

**Detection Logic:**
- For each merchant appearing in the current month, compare current-month total against the merchant's rolling 3-month average.
- Trigger when current month exceeds the average by ≥ 40% AND the absolute delta is ≥ $50.
- Require the merchant to have appeared in at least 2 of the prior 3 months to establish a baseline.
- Do not surface this insight if a Spending Increase insight for the same category was already generated — prefer the broader insight to avoid redundancy. Surface the merchant-level insight only when the category-level insight was not triggered.

**Severity:**
- `low`: 40–74% spike, delta $50–$199
- `medium`: 75–149% spike, or delta $200–$499
- `high`: ≥ 150% spike, or delta ≥ $500

**Confidence Factors:**
- Merchant appears in all 3 baseline months → +0.30
- Auto-detected merchant name (not raw description) → +0.25
- Amount variance in baseline period < 20% → +0.25
- Current month is fully elapsed → +0.20

**Example:**
> **Amazon spending up 91% in April**
> You spent $620 at Amazon in April, compared to your 3-month average of $325. Confidence: Medium
> Suggested next step: Review April Amazon charges to identify any large or unexpected orders.

**Metadata payload:**
```json
{
  "merchant": "Amazon",
  "current_period_amount": 620.00,
  "baseline_amount": 325.00,
  "pct_change": 90.8,
  "category": "Shopping"
}
```

---

### 8. Cashflow Risk

**Description:** The user's net cashflow (income minus expenses) is negative or narrowing dangerously — a forward-looking risk signal.

**Detection Logic:**
- Compute net cashflow for the current month: confirmed income minus total debits (excluding transfers).
- Trigger if net cashflow is negative, OR if net cashflow is positive but ≤ 10% of total income (very thin margin).
- Additionally trigger a "narrowing" variant if net cashflow this month is ≥ 30% lower than the prior month's net, even if still positive.
- Require at least 2 months of data to evaluate trends; surface a lower-confidence version on first month if net is negative.

**Severity:**
- `medium`: Thin margin (positive cashflow ≤ 10% of income), or narrowing trend
- `high`: Negative net cashflow for the month

**Confidence Factors:**
- Uses confirmed income (not candidates) → +0.35
- Current month is fully elapsed → +0.25
- Transfers correctly excluded → +0.20
- ≥ 2 months of prior data → +0.20

**Example:**
> **Cashflow risk: spending exceeded income in March**
> Your confirmed income for March was $5,200, but total expenses were $5,890, leaving a net outflow of -$690. This is the first month where spending has exceeded income in your imported data. Confidence: High
> Suggested next step: Identify which expense categories drove the overage and determine if any are reducible next month.

**Metadata payload:**
```json
{
  "period": "2026-03",
  "confirmed_income": 5200.00,
  "total_expenses": 5890.00,
  "net_cashflow": -690.00,
  "prior_month_net_cashflow": 1100.00,
  "variant": "negative"
}
```

---

### 9. Transfer Detection

**Description:** One or more transactions appear to be transfers between the user's own accounts — important to flag so they are excluded from income and expense totals and do not distort financial analysis.

**Detection Logic:**
- A transfer pair is detected when a debit and a credit occur within 3 business days for the same or near-identical amount (within 1%).
- Additional signals that increase confidence: description contains keywords (`transfer`, `zelle`, `wire`, `ACH`, `from checking`, `to savings`, `own transfer`), or the counterpart account is one of the user's other imported accounts.
- Transfers that are already classified by the income classifier as exclusions (`_NOT_INCOME` pattern match) are auto-marked; this insight surfaces any remaining untagged probable transfers.
- Do not surface this insight if the transaction is already `income_confirmed = false` and manually reviewed.

**Severity:**
- Always `low` — this is a data-quality signal, not a financial risk.

**Confidence Factors:**
- Matching debit/credit pair found within 3 days → +0.40
- Amount match within 0.1% → +0.20
- Description contains transfer keywords → +0.25
- Counterpart account is another imported account → +0.15

**Example:**
> **Likely transfer detected: $3,000 on April 5**
> A $3,000 credit on April 5 closely matches a $3,000 debit on April 4 from another imported account. These may be an internal transfer rather than income or an expense. Confidence: High
> Suggested next step: Confirm these are internal transfers so they are excluded from your income and cashflow totals.

**Metadata payload:**
```json
{
  "credit_transaction_id": 1042,
  "debit_transaction_id": 881,
  "amount": 3000.00,
  "days_apart": 1,
  "match_basis": "amount_and_keyword"
}
```

---

### 10. Subscription Creep

**Description:** The user's total recurring subscription spend has grown over time, even if no single subscription triggered a Recurring Charge Detected insight. This is a portfolio-level pattern — the sum of many small commitments adding up.

**Detection Logic:**
- Identify all transactions classified as recurring (from Recurring Charge Detected insights, or matching the recurring detection criteria) for each month in the dataset.
- Sum recurring spend per month.
- Trigger if total recurring spend in the current month is ≥ 20% higher than the earliest month with sufficient data, AND the absolute delta is ≥ $30.
- Require at least 2 months of data. Require at least 3 distinct recurring merchants to avoid surfacing this for users with a single subscription.

**Severity:**
- `low`: increase $30–$99, or < 35% growth
- `medium`: increase $100–$249, or 35–74% growth
- `high`: increase ≥ $250, or ≥ 75% growth

**Confidence Factors:**
- ≥ 3 months of data → +0.30
- ≥ 3 distinct recurring merchants identified → +0.30
- Recurring merchants identified with High confidence → +0.25
- Current month is fully elapsed → +0.15

**Example:**
> **Subscription creep: monthly recurring spend up $94 since January**
> Your total recurring subscription spend has grown from $187/month in January to $281/month in April — a 50% increase. The additions include YouTube Premium, Duolingo, and a second cloud storage plan. Confidence: Medium
> Suggested next step: Review your full subscription list and cancel any services you're not actively using.

**Metadata payload:**
```json
{
  "earliest_month": "2026-01",
  "earliest_month_total": 187.00,
  "current_month_total": 281.00,
  "absolute_delta": 94.00,
  "pct_change": 50.3,
  "new_merchants_detected": ["YouTube Premium", "Duolingo", "iCloud+"]
}
```

---

## Insight Generation Pipeline

### Trigger

Insight generation runs automatically at the end of a successful import job, after the Income Review step is completed (or skipped). It can also be re-triggered manually via the UI.

### Processing Order

1. Load all non-duplicate, non-ambiguous transactions for the user (across all import jobs, not just the current one).
2. Exclude transactions flagged as transfers.
3. Run all 10 detectors in sequence. Each detector returns zero or more candidate insights.
4. Apply de-duplication: if two insights of the same type and same time period already exist in the DB with `is_dismissed = false`, suppress the new one.
5. Compute confidence scores and severity labels.
6. Persist to the `Insight` table.
7. Return the feed ordered by: severity (high first), then confidence (high first), then created_at (newest first).

### Minimum Data Requirements

If fewer than 2 months of data are available across all imported files, suppress all comparative insights (types 1, 2, 3, 7, 8, 10) and surface only non-comparative insights (4, 5, 6, 9) with a feed-level notice: "Import more statements to unlock trend-based insights."

---

## API Contract

### Generate Insights

```
POST /api/import/{job_id}/generate-insights
```

Triggers insight generation for the job. Runs synchronously for Phase 1 (async queue in a later phase). Returns the generated insight IDs.

**Response:**
```json
{
  "job_id": "uuid",
  "insights_generated": 7,
  "insight_ids": [1, 2, 3, 4, 5, 6, 7]
}
```

### Get Insight Feed

```
GET /api/insights
```

Returns all non-dismissed insights for the user, ordered by severity and confidence.

**Query parameters:**
- `severity` — filter by `low`, `medium`, `high`
- `type` — filter by insight type enum value
- `include_dismissed` — boolean, default `false`

**Response:**
```json
{
  "insights": [
    {
      "id": 1,
      "insight_type": "cashflow_risk",
      "title": "Cashflow risk: spending exceeded income in March",
      "explanation": "Your confirmed income for March was $5,200...",
      "severity": "high",
      "confidence": 0.88,
      "confidence_label": "high",
      "time_period_start": "2026-03-01",
      "time_period_end": "2026-03-31",
      "supporting_transaction_ids": [42, 71, 88],
      "suggested_next_step": "Identify which expense categories drove the overage...",
      "is_dismissed": false,
      "created_at": "2026-05-25T10:32:00Z",
      "metadata": { ... }
    }
  ],
  "total": 7,
  "high_severity_count": 1,
  "medium_severity_count": 3,
  "low_severity_count": 3
}
```

### Dismiss Insight

```
PATCH /api/insights/{insight_id}/dismiss
```

Marks an insight as dismissed. Dismissed insights are excluded from the default feed but available via `include_dismissed=true`.

---

## Frontend: Insight Feed Page

**Route:** `/insights`

**Layout:** Vertical card feed, most severe at top. Each card contains:

- Severity badge (color-coded: red = high, amber = medium, blue = low)
- Insight type label (e.g., "Cashflow Risk", "Subscription Creep")
- Title (bold headline)
- Explanation (2–4 sentence narrative)
- Confidence chip ("High confidence" / "Medium confidence" / "Low confidence")
- Time period (e.g., "April 2026")
- Supporting transactions: expandable list of linked transaction rows
- Suggested next step (highlighted call-to-action)
- Dismiss button

**Empty state:** If no insights are generated (e.g., insufficient data), show: "Not enough data yet — import at least 2 months of statements to unlock your Insight Feed."

**Filter bar:** Pill-style filters for severity and insight type. Defaults to all non-dismissed, all types.

---

## Insight Type Enum Values

For API and DB use:

| Enum Value | Display Name |
|---|---|
| `spending_increase` | Spending Increase |
| `spending_decrease` | Spending Decrease |
| `income_change` | Income Change |
| `recurring_charge` | Recurring Charge Detected |
| `duplicate_charge` | Possible Duplicate Charge |
| `large_expense` | Large Unusual Expense |
| `merchant_spike` | Merchant/Category Spike |
| `cashflow_risk` | Cashflow Risk |
| `transfer_detected` | Transfer Detection |
| `subscription_creep` | Subscription Creep |

---

## Non-Goals for This Flow

- Push notifications or email alerts (later phase)
- User-configurable insight thresholds (later phase)
- Forecasting or predictive insights (later phase)
- Personalized benchmarking against peer cohorts (later phase)
- NLP-generated insight text via LLM (later phase — Phase 1 uses templated strings)
- Insight snooze/remind-me-later (later phase)
