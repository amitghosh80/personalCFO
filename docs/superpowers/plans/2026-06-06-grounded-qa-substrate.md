# Grounded Q&A Substrate + Conversational Chat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user ask natural-language questions about their imported finances and get answers whose every number is computed by deterministic tools, never invented by the model.

**Architecture:** A tool-calling loop between Claude and the existing SQLite ledger. A new `analytics.py` holds aggregate-first, deterministic query functions (the "tools"); `chat_service.py` runs the Anthropic tool-use loop and owns the grounding contract; `routers/chat.py` exposes `POST /api/chat`. The frontend adds a chat page. The only tool that returns raw transaction descriptions is `search_transactions`, and it is row-capped — making "aggregate-first" structural.

**Tech Stack:** FastAPI + SQLModel + SQLite (backend), Anthropic Python SDK (tool use), Next.js 14 App Router + TypeScript + Tailwind (frontend), pytest (tests).

**Spec:** `docs/superpowers/specs/2026-06-06-grounded-qa-substrate-design.md`

---

## File Structure

**Backend — create:**
- `backend/app/services/analytics.py` — ledger loader, period resolution, the six tool functions, Anthropic tool schemas, dispatcher. The single source of truth for the math.
- `backend/app/services/chat_service.py` — tool-calling loop, system prompt / grounding contract, iteration cap, client injection.
- `backend/app/routers/chat.py` — `POST /api/chat`.
- `backend/tests/conftest.py` — in-memory DB session fixture + `make_txn` helper.
- `backend/tests/test_analytics.py` — deterministic unit tests for every tool.
- `backend/tests/test_chat_service.py` — tool-loop tests with a fake Anthropic client.
- `backend/tests/test_chat_router.py` — endpoint test with a stubbed service.
- `backend/tests/test_qa_eval.py` — real-API grounding eval (skips without key).

**Backend — modify:**
- `backend/app/config.py` — add `chat_model` setting.
- `backend/app/requirements.txt` — add `anthropic`.
- `backend/app/services/insight_engine.py` — delegate ledger loading + transfer detection to `analytics.py` (pure move, behavior-preserving).
- `backend/app/main.py` — include the chat router.

**Frontend — create:**
- `frontend/app/chat/page.tsx` — chat page shell.
- `frontend/components/ChatInterface.tsx` — message thread + input + grounding line.

**Frontend — modify:**
- `frontend/lib/types.ts` — chat types.
- `frontend/lib/api.ts` — `sendChatMessage`.

**Docs — modify:**
- `CLAUDE.md` — chat commands, run-before-commit trigger, `ANTHROPIC_API_KEY` note.

---

## Task 1: Add dependency and chat model config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py:6-11`

- [ ] **Step 1: Add the Anthropic SDK to requirements**

Append to `backend/requirements.txt`:

```
anthropic>=0.40.0
```

- [ ] **Step 2: Install it**

Run (from `backend/`, venv active):
```powershell
pip install "anthropic>=0.40.0"
```
Expected: `Successfully installed anthropic-…`

- [ ] **Step 3: Add the `chat_model` setting**

In `backend/app/config.py`, add the field directly below `ai_categorizer_model`:

```python
class Settings(BaseSettings):
    encryption_key: str = ""
    database_url: str = "sqlite:///./personalcfo.db"
    max_upload_size_mb: int = 10
    anthropic_api_key: str = ""
    ai_categorizer_model: str = "claude-haiku-4-5"
    chat_model: str = "claude-sonnet-4-6"

    class Config:
        env_file = ".env"
```

- [ ] **Step 4: Verify config imports cleanly**

Run (from `backend/`):
```powershell
python -c "from app.config import get_settings; print(get_settings().chat_model)"
```
Expected: `claude-sonnet-4-6`

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/app/config.py
git commit -m "$(cat <<'EOF'
Add anthropic dependency and chat_model setting

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Test harness — conftest with in-memory DB and `make_txn`

This fixture is reused by every backend test below. The ledger stores descriptions Fernet-encrypted, so the helper must encrypt on insert; that requires `ENCRYPTION_KEY` to be set *before* `app.services.encryption` is imported.

**Files:**
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Write conftest**

Create `backend/tests/conftest.py`:

```python
"""Shared pytest fixtures: an isolated in-memory ledger and a row factory.

ENCRYPTION_KEY must be set before app.services.encryption is imported, so we
generate one and clear the settings cache at module import time.
"""
import os
from datetime import date as _date

import pytest
from cryptography.fernet import Fernet

# Must run before any app import that reads settings / builds Fernet.
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from sqlmodel import SQLModel, Session, create_engine  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.models.transaction import Transaction, TransactionType  # noqa: E402
from app.services.encryption import encrypt  # noqa: E402

get_settings.cache_clear()  # pick up the ENCRYPTION_KEY we just set


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",  # in-memory
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_txn(
    session,
    *,
    day: str,
    amount: float,
    txn_type: TransactionType,
    description: str,
    expense_category: str | None = None,
    expense_subcategory: str | None = None,
    is_income_candidate: bool = False,
    income_confirmed: bool | None = None,
    income_category: str | None = None,
    is_duplicate: bool = False,
    is_ambiguous: bool = False,
) -> Transaction:
    t = Transaction(
        import_job_id="job1",
        date=_date.fromisoformat(day),
        description=encrypt(description),
        amount=amount,
        transaction_type=txn_type,
        source_file_hash="hash1",
        expense_category=expense_category,
        expense_subcategory=expense_subcategory,
        is_income_candidate=is_income_candidate,
        income_confirmed=income_confirmed,
        income_category=income_category,
        is_duplicate=is_duplicate,
        is_ambiguous=is_ambiguous,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


@pytest.fixture
def make_txn(session):
    def _factory(**kwargs):
        return _make_txn(session, **kwargs)
    return _factory
```

- [ ] **Step 2: Verify fixtures import**

Run (from `backend/`):
```powershell
pip install pytest httpx
python -c "import tests.conftest; print('ok')"
```
Expected: `ok` (httpx is needed later by TestClient; install now).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "$(cat <<'EOF'
Add pytest fixtures for in-memory ledger and txn factory

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `analytics.py` — ledger loader, transfer detection, period resolution

This task creates the foundation: `load_ledger`, `is_transfer`, `is_spending_txn`, and `resolve_period`. The period resolver is the trickiest pure function and is fully tested with an injected reference date so it's deterministic.

**Files:**
- Create: `backend/app/services/analytics.py`
- Test: `backend/tests/test_analytics.py`

- [ ] **Step 1: Write failing tests for the loader and period resolver**

Create `backend/tests/test_analytics.py`:

```python
from datetime import date

from app.models.transaction import TransactionType
from app.services import analytics

TODAY = date(2026, 6, 6)


def test_load_ledger_decrypts_and_excludes_dupes_and_ambiguous(make_txn):
    make_txn(day="2026-05-01", amount=10.0, txn_type=TransactionType.debit,
             description="STARBUCKS", expense_category="food_and_drink")
    make_txn(day="2026-05-02", amount=99.0, txn_type=TransactionType.debit,
             description="DUPE", expense_category="shopping", is_duplicate=True)
    make_txn(day="2026-05-03", amount=88.0, txn_type=TransactionType.debit,
             description="AMBIG", expense_category="shopping", is_ambiguous=True)

    rows = analytics.load_ledger(_session_of(make_txn))
    assert len(rows) == 1
    assert rows[0]["description"] == "STARBUCKS"
    assert rows[0]["month"] == "2026-05"
    assert rows[0]["expense_category"] == "food_and_drink"


def test_is_transfer_matches_keywords():
    assert analytics.is_transfer("ZELLE PAYMENT TO JOHN")
    assert analytics.is_transfer("ONLINE TRANSFER TO SAVINGS")
    assert not analytics.is_transfer("STARBUCKS STORE 123")


def test_resolve_period_explicit_range():
    s, e, label = analytics.resolve_period(
        {"start": "2026-01-01", "end": "2026-03-31"}, today=TODAY)
    assert (s, e) == (date(2026, 1, 1), date(2026, 3, 31))
    assert "2026-01-01" in label


def test_resolve_period_month_and_quarter_and_year():
    s, e, label = analytics.resolve_period({"month": "2026-05"}, today=TODAY)
    assert (s, e, label) == (date(2026, 5, 1), date(2026, 5, 31), "May 2026")

    s, e, label = analytics.resolve_period({"quarter": "2026-Q1"}, today=TODAY)
    assert (s, e, label) == (date(2026, 1, 1), date(2026, 3, 31), "Q1 2026")

    s, e, label = analytics.resolve_period({"year": "2025"}, today=TODAY)
    assert (s, e, label) == (date(2025, 1, 1), date(2025, 12, 31), "2025")


def test_resolve_period_presets_relative_to_today():
    s, e, label = analytics.resolve_period({"preset": "last_month"}, today=TODAY)
    assert (s, e, label) == (date(2026, 5, 1), date(2026, 5, 31), "May 2026")

    s, e, label = analytics.resolve_period({"preset": "last_quarter"}, today=TODAY)
    assert (s, e, label) == (date(2026, 1, 1), date(2026, 3, 31), "Q1 2026")

    s, e, _ = analytics.resolve_period({"preset": "all_time"}, today=TODAY)
    assert s == date(1970, 1, 1) and e == TODAY


# Helper so tests can reach the session the factory writes to.
def _session_of(make_txn):
    # make_txn closes over the session fixture; expose it via the factory.
    return make_txn.__self_session__
```

NOTE: `_session_of` needs the session. Adjust `conftest.make_txn` fixture to attach it — do Step 2 before running.

- [ ] **Step 2: Expose the session on the factory (conftest tweak)**

In `backend/tests/conftest.py`, update the `make_txn` fixture so tests can read the session back:

```python
@pytest.fixture
def make_txn(session):
    def _factory(**kwargs):
        return _make_txn(session, **kwargs)
    _factory.__self_session__ = session
    return _factory
```

- [ ] **Step 3: Run the tests to verify they fail**

Run (from `backend/`):
```powershell
pytest tests/test_analytics.py -v
```
Expected: FAIL — `ModuleNotFoundError` / `AttributeError: module 'app.services.analytics' has no attribute ...`

- [ ] **Step 4: Implement loader, transfer, spending, period resolution**

Create `backend/app/services/analytics.py`:

```python
"""Aggregate-first analytic queries over the whole transaction ledger.

This module is the single source of truth for the math behind both the
rule-based insight engine and the conversational chat tools. Every public
function is deterministic: given the same ledger and parameters, it returns the
same numbers. The chat layer never computes financial figures itself.
"""
import re
from calendar import monthrange
from collections import defaultdict
from datetime import date

from sqlmodel import Session, select

from ..models.transaction import Transaction, TransactionType
from ..services.encryption import decrypt
from ..services.expense_categorizer import (
    is_spending,
    primary_display,
    subcategory_display,
)

# ─── Transfer detection (moved from insight_engine for shared use) ────────────

_TRANSFER_RE = re.compile(
    r"transfer|zelle|wire|ach\s+(deposit|debit|credit)|"
    r"ext\s+trnsf|from\s+checking|to\s+savings|jpmorgan\s+chase\s+ext",
    re.IGNORECASE,
)


def is_transfer(description: str) -> bool:
    return bool(_TRANSFER_RE.search(description))


def _norm(desc: str) -> str:
    d = desc.upper()
    d = re.sub(r"\*\S+", " ", d)
    d = re.sub(r"#\d+", " ", d)
    d = re.sub(r"\d{3}[.\-]\d{3}[.\-]\d{4}", " ", d)
    d = re.sub(r"\b\d{5,}\b", " ", d)
    words = [w for w in d.split() if len(w) > 1]
    return " ".join(words[:3]).strip()


# ─── Ledger loading ───────────────────────────────────────────────────────────

def load_ledger(session: Session) -> list[dict]:
    """Decrypt and normalize every non-duplicate, non-ambiguous transaction."""
    rows = session.exec(
        select(Transaction)
        .where(Transaction.is_duplicate == False)   # noqa: E712
        .where(Transaction.is_ambiguous == False)    # noqa: E712
        .order_by(Transaction.date)
    ).all()
    result = []
    for t in rows:
        try:
            desc = decrypt(t.description)
        except Exception:
            desc = ""
        result.append({
            "id": t.id,
            "date": t.date,
            "month": t.date.strftime("%Y-%m"),
            "description": desc,
            "amount": t.amount,
            "type": t.transaction_type,
            "is_income_candidate": t.is_income_candidate,
            "income_confirmed": t.income_confirmed,
            "income_category": t.income_category or "other",
            "expense_category": t.expense_category or "other",
            "expense_subcategory": t.expense_subcategory or "other",
        })
    return result


def is_spending_txn(t: dict) -> bool:
    """True for real consumption: a debit that isn't money movement."""
    return (
        t["type"] == TransactionType.debit
        and is_spending(t["expense_category"])
        and not is_transfer(t["description"])
    )


def _in_range(t: dict, start: date, end: date) -> bool:
    return start <= t["date"] <= end


# ─── Period resolution ─────────────────────────────────────────────────────────

def _month_start(y: int, m: int) -> date:
    return date(y, m, 1)


def _month_end(y: int, m: int) -> date:
    return date(y, m, monthrange(y, m)[1])


def _add_months(y: int, m: int, delta: int) -> tuple[int, int]:
    idx = y * 12 + (m - 1) + delta
    return idx // 12, idx % 12 + 1


def resolve_period(period: dict | None, today: date | None = None) -> tuple[date, date, str]:
    """Resolve a period spec to (start, end, human_label). All date math lives
    here so the model never computes dates. `today` is injectable for tests."""
    today = today or date.today()
    period = period or {}

    if period.get("start") and period.get("end"):
        s = date.fromisoformat(period["start"])
        e = date.fromisoformat(period["end"])
        return s, e, f"{s.isoformat()} to {e.isoformat()}"

    if period.get("month"):
        y, m = map(int, period["month"].split("-"))
        return _month_start(y, m), _month_end(y, m), date(y, m, 1).strftime("%B %Y")

    if period.get("quarter"):
        ys, qs = period["quarter"].split("-Q")
        y, q = int(ys), int(qs)
        m1 = (q - 1) * 3 + 1
        ey, em = _add_months(y, m1, 2)
        return _month_start(y, m1), _month_end(ey, em), f"Q{q} {y}"

    if period.get("year"):
        y = int(period["year"])
        return date(y, 1, 1), date(y, 12, 31), str(y)

    preset = period.get("preset", "all_time")
    if preset == "all_time":
        return date(1970, 1, 1), today, "all time"
    if preset == "this_month":
        return _month_start(today.year, today.month), _month_end(today.year, today.month), today.strftime("%B %Y")
    if preset == "last_month":
        y, m = _add_months(today.year, today.month, -1)
        return _month_start(y, m), _month_end(y, m), date(y, m, 1).strftime("%B %Y")
    if preset in ("this_quarter", "last_quarter"):
        q = (today.month - 1) // 3 + 1
        m1 = (q - 1) * 3 + 1
        year = today.year
        if preset == "last_quarter":
            year, m1 = _add_months(today.year, m1, -3)
            q = (m1 - 1) // 3 + 1
        ey, em = _add_months(year, m1, 2)
        return _month_start(year, m1), _month_end(ey, em), f"Q{q} {year}"
    if preset == "this_year":
        return date(today.year, 1, 1), date(today.year, 12, 31), str(today.year)
    if preset == "last_year":
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31), str(today.year - 1)
    if preset in ("last_3_months", "last_6_months", "last_12_months"):
        n = int(preset.split("_")[1])
        y, m = _add_months(today.year, today.month, -(n - 1))
        return _month_start(y, m), today, f"last {n} months"

    raise ValueError(f"Unknown period spec: {period}")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run (from `backend/`):
```powershell
pytest tests/test_analytics.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/analytics.py backend/tests/test_analytics.py backend/tests/conftest.py
git commit -m "$(cat <<'EOF'
Add analytics ledger loader, transfer detection, and period resolver

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `spending_by_category` tool

**Files:**
- Modify: `backend/app/services/analytics.py` (append)
- Test: `backend/tests/test_analytics.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_analytics.py`:

```python
def test_spending_by_category_groups_and_excludes_non_spending(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-02", amount=100.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink", expense_subcategory="groceries")
    make_txn(day="2026-05-10", amount=40.0, txn_type=TransactionType.debit,
             description="CHIPOTLE", expense_category="food_and_drink", expense_subcategory="restaurant")
    make_txn(day="2026-05-15", amount=60.0, txn_type=TransactionType.debit,
             description="SHELL", expense_category="transportation", expense_subcategory="gas")
    # Non-spending: a credit-card payment debit must be excluded.
    make_txn(day="2026-05-20", amount=500.0, txn_type=TransactionType.debit,
             description="CHASE CARD PAYMENT", expense_category="credit_card_payment")
    # Out of period: ignored.
    make_txn(day="2026-04-01", amount=999.0, txn_type=TransactionType.debit,
             description="OLD", expense_category="shopping")

    out = analytics.spending_by_category(s, {"month": "2026-05"}, today=TODAY)

    assert out["total_spending"] == 200.0
    assert out["transaction_count"] == 3
    top = out["by_primary"][0]
    assert top["category"] == "food_and_drink"
    assert top["amount"] == 140.0
    subs = {x["subcategory"]: x["amount"] for x in top["by_subcategory"]}
    assert subs == {"groceries": 100.0, "restaurant": 40.0}


def test_spending_by_category_filtered_to_one_primary(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-02", amount=100.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink", expense_subcategory="groceries")
    make_txn(day="2026-05-15", amount=60.0, txn_type=TransactionType.debit,
             description="SHELL", expense_category="transportation", expense_subcategory="gas")

    out = analytics.spending_by_category(s, {"month": "2026-05"}, primary="transportation", today=TODAY)
    assert out["total_spending"] == 60.0
    assert len(out["by_primary"]) == 1
    assert out["by_primary"][0]["category"] == "transportation"
```

- [ ] **Step 2: Run to verify failure**

```powershell
pytest tests/test_analytics.py -k spending_by_category -v
```
Expected: FAIL — `AttributeError: ... 'spending_by_category'`

- [ ] **Step 3: Implement the tool**

Append to `backend/app/services/analytics.py`:

```python
def spending_by_category(
    session: Session,
    period: dict | None = None,
    primary: str | None = None,
    today: date | None = None,
) -> dict:
    """Total spending broken down by primary category and subcategory.

    Excludes money movement (transfers, credit-card payments, investments) so
    'how much did I spend' is never inflated by offsetting transactions.
    """
    start, end, label = resolve_period(period, today)
    txns = [t for t in load_ledger(session) if _in_range(t, start, end) and is_spending_txn(t)]
    if primary:
        txns = [t for t in txns if t["expense_category"] == primary]

    by_primary: dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "count": 0, "subs": defaultdict(lambda: {"amount": 0.0, "count": 0})})
    for t in txns:
        p = by_primary[t["expense_category"]]
        p["amount"] += t["amount"]
        p["count"] += 1
        sub = p["subs"][t["expense_subcategory"]]
        sub["amount"] += t["amount"]
        sub["count"] += 1

    primaries = []
    for cat, data in by_primary.items():
        subs = [
            {"subcategory": sk, "display": subcategory_display(sk),
             "amount": round(sv["amount"], 2), "count": sv["count"]}
            for sk, sv in sorted(data["subs"].items(), key=lambda kv: kv[1]["amount"], reverse=True)
        ]
        primaries.append({
            "category": cat, "display": primary_display(cat),
            "amount": round(data["amount"], 2), "count": data["count"],
            "by_subcategory": subs,
        })
    primaries.sort(key=lambda x: x["amount"], reverse=True)

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "label": label},
        "total_spending": round(sum(t["amount"] for t in txns), 2),
        "transaction_count": len(txns),
        "by_primary": primaries,
    }
```

- [ ] **Step 4: Run to verify pass**

```powershell
pytest tests/test_analytics.py -k spending_by_category -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/analytics.py backend/tests/test_analytics.py
git commit -m "$(cat <<'EOF'
Add spending_by_category analytic tool

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `cashflow_summary` and `income_summary` tools

**Files:**
- Modify: `backend/app/services/analytics.py` (append)
- Test: `backend/tests/test_analytics.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_analytics.py`:

```python
def test_cashflow_summary_totals_and_by_month(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-01", amount=3000.0, txn_type=TransactionType.credit,
             description="ACME PAYROLL", is_income_candidate=True, income_confirmed=True,
             income_category="salary")
    make_txn(day="2026-05-05", amount=200.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink")
    make_txn(day="2026-06-05", amount=100.0, txn_type=TransactionType.debit,
             description="SHELL", expense_category="transportation")

    out = analytics.cashflow_summary(s, {"start": "2026-05-01", "end": "2026-06-30"}, today=TODAY)
    assert out["total_credits"] == 3000.0
    assert out["total_debits"] == 300.0
    assert out["net_cashflow"] == 2700.0
    assert out["confirmed_income"] == 3000.0
    months = {m["month"]: m for m in out["by_month"]}
    assert months["2026-05"]["debits"] == 200.0
    assert months["2026-06"]["debits"] == 100.0


def test_income_summary_prefers_confirmed_and_groups_by_category(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-01", amount=3000.0, txn_type=TransactionType.credit,
             description="ACME PAYROLL", is_income_candidate=True, income_confirmed=True,
             income_category="salary")
    make_txn(day="2026-05-20", amount=50.0, txn_type=TransactionType.credit,
             description="SAVINGS INTEREST", is_income_candidate=True, income_confirmed=True,
             income_category="interest")
    # Unconfirmed candidate is ignored once confirmed income exists.
    make_txn(day="2026-05-25", amount=999.0, txn_type=TransactionType.credit,
             description="MAYBE INCOME", is_income_candidate=True, income_confirmed=None,
             income_category="other")

    out = analytics.income_summary(s, {"month": "2026-05"}, today=TODAY)
    assert out["basis"] == "confirmed"
    assert out["total_income"] == 3050.0
    by_cat = {c["category"]: c["amount"] for c in out["by_category"]}
    assert by_cat == {"salary": 3000.0, "interest": 50.0}
```

- [ ] **Step 2: Run to verify failure**

```powershell
pytest tests/test_analytics.py -k "cashflow_summary or income_summary" -v
```
Expected: FAIL — attributes missing.

- [ ] **Step 3: Implement both tools**

Append to `backend/app/services/analytics.py`:

```python
def cashflow_summary(session: Session, period: dict | None = None, today: date | None = None) -> dict:
    """Money in vs out for the period. Debits here are ALL outflows (not just
    spending), so net reflects actual account movement; use spending_by_category
    for consumption-only totals."""
    start, end, label = resolve_period(period, today)
    txns = [t for t in load_ledger(session) if _in_range(t, start, end)]

    credits = sum(t["amount"] for t in txns if t["type"] == TransactionType.credit)
    debits = sum(t["amount"] for t in txns if t["type"] == TransactionType.debit)
    confirmed_income = sum(
        t["amount"] for t in txns
        if t["type"] == TransactionType.credit and t["income_confirmed"] is True
    )

    by_month: dict[str, dict] = defaultdict(lambda: {"credits": 0.0, "debits": 0.0, "income": 0.0})
    for t in txns:
        bucket = by_month[t["month"]]
        if t["type"] == TransactionType.credit:
            bucket["credits"] += t["amount"]
            if t["income_confirmed"] is True:
                bucket["income"] += t["amount"]
        else:
            bucket["debits"] += t["amount"]

    months = [
        {"month": m, "credits": round(v["credits"], 2), "debits": round(v["debits"], 2),
         "net": round(v["credits"] - v["debits"], 2), "income": round(v["income"], 2)}
        for m, v in sorted(by_month.items())
    ]

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "label": label},
        "total_credits": round(credits, 2),
        "total_debits": round(debits, 2),
        "net_cashflow": round(credits - debits, 2),
        "confirmed_income": round(confirmed_income, 2),
        "by_month": months,
    }


def income_summary(session: Session, period: dict | None = None, today: date | None = None) -> dict:
    """Income for the period, by income category. Prefers confirmed income; if
    none is confirmed in the period, falls back to income candidates and flags
    the basis so the model can caveat the answer."""
    start, end, label = resolve_period(period, today)
    credits = [
        t for t in load_ledger(session)
        if _in_range(t, start, end) and t["type"] == TransactionType.credit
    ]

    confirmed = [t for t in credits if t["income_confirmed"] is True]
    if confirmed:
        basis, income_txns = "confirmed", confirmed
    else:
        basis = "candidate_included"
        income_txns = [t for t in credits if t["is_income_candidate"] and t["income_confirmed"] is None]

    by_cat: dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "count": 0})
    for t in income_txns:
        c = by_cat[t["income_category"]]
        c["amount"] += t["amount"]
        c["count"] += 1

    categories = [
        {"category": k, "amount": round(v["amount"], 2), "count": v["count"]}
        for k, v in sorted(by_cat.items(), key=lambda kv: kv[1]["amount"], reverse=True)
    ]

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "label": label},
        "basis": basis,
        "total_income": round(sum(t["amount"] for t in income_txns), 2),
        "by_category": categories,
    }
```

- [ ] **Step 4: Run to verify pass**

```powershell
pytest tests/test_analytics.py -k "cashflow_summary or income_summary" -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/analytics.py backend/tests/test_analytics.py
git commit -m "$(cat <<'EOF'
Add cashflow_summary and income_summary analytic tools

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `compare_periods` and `recurring_charges` tools

**Files:**
- Modify: `backend/app/services/analytics.py` (append)
- Test: `backend/tests/test_analytics.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_analytics.py`:

```python
def test_compare_periods_delta_and_pct(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-04-10", amount=100.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink")
    make_txn(day="2026-05-10", amount=150.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink")

    out = analytics.compare_periods(
        s, {"month": "2026-04"}, {"month": "2026-05"}, today=TODAY)
    assert out["period_a"]["total"] == 100.0
    assert out["period_b"]["total"] == 150.0
    assert out["delta"] == 50.0
    assert out["pct_change"] == 50.0


def test_recurring_charges_detects_monthly_merchant(make_txn):
    s = make_txn.__self_session__
    for day in ("2026-03-15", "2026-04-15", "2026-05-15"):
        make_txn(day=day, amount=15.99, txn_type=TransactionType.debit,
                 description="NETFLIX SUBSCRIPTION", expense_category="subscriptions",
                 expense_subcategory="streaming")
    # A one-off should not be flagged.
    make_txn(day="2026-05-02", amount=200.0, txn_type=TransactionType.debit,
             description="RANDOM SHOP", expense_category="shopping")

    out = analytics.recurring_charges(s, today=TODAY)
    merchants = {r["merchant"]: r for r in out["recurring"]}
    assert "NETFLIX SUBSCRIPTION" in merchants
    netflix = merchants["NETFLIX SUBSCRIPTION"]
    assert netflix["occurrences"] == 3
    assert netflix["typical_amount"] == 15.99
    assert netflix["cadence"] == "monthly"
    assert "RANDOM SHOP" not in merchants
```

- [ ] **Step 2: Run to verify failure**

```powershell
pytest tests/test_analytics.py -k "compare_periods or recurring_charges" -v
```
Expected: FAIL — attributes missing.

- [ ] **Step 3: Implement both tools**

Append to `backend/app/services/analytics.py`:

```python
def _spending_total(session: Session, period: dict | None, primary: str | None, today: date | None):
    start, end, label = resolve_period(period, today)
    txns = [t for t in load_ledger(session) if _in_range(t, start, end) and is_spending_txn(t)]
    if primary:
        txns = [t for t in txns if t["expense_category"] == primary]
    return round(sum(t["amount"] for t in txns), 2), {"start": start.isoformat(), "end": end.isoformat(), "label": label}


def compare_periods(
    session: Session,
    period_a: dict | None,
    period_b: dict | None,
    primary: str | None = None,
    today: date | None = None,
) -> dict:
    """Compare spending between two periods. delta and pct_change are period_b
    relative to period_a (positive = increase)."""
    a_total, a_meta = _spending_total(session, period_a, primary, today)
    b_total, b_meta = _spending_total(session, period_b, primary, today)
    delta = round(b_total - a_total, 2)
    pct = round((delta / a_total * 100), 2) if a_total else None
    return {
        "category": primary or "all",
        "period_a": {**a_meta, "total": a_total},
        "period_b": {**b_meta, "total": b_total},
        "delta": delta,
        "pct_change": pct,
    }


def detect_recurring(txns: list[dict]) -> list[dict]:
    """Group debits by normalized merchant; flag those charged >=3 times at a
    roughly monthly cadence with stable amounts."""
    by_merchant: dict[str, list[dict]] = defaultdict(list)
    for t in txns:
        if t["type"] != TransactionType.debit or is_transfer(t["description"]):
            continue
        key = _norm(t["description"])
        if key:
            by_merchant[key].append(t)

    results = []
    for merchant, items in by_merchant.items():
        if len(items) < 3:
            continue
        items = sorted(items, key=lambda x: x["date"])
        amounts = [i["amount"] for i in items]
        median = sorted(amounts)[len(amounts) // 2]
        if median <= 0:
            continue
        # amounts must be stable (within 25% of median)
        if any(abs(a - median) > 0.25 * median for a in amounts):
            continue
        gaps = [(items[i]["date"] - items[i - 1]["date"]).days for i in range(1, len(items))]
        avg_gap = sum(gaps) / len(gaps)
        if not (20 <= avg_gap <= 40):  # roughly monthly
            continue
        cats = [i["expense_category"] for i in items]
        category = max(set(cats), key=cats.count)
        results.append({
            "merchant": merchant,
            "cadence": "monthly" if 26 <= avg_gap <= 35 else f"~{round(avg_gap)}d",
            "typical_amount": round(median, 2),
            "occurrences": len(items),
            "last_seen": items[-1]["date"].isoformat(),
            "category": category,
            "display": primary_display(category),
        })
    results.sort(key=lambda r: r["typical_amount"], reverse=True)
    return results


def recurring_charges(session: Session, primary: str | None = None, today: date | None = None) -> dict:
    """Detected recurring charges across the full ledger (today unused; kept for
    a uniform tool signature)."""
    txns = load_ledger(session)
    recurring = detect_recurring(txns)
    if primary:
        recurring = [r for r in recurring if r["category"] == primary]
    return {"recurring": recurring}
```

- [ ] **Step 4: Run to verify pass**

```powershell
pytest tests/test_analytics.py -k "compare_periods or recurring_charges" -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/analytics.py backend/tests/test_analytics.py
git commit -m "$(cat <<'EOF'
Add compare_periods and recurring_charges analytic tools

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `search_transactions` tool (the single PII door)

This is the only tool returning raw descriptions. It is row-capped (hard cap 100, default 50) so aggregate-first is enforced structurally.

**Files:**
- Modify: `backend/app/services/analytics.py` (append)
- Test: `backend/tests/test_analytics.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_analytics.py`:

```python
def test_search_transactions_filters_and_caps(make_txn):
    s = make_txn.__self_session__
    for i in range(5):
        make_txn(day=f"2026-05-0{i + 1}", amount=10.0 + i, txn_type=TransactionType.debit,
                 description=f"COFFEE SHOP {i}", expense_category="food_and_drink",
                 expense_subcategory="coffee")
    make_txn(day="2026-05-10", amount=500.0, txn_type=TransactionType.debit,
             description="BIG TV", expense_category="shopping")

    # Filter by merchant substring (case-insensitive).
    out = analytics.search_transactions(s, merchant_contains="coffee", today=TODAY)
    assert out["returned"] == 5
    assert all("COFFEE" in t["description"] for t in out["transactions"])

    # Filter by amount.
    out = analytics.search_transactions(s, min_amount=100.0, today=TODAY)
    assert out["returned"] == 1
    assert out["transactions"][0]["description"] == "BIG TV"

    # Cap enforced.
    out = analytics.search_transactions(s, limit=2, today=TODAY)
    assert out["returned"] == 2
    assert out["truncated"] is True
    assert out["limit"] == 2
```

- [ ] **Step 2: Run to verify failure**

```powershell
pytest tests/test_analytics.py -k search_transactions -v
```
Expected: FAIL — attribute missing.

- [ ] **Step 3: Implement the tool**

Append to `backend/app/services/analytics.py`:

```python
_SEARCH_HARD_CAP = 100


def search_transactions(
    session: Session,
    period: dict | None = None,
    primary: str | None = None,
    subcategory: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    merchant_contains: str | None = None,
    txn_type: str | None = None,
    limit: int = 50,
    today: date | None = None,
) -> dict:
    """Return individual line items matching filters. The ONLY tool that exposes
    raw descriptions; results are hard-capped at 100 rows."""
    limit = max(1, min(int(limit), _SEARCH_HARD_CAP))
    txns = load_ledger(session)

    if period:
        start, end, _ = resolve_period(period, today)
        txns = [t for t in txns if _in_range(t, start, end)]
    if primary:
        txns = [t for t in txns if t["expense_category"] == primary]
    if subcategory:
        txns = [t for t in txns if t["expense_subcategory"] == subcategory]
    if min_amount is not None:
        txns = [t for t in txns if t["amount"] >= min_amount]
    if max_amount is not None:
        txns = [t for t in txns if t["amount"] <= max_amount]
    if merchant_contains:
        needle = merchant_contains.lower()
        txns = [t for t in txns if needle in t["description"].lower()]
    if txn_type in ("debit", "credit"):
        txns = [t for t in txns if t["type"].value == txn_type]

    txns.sort(key=lambda t: t["date"], reverse=True)
    truncated = len(txns) > limit
    rows = [
        {"id": t["id"], "date": t["date"].isoformat(), "description": t["description"],
         "amount": round(t["amount"], 2), "type": t["type"].value,
         "category": t["expense_category"], "subcategory": t["expense_subcategory"]}
        for t in txns[:limit]
    ]
    return {"transactions": rows, "returned": len(rows), "truncated": truncated, "limit": limit}
```

- [ ] **Step 4: Run to verify pass**

```powershell
pytest tests/test_analytics.py -k search_transactions -v
```
Expected: passed.

- [ ] **Step 5: Run the whole analytics suite**

```powershell
pytest tests/test_analytics.py -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/analytics.py backend/tests/test_analytics.py
git commit -m "$(cat <<'EOF'
Add search_transactions tool (row-capped, single raw-description door)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Anthropic tool schemas + dispatcher

**Files:**
- Modify: `backend/app/services/analytics.py` (append)
- Test: `backend/tests/test_analytics.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_analytics.py`:

```python
def test_tools_schema_shape():
    names = {t["name"] for t in analytics.TOOLS}
    assert names == {
        "spending_by_category", "cashflow_summary", "income_summary",
        "compare_periods", "recurring_charges", "search_transactions",
    }
    for t in analytics.TOOLS:
        assert "description" in t and "input_schema" in t


def test_dispatch_tool_routes_and_wraps_errors(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-02", amount=100.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink")

    ok = analytics.dispatch_tool(s, "spending_by_category", {"period": {"month": "2026-05"}}, today=TODAY)
    assert ok["total_spending"] == 100.0

    err = analytics.dispatch_tool(s, "spending_by_category", {"period": {"month": "garbage"}}, today=TODAY)
    assert "error" in err

    unknown = analytics.dispatch_tool(s, "no_such_tool", {}, today=TODAY)
    assert "error" in unknown
```

- [ ] **Step 2: Run to verify failure**

```powershell
pytest tests/test_analytics.py -k "tools_schema or dispatch_tool" -v
```
Expected: FAIL — `TOOLS` / `dispatch_tool` missing.

- [ ] **Step 3: Implement schemas and dispatcher**

Append to `backend/app/services/analytics.py`:

```python
# ─── Anthropic tool schemas + dispatcher ──────────────────────────────────────

_PERIOD_SCHEMA = {
    "type": "object",
    "description": "A time period. Use exactly one style.",
    "properties": {
        "preset": {"type": "string", "enum": [
            "this_month", "last_month", "this_quarter", "last_quarter",
            "this_year", "last_year", "last_3_months", "last_6_months",
            "last_12_months", "all_time",
        ]},
        "month": {"type": "string", "description": "YYYY-MM"},
        "quarter": {"type": "string", "description": "YYYY-Qn, e.g. 2026-Q1"},
        "year": {"type": "string", "description": "YYYY"},
        "start": {"type": "string", "description": "YYYY-MM-DD (use with end)"},
        "end": {"type": "string", "description": "YYYY-MM-DD (use with start)"},
    },
}

TOOLS = [
    {
        "name": "spending_by_category",
        "description": "Total spending in a period, broken down by category and subcategory. Excludes transfers, credit-card payments, and investments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": _PERIOD_SCHEMA,
                "primary": {"type": "string", "description": "Optional primary category key to filter to (e.g. food_and_drink)."},
            },
        },
    },
    {
        "name": "cashflow_summary",
        "description": "Money in vs out for a period: total credits, total debits, net, confirmed income, and a per-month breakdown.",
        "input_schema": {"type": "object", "properties": {"period": _PERIOD_SCHEMA}},
    },
    {
        "name": "income_summary",
        "description": "Income for a period broken down by income category (salary, interest, rental, gig, other). Prefers confirmed income.",
        "input_schema": {"type": "object", "properties": {"period": _PERIOD_SCHEMA}},
    },
    {
        "name": "compare_periods",
        "description": "Compare spending between two periods; returns each total plus delta and percent change (period_b relative to period_a).",
        "input_schema": {
            "type": "object",
            "properties": {
                "period_a": _PERIOD_SCHEMA,
                "period_b": _PERIOD_SCHEMA,
                "primary": {"type": "string", "description": "Optional primary category to compare."},
            },
            "required": ["period_a", "period_b"],
        },
    },
    {
        "name": "recurring_charges",
        "description": "Recurring charges detected across the full ledger (roughly monthly, stable amount, 3+ occurrences).",
        "input_schema": {
            "type": "object",
            "properties": {"primary": {"type": "string", "description": "Optional primary category filter."}},
        },
    },
    {
        "name": "search_transactions",
        "description": "List individual transactions matching filters. Use only when line-item detail is needed; results are capped at 100 rows.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": _PERIOD_SCHEMA,
                "primary": {"type": "string"},
                "subcategory": {"type": "string"},
                "min_amount": {"type": "number"},
                "max_amount": {"type": "number"},
                "merchant_contains": {"type": "string"},
                "txn_type": {"type": "string", "enum": ["debit", "credit"]},
                "limit": {"type": "integer", "description": "Max rows (default 50, hard cap 100)."},
            },
        },
    },
]

_DISPATCH = {
    "spending_by_category": lambda s, a, today: spending_by_category(s, a.get("period"), a.get("primary"), today),
    "cashflow_summary": lambda s, a, today: cashflow_summary(s, a.get("period"), today),
    "income_summary": lambda s, a, today: income_summary(s, a.get("period"), today),
    "compare_periods": lambda s, a, today: compare_periods(s, a.get("period_a"), a.get("period_b"), a.get("primary"), today),
    "recurring_charges": lambda s, a, today: recurring_charges(s, a.get("primary"), today),
    "search_transactions": lambda s, a, today: search_transactions(
        s, a.get("period"), a.get("primary"), a.get("subcategory"),
        a.get("min_amount"), a.get("max_amount"), a.get("merchant_contains"),
        a.get("txn_type"), a.get("limit", 50), today),
}


def dispatch_tool(session: Session, name: str, tool_input: dict, today: date | None = None) -> dict:
    """Run a named tool, returning its result dict or {'error': ...} on failure."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(session, tool_input or {}, today)
    except Exception as e:  # surfaced to the model, never crashes the loop
        return {"error": f"{type(e).__name__}: {e}"}
```

- [ ] **Step 4: Run to verify pass**

```powershell
pytest tests/test_analytics.py -k "tools_schema or dispatch_tool" -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/analytics.py backend/tests/test_analytics.py
git commit -m "$(cat <<'EOF'
Add Anthropic tool schemas and dispatcher for analytic tools

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Refactor `insight_engine.py` to share the loader (behavior-preserving)

Make `analytics.py` the single source of truth for ledger loading and transfer detection, without changing any insight behavior. A smoke test guards the refactor (insight_engine currently has no tests).

**Files:**
- Modify: `backend/app/services/insight_engine.py:14-23,50-52,126-150`
- Test: `backend/tests/test_insight_smoke.py`

- [ ] **Step 1: Write a smoke test that exercises the current engine**

Create `backend/tests/test_insight_smoke.py`:

```python
from app.models.transaction import TransactionType
from app.services.insight_engine import generate_insights


def test_generate_insights_runs_on_seeded_ledger(make_txn):
    s = make_txn.__self_session__
    # Two months of spending so detectors have something to chew on.
    for day, amt in (("2026-04-05", 100.0), ("2026-04-20", 120.0),
                     ("2026-05-05", 300.0), ("2026-05-20", 350.0)):
        make_txn(day=day, amount=amt, txn_type=TransactionType.debit,
                 description="SAFEWAY GROCERY", expense_category="food_and_drink")
    make_txn(day="2026-05-01", amount=3000.0, txn_type=TransactionType.credit,
             description="ACME PAYROLL", is_income_candidate=True, income_confirmed=True,
             income_category="salary")

    insights = generate_insights(s, "job1")
    assert isinstance(insights, list)  # runs without error and returns rows
```

- [ ] **Step 2: Run it against the CURRENT engine to confirm it passes first**

```powershell
pytest tests/test_insight_smoke.py -v
```
Expected: PASS (this captures current behavior before refactor).

- [ ] **Step 3: Replace the transfer regex import in insight_engine**

In `backend/app/services/insight_engine.py`, replace the existing import line (currently line 14):

```python
from ..services.expense_categorizer import CATEGORY_DISPLAY
```

with:

```python
from ..services.expense_categorizer import CATEGORY_DISPLAY
from ..services.analytics import load_ledger, is_transfer as _is_transfer
```

- [ ] **Step 4: Delete the now-duplicated definitions**

In `backend/app/services/insight_engine.py`, delete the local `_TRANSFER_RE` block (the `_TRANSFER_RE = re.compile(...)` assignment near the top) and the `def _is_transfer(desc): return bool(_TRANSFER_RE.search(desc))` function. Then delete the entire `def _load_txns(session)` function (the body that selects, decrypts, and builds dicts).

Immediately after the imports, add a back-compat alias so existing call sites keep working:

```python
_load_txns = load_ledger
```

- [ ] **Step 5: Run the smoke test plus the analytics suite**

```powershell
pytest tests/test_insight_smoke.py tests/test_analytics.py -v
```
Expected: all green — behavior preserved, no duplicate loaders.

- [ ] **Step 6: Run the existing income classification regression suite (per CLAUDE.md)**

```powershell
pytest tests/test_income_classification.py -v --tb=short
```
Expected: same pass/skip result as before this change (PDFs may skip if absent — that is fine).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/insight_engine.py backend/tests/test_insight_smoke.py
git commit -m "$(cat <<'EOF'
Share ledger loader and transfer detection via analytics module

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: `chat_service.py` — the tool-calling loop and grounding contract

The loop is tested with a fake Anthropic client (no network), injected via the `client` parameter.

**Files:**
- Create: `backend/app/services/chat_service.py`
- Test: `backend/tests/test_chat_service.py`

- [ ] **Step 1: Write the failing tests with a fake client**

Create `backend/tests/test_chat_service.py`:

```python
from datetime import date
from types import SimpleNamespace

from app.models.transaction import TransactionType
from app.services import chat_service

TODAY = date(2026, 6, 6)


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_block(tid, name, tool_input):
    return SimpleNamespace(type="tool_use", id=tid, name=name, input=tool_input)


class FakeClient:
    """Scripts a sequence of responses. Each .create() pops the next one."""
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def test_loop_runs_tool_then_returns_grounded_answer(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-02", amount=100.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink")

    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[
            _tool_block("t1", "spending_by_category", {"period": {"month": "2026-05"}})]),
        SimpleNamespace(stop_reason="end_turn", content=[
            _text_block("In May 2026 you spent $100.00 on food.")]),
    ]
    client = FakeClient(responses)

    out = chat_service.answer_question(
        s, "How much did I spend in May?", [], client=client, model="m", today=TODAY)

    assert "100" in out["answer"]
    assert out["tools_used"] == [{"name": "spending_by_category", "input": {"period": {"month": "2026-05"}}}]
    # Second call must include the tool_result the loop fed back.
    second_msgs = client.calls[1]["messages"]
    assert any(
        isinstance(m["content"], list) and m["content"][0].get("type") == "tool_result"
        for m in second_msgs
    )


def test_loop_respects_iteration_cap(make_txn):
    s = make_txn.__self_session__
    # Always asks for a tool -> never terminates on its own.
    always_tool = SimpleNamespace(stop_reason="tool_use", content=[
        _tool_block("t", "recurring_charges", {})])
    client = FakeClient([always_tool] * 10)

    out = chat_service.answer_question(
        s, "loop forever?", [], client=client, model="m", today=TODAY, max_iterations=3)

    assert len(client.calls) == 3  # capped
    assert out["answer"]  # returns a graceful message, not an exception
```

- [ ] **Step 2: Run to verify failure**

```powershell
pytest tests/test_chat_service.py -v
```
Expected: FAIL — module/function missing.

- [ ] **Step 3: Implement the service**

Create `backend/app/services/chat_service.py`:

```python
"""Conversational layer: a bounded Claude tool-use loop over the analytics tools.

The model never states a financial figure it didn't get from a tool. All tools
are aggregate-first; search_transactions is the only one returning raw
descriptions and it is row-capped. The Anthropic client is injectable for tests.
"""
import json
from datetime import date

from sqlmodel import Session

from ..config import get_settings
from .analytics import TOOLS, dispatch_tool

SYSTEM_PROMPT = """You are the analyst inside a personal finance app. You answer \
questions about the user's imported bank and card transactions.

Rules you must follow:
- State only numbers returned by the tools. Never estimate, guess, or use outside \
knowledge to fill gaps. If you didn't get a number from a tool, you don't have it.
- Always anchor an answer to its period and scope, e.g. "In Q1 2026, across all \
imported accounts...".
- "Spending" excludes money movement (transfers, credit-card payments, \
investments). Use spending_by_category for spending questions and cashflow_summary \
for money-in-vs-out questions.
- If the tools cannot answer, say so plainly and suggest what the user could import \
or confirm. Do not invent an answer.
- When a figure depends on auto-categorization or unconfirmed income, add a brief \
caveat (e.g. "based on auto-categorization").
- Give descriptive analysis only. Do not give financial, tax, or legal advice.
Be concise and use plain dollar figures."""

_MAX_TOKENS = 1024


def _build_client():
    import anthropic
    key = get_settings().anthropic_api_key
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment")
    return anthropic.Anthropic(api_key=key)


def answer_question(
    session: Session,
    question: str,
    history: list[dict] | None = None,
    *,
    client=None,
    model: str | None = None,
    today: date | None = None,
    max_iterations: int = 5,
) -> dict:
    """Run the tool-use loop and return {'answer', 'tools_used'}.

    `history` is a list of {'role','content'} dicts with string content.
    `client` and `model` are injectable; default to the configured Anthropic client.
    """
    client = client or _build_client()
    model = model or get_settings().chat_model

    messages = list(history or []) + [{"role": "user", "content": question}]
    tools_used: list[dict] = []
    last_text = ""

    for _ in range(max_iterations):
        resp = client.messages.create(
            model=model,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        assistant_content = []
        tool_uses = []
        text_parts = []
        for block in resp.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
                text_parts.append(block.text)
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use", "id": block.id,
                    "name": block.name, "input": block.input,
                })
                tool_uses.append(block)

        messages.append({"role": "assistant", "content": assistant_content})
        if text_parts:
            last_text = "\n".join(text_parts).strip()

        if resp.stop_reason != "tool_use":
            return {"answer": last_text, "tools_used": tools_used}

        tool_results = []
        for tu in tool_uses:
            tools_used.append({"name": tu.name, "input": tu.input})
            result = dispatch_tool(session, tu.name, tu.input, today=today)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result, default=str),
            })
        messages.append({"role": "user", "content": tool_results})

    # Iteration cap reached.
    fallback = "I couldn't fully resolve that with the available data tools."
    return {"answer": (last_text + "\n\n" + fallback).strip() if last_text else fallback,
            "tools_used": tools_used}
```

- [ ] **Step 4: Run to verify pass**

```powershell
pytest tests/test_chat_service.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/chat_service.py backend/tests/test_chat_service.py
git commit -m "$(cat <<'EOF'
Add chat_service tool-use loop with grounding contract and iteration cap

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: `routers/chat.py` — POST /api/chat, wired into the app

**Files:**
- Create: `backend/app/routers/chat.py`
- Modify: `backend/app/main.py:6-7,74-76`
- Test: `backend/tests/test_chat_router.py`

- [ ] **Step 1: Write the failing endpoint test (service stubbed)**

Create `backend/tests/test_chat_router.py`:

```python
from fastapi.testclient import TestClient

import app.routers.chat as chat_router
from app.main import app
from app.database import get_session


def _override_session(session):
    def _dep():
        yield session
    return _dep


def test_chat_endpoint_returns_answer(session, monkeypatch):
    def fake_answer(sess, question, history, **kwargs):
        return {"answer": f"echo: {question}", "tools_used": [{"name": "cashflow_summary", "input": {}}]}

    monkeypatch.setattr(chat_router, "answer_question", fake_answer)
    app.dependency_overrides[get_session] = _override_session(session)
    try:
        client = TestClient(app)
        res = client.post("/api/chat", json={"question": "hi", "history": []})
        assert res.status_code == 200
        body = res.json()
        assert body["answer"] == "echo: hi"
        assert body["tools_used"][0]["name"] == "cashflow_summary"
    finally:
        app.dependency_overrides.clear()


def test_chat_endpoint_503_when_key_missing(session, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment")

    monkeypatch.setattr(chat_router, "answer_question", boom)
    app.dependency_overrides[get_session] = _override_session(session)
    try:
        client = TestClient(app)
        res = client.post("/api/chat", json={"question": "hi", "history": []})
        assert res.status_code == 503
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run to verify failure**

```powershell
pytest tests/test_chat_router.py -v
```
Expected: FAIL — `/api/chat` 404 / import error.

- [ ] **Step 3: Implement the router**

Create `backend/app/routers/chat.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from ..database import get_session
from ..services.chat_service import answer_question

router = APIRouter(prefix="/api", tags=["chat"])


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessageIn] = []


@router.post("/chat")
def chat(req: ChatRequest, session: Session = Depends(get_session)):
    history = [{"role": m.role, "content": m.content} for m in req.history]
    try:
        return answer_question(session, req.question, history)
    except RuntimeError as e:  # config problem (e.g. missing API key)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:  # upstream/model failure
        raise HTTPException(status_code=502, detail=f"Chat failed: {e}")
```

- [ ] **Step 4: Wire it into the app**

In `backend/app/main.py`, add the import alongside the others (after line 7):

```python
from .routers import chat
```

and register it after the insights router (after line 76):

```python
app.include_router(chat.router)
```

- [ ] **Step 5: Run to verify pass**

```powershell
pytest tests/test_chat_router.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/chat.py backend/app/main.py backend/tests/test_chat_router.py
git commit -m "$(cat <<'EOF'
Add POST /api/chat endpoint wired to chat_service

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Q&A grounding eval (real API, skips without key)

Mirrors the income-classification regression discipline: real-loop assertions that the model picks sane tools and states the correct number. Skips cleanly when `ANTHROPIC_API_KEY` is absent so CI without a key stays green.

**Files:**
- Create: `backend/tests/test_qa_eval.py`

- [ ] **Step 1: Write the eval**

Create `backend/tests/test_qa_eval.py`:

```python
"""Grounding eval for the chat substrate. Runs the REAL tool-use loop against a
fixed fixture ledger and asserts the model uses the right tool and states the
correct number. Skips if ANTHROPIC_API_KEY is not set.

Run from backend/:
    pytest tests/test_qa_eval.py -v
"""
import os
from datetime import date

import pytest

from app.config import get_settings
from app.models.transaction import TransactionType
from app.services.chat_service import answer_question

TODAY = date(2026, 6, 6)

pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY") and not get_settings().anthropic_api_key,
    reason="ANTHROPIC_API_KEY not set; skipping live grounding eval",
)


@pytest.fixture
def seeded(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-02", amount=100.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink", expense_subcategory="groceries")
    make_txn(day="2026-05-10", amount=40.0, txn_type=TransactionType.debit,
             description="CHIPOTLE", expense_category="food_and_drink", expense_subcategory="restaurant")
    make_txn(day="2026-05-01", amount=3000.0, txn_type=TransactionType.credit,
             description="ACME PAYROLL", is_income_candidate=True, income_confirmed=True,
             income_category="salary")
    return s


def test_spending_question_is_grounded(seeded):
    out = answer_question(seeded, "How much did I spend on food in May 2026?", [], today=TODAY)
    assert any(t["name"] == "spending_by_category" for t in out["tools_used"])
    assert "140" in out["answer"]


def test_income_question_is_grounded(seeded):
    out = answer_question(seeded, "What was my income in May 2026?", [], today=TODAY)
    assert any(t["name"] in ("income_summary", "cashflow_summary") for t in out["tools_used"])
    assert "3,000" in out["answer"] or "3000" in out["answer"]
```

- [ ] **Step 2: Run it (skips without a key)**

```powershell
pytest tests/test_qa_eval.py -v
```
Expected: SKIPPED if no key; both PASS if `ANTHROPIC_API_KEY` is set in env/.env.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_qa_eval.py
git commit -m "$(cat <<'EOF'
Add live Q&A grounding eval (skips without ANTHROPIC_API_KEY)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Frontend types and API client

**Files:**
- Modify: `frontend/lib/types.ts` (append)
- Modify: `frontend/lib/api.ts` (append)

- [ ] **Step 1: Add chat types**

Append to `frontend/lib/types.ts`:

```typescript
export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface ChatToolUse {
  name: string;
  input: Record<string, unknown>;
}

export interface ChatResponse {
  answer: string;
  tools_used: ChatToolUse[];
}
```

- [ ] **Step 2: Add the API call**

Append to `frontend/lib/api.ts`:

```typescript
export async function sendChatMessage(
  question: string,
  history: ChatMessage[]
): Promise<ChatResponse> {
  const res = await fetch(`${API}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  });
  return handleResponse<ChatResponse>(res);
}
```

- [ ] **Step 3: Add the imports to api.ts**

In `frontend/lib/api.ts`, extend the existing top-of-file type import to include the chat types:

```typescript
import type { ChatMessage, ChatResponse, FileResult, ImportSummary, InsightFeedResponse, Transaction, UploadResult } from "./types";
```

- [ ] **Step 4: Verify the frontend type-checks**

Run (from `frontend/`):
```powershell
npm run build
```
Expected: build succeeds (no TypeScript errors).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "$(cat <<'EOF'
Add chat types and sendChatMessage API client

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Chat UI — `ChatInterface` component and page

**Files:**
- Create: `frontend/components/ChatInterface.tsx`
- Create: `frontend/app/chat/page.tsx`

- [ ] **Step 1: Build the chat component**

Create `frontend/components/ChatInterface.tsx`:

```typescript
"use client";

import { useState } from "react";
import { sendChatMessage } from "@/lib/api";
import type { ChatMessage, ChatToolUse } from "@/lib/types";

interface DisplayMessage extends ChatMessage {
  tools?: ChatToolUse[];
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    const question = input.trim();
    if (!question || loading) return;
    setError(null);
    setInput("");

    const history: ChatMessage[] = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);
    try {
      const res = await sendChatMessage(question, history);
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer, tools: res.tools_used }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[70vh]">
      <div className="flex-1 overflow-y-auto space-y-4 p-2">
        {messages.length === 0 && (
          <p className="text-gray-400 text-sm text-center mt-8">
            Ask about your finances — e.g. &ldquo;How much did I spend on dining last quarter?&rdquo;
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div
              className={`inline-block rounded-lg px-3 py-2 max-w-[85%] whitespace-pre-wrap text-sm ${
                m.role === "user" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-800"
              }`}
            >
              {m.content}
            </div>
            {m.tools && m.tools.length > 0 && (
              <div className="text-[11px] text-gray-400 mt-1">
                based on: {m.tools.map((t) => t.name).join(", ")}
              </div>
            )}
          </div>
        ))}
        {loading && <div className="text-gray-400 text-sm">Thinking…</div>}
      </div>

      {error && <div className="text-red-600 text-sm px-2 py-1">{error}</div>}

      <div className="flex gap-2 border-t pt-3">
        <input
          className="flex-1 border rounded-lg px-3 py-2 text-sm"
          placeholder="Ask a question about your money…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={loading}
        />
        <button
          className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm disabled:opacity-50"
          onClick={send}
          disabled={loading || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build the page**

Create `frontend/app/chat/page.tsx`:

```typescript
import ChatInterface from "@/components/ChatInterface";

export default function ChatPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-10">
        <h1 className="text-xl font-semibold mb-4">Ask your money</h1>
        <ChatInterface />
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Verify build**

Run (from `frontend/`):
```powershell
npm run build
```
Expected: build succeeds.

- [ ] **Step 4: Manual smoke test (requires API key + backend running)**

```powershell
# Terminal A (from backend/, venv active, ANTHROPIC_API_KEY in .env):
uvicorn app.main:app --reload
# Terminal B (from frontend/):
npm run dev
```
Open http://localhost:3000/chat , ask "How much did I spend on food in May 2026?" against imported data, and confirm the answer cites a tool and shows a number consistent with the Transactions page.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ChatInterface.tsx frontend/app/chat/page.tsx
git commit -m "$(cat <<'EOF'
Add conversational chat UI page and component

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Documentation — CLAUDE.md updates

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Document the chat substrate and its test/commit triggers**

In `CLAUDE.md`, under the **Tests** section, add a new subsection after the income-classification suite description:

```markdown
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
```

- [ ] **Step 2: Document the chat env var**

In `CLAUDE.md`, in the **Environment** section, add:

```markdown
The conversational chat feature requires `ANTHROPIC_API_KEY` in `backend/.env`.
The model is configurable via `chat_model` (default `claude-sonnet-4-6`). Without a
key, `/api/chat` returns HTTP 503 and the live grounding eval skips.
```

- [ ] **Step 3: Add the chat architecture note**

In `CLAUDE.md`, under **Architecture → Backend**, add a bullet:

```markdown
- **`services/analytics.py`** — single source of truth for ledger math: `load_ledger`,
  `resolve_period`, and the six aggregate-first tools (`spending_by_category`,
  `cashflow_summary`, `income_summary`, `compare_periods`, `recurring_charges`,
  `search_transactions`) plus their Anthropic tool schemas and `dispatch_tool`.
  `services/chat_service.py` runs a bounded Claude tool-use loop over these tools
  (`POST /api/chat`); the model states only tool-returned numbers. `search_transactions`
  is the only tool exposing raw descriptions and is row-capped at 100.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
Document chat substrate: tests, env, and architecture

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final Verification

- [ ] **Run the full backend suite**

```powershell
pytest tests/test_analytics.py tests/test_chat_service.py tests/test_chat_router.py tests/test_insight_smoke.py -v
pytest tests/test_income_classification.py -v --tb=short   # regression guard (PDFs may skip)
```
Expected: all non-skipped tests pass.

- [ ] **Build the frontend**

```powershell
# from frontend/
npm run build
```
Expected: success.

- [ ] **End-to-end smoke (with key + data)** — confirm a real question returns a number matching the Transactions/Summary pages, and the answer shows a "based on:" tool line.
