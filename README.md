# PersonalCFO

An AI-driven personal finance app: upload bank/card statements (CSV or PDF), get transactions parsed and classified automatically, review flagged income, and ask a conversational AI assistant questions about your spending, cash flow, and recurring charges — all grounded in your own transaction data.

## Features

- **Statement import** — upload CSV or PDF statements from Chase, Bank of America, Citi, Capital One, American Express, or Wells Fargo. The parser auto-detects the institution and column layout, handles sign conventions (e.g. credit card positive-is-charge), and flags duplicates across uploads.
- **Income review** — credit transactions are classified (salary, interest, rental, gig, refund, transfer, etc.) via regex-based rules, with unclear high-value credits surfaced for manual confirmation.
- **Import summary** — aggregated totals for credits, debits, net cash flow, and confirmed income per import job.
- **Ask CFO (chat)** — a bounded Claude tool-use loop answers natural-language questions about your finances using aggregate tools (spending by category, cash flow summary, income summary, period comparison, recurring charges, transaction search) — the model only ever states numbers returned by these tools, never invents figures.
- **Insights & financial vitals** — automated observations and health metrics derived from the same ledger data.
- **Multi-tenant auth** — email/password and Google Sign-In, with per-user data isolation. All transaction descriptions are encrypted at rest.

## Tech Stack

- **Backend**: FastAPI, SQLModel, Alembic migrations, SQLite (dev) / PostgreSQL (prod), `pdfplumber` for PDF parsing, Fernet encryption, Anthropic Claude for chat/insights.
- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Recharts.

## Getting Started

### Backend (FastAPI)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Generate an encryption key and add it to backend/.env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Copy the example env file and fill in the values (see backend/.env.example)
copy .env.example .env

alembic upgrade head
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`.

### Frontend (Next.js)

```powershell
cd frontend
npm install
npm run dev
```

The app runs at `http://localhost:3000`.

### Environment variables

Copy `backend/.env.example` to `backend/.env` and fill in at least `ENCRYPTION_KEY` and `JWT_SECRET`. `ANTHROPIC_API_KEY` is required for the chat/insights features; without it, `/api/chat` returns HTTP 503. See the file for the full list (Google OAuth, Resend email, Linear feedback integration are all optional).

## Testing

```powershell
# From backend/ — analytics + chat substrate (fast, no network)
pytest tests/test_analytics.py tests/test_chat_service.py tests/test_chat_router.py tests/test_insight_smoke.py -v

# Income classification regression suite (requires real PDF statements on disk, see below)
pytest tests/test_income_classification.py -v

# Live grounding eval for chat (requires ANTHROPIC_API_KEY; skips without it)
pytest tests/test_qa_eval.py -v
```

The income classification suite parses real PDF statements against a user-reviewed ground truth. PDFs are read from `C:\Users\<you>\Downloads\` by default; override with `$env:INCOME_TEST_PDF_DIR`. PDFs are gitignored and never committed — tests skip gracefully for missing files.

```powershell
cd frontend
npm run lint
npm run build
```

## Architecture

The app is built around a multi-step import pipeline:

1. **Upload** — `POST /api/upload` accepts one or more CSV/PDF files, parses and classifies transactions for income, checks for duplicates, and persists them. Returns an `import_job_id`.
2. **Income Review** — `GET /api/import/{job_id}/income-review` returns credit transactions (income candidates first) for the user to confirm or deny.
3. **Summary** — `GET /api/import/{job_id}/summary` returns aggregated totals for the job.

The frontend mirrors this flow: upload on the home page → redirect to `/import/[jobId]/income` → `/import/[jobId]/summary`.

### Backend (`backend/app/`)

- `main.py` — FastAPI app and lifespan setup.
- `config.py` — Pydantic settings loaded from `.env`.
- `database.py` — SQLModel engine and session dependency.
- `models/` — `Transaction`, `ImportJob`, and related tables. Transaction descriptions are Fernet-encrypted at rest.
- `parsers/` — `csv_parser.py` (institution detection + column mapping) and `pdf_parser.py` (table extraction with regex fallback, sign-convention detection).
- `services/` — `income_classifier.py`, `duplicate_detector.py`, `encryption.py`, `analytics.py` (ledger math and chat tool schemas), `chat_service.py` (Claude tool-use loop), `insight_engine.py`.
- `routers/` — `auth`, `upload`, `transactions`, `chat`, `insights`, `financial_profile`, `financial_vitals`, `categories`, `feedback`, `health`, `sandbox`.

### Frontend (`frontend/`)

- Next.js App Router pages: `app/page.tsx`, `app/import/[jobId]/income/page.tsx`, `app/import/[jobId]/summary/page.tsx`, `app/transactions/page.tsx`.
- `lib/api.ts` — all backend calls (base URL via `NEXT_PUBLIC_API_URL`, defaults to `http://localhost:8000`).
- `lib/types.ts` — TypeScript types mirroring backend response shapes.
- `components/` — colocated UI components; local React state, no state management library.

See `CLAUDE.md` for more detailed developer guidance.
