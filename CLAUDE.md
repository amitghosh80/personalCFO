# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (FastAPI)
```powershell
# From backend/
.venv\Scripts\activate
pip install -r requirements.txt   # first time
uvicorn app.main:app --reload     # runs on http://localhost:8000
```

Generate an encryption key (required before first run):
```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Copy the output into `backend/.env` as `ENCRYPTION_KEY=...`.

### Frontend (Next.js)
```powershell
# From frontend/
npm install   # first time
npm run dev   # runs on http://localhost:3000
npm run build
npm run lint
```

### Tests (income classification regression suite)
```powershell
# From backend/ — install pytest once, then run any time classification logic changes
pip install pytest
pytest tests/test_income_classification.py -v
pytest tests/test_income_classification.py -v --tb=short   # brief failure detail
pytest tests/test_income_classification.py -v -k "FirstTech"  # one class only
```

The suite (53 tests, ~12 s) parses 8 real PDF statements and asserts expected
classification for every ground-truth transaction from the user-reviewed Excel.
PDF files are read from `C:\Users\amitg\Downloads\` by default; override with:
```powershell
$env:INCOME_TEST_PDF_DIR = "C:\path\to\pdfs"
pytest tests/test_income_classification.py -v
```
PDFs are in `.gitignore` — they must exist on disk but are never committed.
Tests skip gracefully for any file that is not found.

**Run the suite before committing any change to:**
- `backend/app/parsers/pdf_parser.py`
- `backend/app/services/income_classifier.py`
- `backend/app/parsers/institution_profiles.py`

### Tests (chat substrate)
```powershell
# From backend/ — fast, no network:
pytest tests/test_analytics.py tests/test_chat_service.py tests/test_chat_router.py tests/test_insight_smoke.py -v

# Live grounding eval (requires ANTHROPIC_API_KEY; skips without it):
pytest tests/test_qa_eval.py -v
```

**Run the analytics + chat suite before committing any change to:**
- `backend/app/services/analytics.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/insight_engine.py` (shares the ledger loader with analytics)

### Environment
Copy `backend/.env.example` to `backend/.env` and fill in `ENCRYPTION_KEY`. The SQLite database (`personalcfo.db`) is created automatically on first run in the directory where uvicorn is launched.

The conversational chat feature requires `ANTHROPIC_API_KEY` in `backend/.env`.
The model is configurable via `chat_model` (default `claude-sonnet-4-6`). Without a
key, `/api/chat` returns HTTP 503 and the live grounding eval skips.

## Architecture

### Import Flow (the core feature)
The app is built around a multi-step import pipeline:

1. **Upload** — `POST /api/upload` accepts one or more CSV/PDF files. Each file is parsed, transactions are classified for income, checked for duplicates, and persisted. Returns an `import_job_id` (UUID).
2. **Income Review** — `GET /api/import/{job_id}/income-review` returns all credit transactions for the job (income candidates first). The user confirms or denies each via `PATCH /api/import/{job_id}/income-review`.
3. **Summary** — `GET /api/import/{job_id}/summary` returns aggregated totals (credits, debits, net cash flow, confirmed income).

The frontend mirrors this: `app/page.tsx` → upload → redirects to `/import/[jobId]/income` → then `/import/[jobId]/summary`.

### Backend (`backend/app/`)
- **`main.py`** — FastAPI app, CORS wired to `localhost:3000`, lifespan hook creates DB tables.
- **`config.py`** — Pydantic settings loaded from `.env`; `get_fernet()` provides the Fernet instance for encryption.
- **`database.py`** — SQLite engine via SQLModel; `get_session()` is the FastAPI dependency.
- **`models/`** — Two SQLModel tables: `Transaction` (all fields) and `ImportJob` (tracks job status: `processing → pending_income_review → completed`). Transaction `description` is stored as `bytes` (Fernet-encrypted).
- **`parsers/`** — `csv_parser.py` detects the bank via `institution_profiles.py` (column-matching scored 0.7–1.0), then extracts rows. `pdf_parser.py` uses `pdfplumber` with table extraction first, line-by-line regex fallback if tables yield nothing. Institution is detected from **first-page text only** to avoid false matches on institution names that appear inside transaction descriptions (e.g. "AMEX EPAYMENT" in a First Tech checking statement). Sign convention is detected via `_needs_pdf_sign_inversion()`: if a payment-acknowledgment line (e.g. "Payment Thank You") carries a negative amount, the document uses positive=charge convention and all signs are inverted. This correctly handles Chase and Amex credit card PDFs.
- **`services/`** — `income_classifier.py` uses regex pattern lists (`_SALARY`, `_INTEREST`, `_RENTAL`, `_GIG`, `_NOT_INCOME`, `_EXCLUDE_FROM_REVIEW`) to classify credits. Credits ≥$500 with no match are flagged as `other`. `_NOT_INCOME` excludes transfers, CC payments, refunds, rewards, and explicit outflows (ACH Debit, ATM Withdrawal, POS Transaction). `_EXCLUDE_FROM_REVIEW` is a stricter subset: credit transactions matching it are hidden from the income-review UI entirely (CC payment confirmations, statement metadata). `exclude_from_review()` is called in the income-review endpoint after decryption. `duplicate_detector.py` flags a transaction if an identical (date + amount + type) exists from a *different* source file hash. `encryption.py` wraps Fernet encrypt/decrypt.
- **`services/analytics.py`** — single source of truth for ledger math: `load_ledger`,
  `resolve_period`, and the six aggregate-first tools (`spending_by_category`,
  `cashflow_summary`, `income_summary`, `compare_periods`, `recurring_charges`,
  `search_transactions`) plus their Anthropic tool schemas and `dispatch_tool`.
  `services/chat_service.py` runs a bounded Claude tool-use loop over these tools
  (`POST /api/chat`); the model states only tool-returned numbers. `search_transactions`
  is the only tool exposing raw descriptions and is row-capped at 100.

### Institution Profiles (CSV)
`institution_profiles.py` defines `InstitutionProfile` dataclasses for Chase, Bank of America, Citi, Capital One, American Express, and Wells Fargo. Each profile specifies which columns are required/optional, how to read the date, and whether to use a single signed `amount_col` or separate `debit_col`/`credit_col`. American Express uses `invert_sign=True` (positive = charge). Detection requires all required columns to be present; optional columns raise the confidence score above the 0.7 threshold.

### Frontend (`frontend/`)
- **App Router** (Next.js 14) with pages at `app/page.tsx`, `app/import/[jobId]/income/page.tsx`, `app/import/[jobId]/summary/page.tsx`, and `app/transactions/page.tsx`.
- **`lib/api.ts`** — All backend calls. Base URL defaults to `http://localhost:8000`; override with `NEXT_PUBLIC_API_URL` in `.env.local`.
- **`lib/types.ts`** — TypeScript types mirroring backend response shapes (`Transaction`, `FileResult`, `UploadResult`, `ImportSummary`).
- Components are colocated in `components/` (`FileUploader`, `IncomeReview`, `ImportSummary`, `TransactionTable`). No state management library; state is local React state with fetch calls.
