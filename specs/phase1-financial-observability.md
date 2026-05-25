# Phase 1 — AI-Native Financial Observability

## Goal
Enable a user to upload their bank statements (CSV or PDF) and get a clean, normalized view of all transactions — the foundational data layer that AI-driven insight phases will consume.

---

## Functional Requirements

### F1 — Multi-file Upload
- Accept one or more files in a single upload batch (CSV and/or PDF)
- Enforce max 10 MB per file
- Validate file type by content signature (magic bytes), not MIME header

### F2 — Institution Auto-detection
- Detect bank/institution from column headers (CSV) or embedded text (PDF)
- Supported institutions: Chase, Bank of America, Citi, Capital One, American Express, Wells Fargo
- Use confidence scoring; surface institution + confidence to the user
- Non-blocking: unknown institutions yield warnings, not errors

### F3 — Transaction Normalization
Persist every transaction to the canonical schema:

| Field | Type | Notes |
|---|---|---|
| id | int (PK) | auto-increment |
| import_job_id | UUID | groups files in one upload |
| date | date | parsed from statement |
| description | bytes | Fernet-encrypted at rest |
| amount | float | absolute value |
| transaction_type | enum | `debit` / `credit` |
| currency | string | default `USD` |
| account_last4 | string (nullable) | masked from statement |
| institution | string (nullable) | detected bank name |
| source_file_hash | SHA-256 | for duplicate detection |
| is_income_candidate | bool | from classifier |
| income_category | enum (nullable) | salary / interest / rental / gig / other |
| income_confirmed | bool (nullable) | `None` = unreviewed |
| is_ambiguous | bool | `True` if row could not be parsed |
| ambiguity_reason | string (nullable) | human-readable parse failure reason |
| is_duplicate | bool | same date+amount+type from different file |

### F4 — Income Classification
Rule/pattern-based classification of credit transactions:
- **Salary**: payroll, direct deposit, wages, ACH credit, biweekly, semi-monthly
- **Interest**: interest paid/earned, dividend, APY, capital gain
- **Rental**: rent received, lease, tenant, Airbnb, VRBO
- **Gig**: PayPal, Venmo, Stripe, DoorDash, Uber, Upwork, Fiverr, freelance, consulting
- **Exclusions** (not income): transfer, refund, reversal, cashback, rewards, ATM deposit
- **Other**: credit ≥ $500 with no category match → flagged for user review

### F5 — Income Confirmation Screen
- Show all credits grouped: "Likely Income" (auto-detected, pre-checked) and "Other Credits"
- User can toggle each transaction and assign/change income category
- Skippable: proceeding without confirming leaves `income_confirmed = None` (unreviewed flag)
- Summary warns if unreviewed income candidates exist

### F6 — Import Summary
Display after income review:
- Per-file: filename, institution, confidence, transaction count, date range, credit/debit totals, income candidate count, duplicate count, ambiguous count, warnings
- Job-level: total transactions, total credits, total debits, net cash flow, confirmed income amount + count, unreviewed income count, duplicate count, ambiguous count

### F7 — Ambiguous Item Handling
- Rows that fail to parse are saved as Transaction records with `is_ambiguous = True` and `ambiguity_reason` populated
- Ambiguous items are non-blocking: import completes; ambiguous rows appear in summary count
- Users can later identify and review which specific rows were ambiguous

### F8 — Duplicate Detection
- A transaction is a duplicate if another record exists with the same `date`, `amount`, and `transaction_type` from a **different** `source_file_hash`
- Duplicates are saved with `is_duplicate = True` (non-blocking)
- Duplicate count surfaced in summary and transaction table

### F9 — Transaction Table
- View all imported transactions with columns: date, description (decrypted), amount, type, institution, income category, flags (duplicate, ambiguous)
- Filter by type (debit/credit), income status, flag
- Sort by date (asc/desc)

---

## Security Requirements

### S1 — Files never written to disk
Raw file bytes are processed in memory only; no temp files.

### S2 — Description encryption
`description` field encrypted with Fernet (AES-128-CBC) before DB write; decrypted on read. Key sourced from `ENCRYPTION_KEY` env var.

### S3 — Account number masking
Account numbers extracted from statements and stored as last 4 digits only (`account_last4`). Full numbers never persisted.

### S4 — Input validation
File content validated by magic bytes; size capped at 10 MB per file before parsing begins.

### S5 — No financial data in logs
Transaction descriptions, amounts, and account numbers must not appear in any log output.

---

## Frontend Flow

```
Upload page  →  Income Review  →  Import Summary  →  Transactions Table
(/)              (/import/[id]/income)  (/import/[id]/summary)  (/transactions)
```

---

## Out of Scope for Phase 1
- Authentication / user accounts (anonymous session only)
- Spending categories (Phase 2)
- AI-generated insights (Phase 3+)
- Budget rules or alerts
- Multi-currency conversion
