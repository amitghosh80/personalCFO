# Phase 1 Requirements: AI-Native Financial Observability

## Product Vision

Build the first value layer of a Personal CFO: a financial observability system that helps users understand what is happening across their fragmented financial life and why.

Phase 1 is not a budgeting app. It is a unified financial intelligence layer that ingests user-uploaded statements, normalizes transactions, detects patterns, surfaces insights, and allows users to ask questions about their financial activity in natural language.

---

## Phase 1 Goals

1. Consolidate financial activity across multiple uploaded statements.
2. Normalize transactions into a unified financial timeline.
3. Detect income, expenses, recurring transactions, transfers, and anomalies.
4. Generate cashflow summaries and explain major financial changes.
5. Provide natural-language financial Q&A grounded in uploaded data.
6. Build user trust through transparency, traceability, and confidence scores.

---

## Non-Goals for Phase 1

Do not build these yet:

- Bank account linking via Plaid/MX/Finicity
- Investment advice
- Tax advice
- Automated bill payment
- Automated money movement
- Subscription cancellation
- Credit score monitoring
- Full mobile app
- Multi-user household collaboration
- Regulated financial planning recommendations

---

# Core User Flows

## Flow 1: Upload Statements

User uploads one or more financial files.

Supported file types for Phase 1:

- PDF bank statements
- PDF credit card statements
- CSV transaction exports

System should:

1. Accept multiple files.
2. Detect institution/account if possible.
3. Extract transactions.
4. Normalize transactions into canonical schema.
5. Show import summary.
6. Ask user to confirm ambiguous items.

---

## Flow 2: View Unified Financial Timeline

User sees all transactions across accounts in one place.

Timeline should support:

- Date filtering
- Account filtering
- Institution filtering
- Income vs expense filtering
- Category filtering
- Search by merchant/description
- Sort by date or amount

Each transaction should show:

- Date
- Merchant/description
- Amount
- Account/institution
- Category
- Transaction type
- Confidence score
- Source file reference

---

## Flow 3: Cashflow Summary

User sees monthly cashflow.

For each month, show:

- Total income
- Total expenses
- Net cashflow
- Fixed expenses
- Variable expenses
- Recurring income
- Recurring expenses
- One-time large expenses
- Transfers excluded from income/expense totals

Example:

```text
March 2026:
Income: $14,500
Expenses: $11,200
Net Cashflow: +$3,300
Major drivers: mortgage, childcare, travel, dining