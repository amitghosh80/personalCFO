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
