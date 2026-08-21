"""Aggregate-first analytic queries over the whole transaction ledger.

This module is the single source of truth for the math behind both the
rule-based insight engine and the conversational chat tools. Every public
function is deterministic: given the same ledger and parameters, it returns the
same numbers. The chat layer never computes financial figures itself.
"""
import re
from calendar import monthrange, month_name, month_abbr
from collections import defaultdict
from datetime import date, timedelta

from sqlmodel import Session, select

from ..models.transaction import Transaction, TransactionType
from ..services.encryption import decrypt
from ..services.expense_categorizer import (
    is_spending,
    primary_display,
    subcategory_display,
)
from ..services.income_classifier import INCOME_DISPLAY

# ─── Transfer detection (moved from insight_engine for shared use) ────────────

_TRANSFER_RE = re.compile(
    r"transfer|zelle|wire|"
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

def load_ledger(session: Session, user_id: int) -> list[dict]:
    """Decrypt and normalize every non-duplicate, non-ambiguous transaction
    belonging to the given user."""
    rows = session.exec(
        select(Transaction)
        .where(Transaction.user_id == user_id)
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


def monthly_summary(session: Session, user_id: int) -> dict:
    """Whole-ledger dashboard: spending by category, per month, across every
    import. Uses the same load_ledger + is_spending_txn math as the chat tools,
    so the "View import" dashboard and the chatbot never disagree. Shape mirrors
    the per-job import summary's monthly_breakdown."""
    ledger = load_ledger(session, user_id)
    buckets: dict[str, dict] = defaultdict(lambda: {"income": 0.0, "expenses": 0.0})
    cat_buckets: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    income_cat_buckets: dict[str, dict[str, dict]] = defaultdict(
        lambda: defaultdict(lambda: {"amount": 0.0, "count": 0})
    )
    has_unreviewed = False

    for t in ledger:
        month = t["month"]
        if t["type"] == TransactionType.debit:
            if not is_spending_txn(t):
                continue
            buckets[month]["expenses"] += t["amount"]
            cat_buckets[month][t["expense_category"]] += t["amount"]
        else:  # credit
            is_income = t["income_confirmed"] is True or (
                t["is_income_candidate"] and t["income_confirmed"] is None
            )
            if not is_income:
                continue
            buckets[month]["income"] += t["amount"]
            if t["income_confirmed"] is None:
                has_unreviewed = True
            income_cat_buckets[month][t["income_category"]]["amount"] += t["amount"]
            income_cat_buckets[month][t["income_category"]]["count"] += 1

    def _top(month: str) -> list[dict]:
        # Ranked descending, not truncated — the frontend decides how many to show.
        ranked = sorted(cat_buckets[month].items(), key=lambda kv: kv[1], reverse=True)
        return [
            {"category": c, "display": primary_display(c), "amount": round(a, 2)}
            for c, a in ranked
        ]

    def _top_income(month: str) -> list[dict]:
        ranked = sorted(income_cat_buckets[month].items(), key=lambda kv: kv[1]["amount"], reverse=True)
        return [
            {
                "category": c,
                "display": INCOME_DISPLAY.get(c, c.title()),
                "amount": round(v["amount"], 2),
                "count": v["count"],
            }
            for c, v in ranked
        ]

    monthly = [
        {
            "month": m,
            "income": round(d["income"], 2),
            "expenses": round(d["expenses"], 2),
            "net": round(d["income"] - d["expenses"], 2),
            "top_categories": _top(m),
            "income_by_category": _top_income(m),
        }
        for m, d in sorted(buckets.items())
    ]
    dates = [t["date"] for t in ledger]
    return {
        "total_transactions": len(ledger),
        "monthly_breakdown": monthly,
        "income_includes_unreviewed": has_unreviewed,
        "date_range": {
            "from": str(min(dates)) if dates else None,
            "to": str(max(dates)) if dates else None,
        },
    }


# Uncategorized-data thresholds — mirror app/routers/categories.py; keep in sync.
_UNCAT_COUNT_THRESHOLD = 0.10   # >10% of spending transactions
_UNCAT_SPEND_THRESHOLD = 0.15   # >15% of spend dollars


def uncategorized_status(session: Session, user_id: int) -> dict:
    """How much spending is still uncategorized and whether it exceeds the alert
    thresholds. Gates the chatbot from surfacing spending insights on data that is
    too incompletely categorized to trust (PRD F3 / AMI-33)."""
    rows = session.exec(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.transaction_type == TransactionType.debit)
        .where(Transaction.is_duplicate == False)  # noqa: E712
    ).all()
    debits = [t for t in rows if is_spending(t.expense_category or "other")]
    total_count = len(debits)
    total_spend = sum(t.amount for t in debits)

    def _uncat(t) -> bool:
        return (t.expense_category in (None, "other")) or (t.confidence_label == "low")

    unc = [t for t in debits if _uncat(t)]
    pct_count = (len(unc) / total_count) if total_count else 0.0
    pct_spend = (sum(t.amount for t in unc) / total_spend) if total_spend else 0.0
    return {
        "over": pct_count > _UNCAT_COUNT_THRESHOLD or pct_spend > _UNCAT_SPEND_THRESHOLD,
        "pct_count": pct_count,
        "pct_spend": pct_spend,
        "unc_count": len(unc),
        "unc_spend": round(sum(t.amount for t in unc), 2),
        "total_count": total_count,
    }


# ─── Period resolution ─────────────────────────────────────────────────────────

def _month_start(y: int, m: int) -> date:
    return date(y, m, 1)


def _month_end(y: int, m: int) -> date:
    return date(y, m, monthrange(y, m)[1])


def _add_months(y: int, m: int, delta: int) -> tuple[int, int]:
    idx = y * 12 + (m - 1) + delta
    return idx // 12, idx % 12 + 1


_MONTHS: dict[str, int] = {}
for _i in range(1, 13):
    _MONTHS[month_name[_i].lower()] = _i
    _MONTHS[month_abbr[_i].lower()] = _i


def _month_phrase_to_ym(text: str, today: date) -> tuple[int, int] | None:
    """Map 'march' / 'march 2025' to (year, month). A bare month name resolves to
    its most recent past occurrence (future months roll back a year)."""
    parts = text.strip().split()
    if not parts or parts[0] not in _MONTHS:
        return None
    m = _MONTHS[parts[0]]
    if len(parts) >= 2 and re.fullmatch(r"20\d{2}", parts[1]):
        return int(parts[1]), m
    y = today.year if m <= today.month else today.year - 1
    return y, m


def _parse_nl_period(text: str, today: date) -> dict:
    """Map a free-form natural-language period to a structured period dict that
    resolve_period understands. Raises ValueError on an unrecognized phrase."""
    t = " ".join(text.strip().lower().split())

    presets = {
        "all time": "all_time", "all-time": "all_time", "everything": "all_time",
        "this month": "this_month", "last month": "last_month",
        "this quarter": "this_quarter", "last quarter": "last_quarter",
        "this year": "this_year", "year to date": "this_year", "ytd": "this_year",
        "last year": "last_year",
        "last 3 months": "last_3_months", "last 6 months": "last_6_months",
        "last 12 months": "last_12_months",
    }
    if t in presets:
        return {"preset": presets[t]}

    if t == "today":
        return {"start": today.isoformat(), "end": today.isoformat()}
    if t == "yesterday":
        d = today - timedelta(days=1)
        return {"start": d.isoformat(), "end": d.isoformat()}
    if t in ("last week", "past week", "this week"):
        return {"start": (today - timedelta(days=6)).isoformat(), "end": today.isoformat()}

    m = re.fullmatch(r"last (\d{1,2}) months?", t)
    if m:
        y, mo = _add_months(today.year, today.month, -(int(m.group(1)) - 1))
        return {"start": _month_start(y, mo).isoformat(), "end": today.isoformat()}
    m = re.fullmatch(r"last (\d{1,3}) days?", t)
    if m:
        return {"start": (today - timedelta(days=int(m.group(1)) - 1)).isoformat(),
                "end": today.isoformat()}

    m = re.search(r"\bq([1-4])\b", t)
    if m:
        ym = re.search(r"\b(20\d{2})\b", t)
        y = int(ym.group(1)) if ym else today.year
        return {"quarter": f"{y}-Q{m.group(1)}"}

    if t.startswith("since "):
        rest = t[len("since "):].strip()
        ym = _month_phrase_to_ym(rest, today)
        if ym:
            return {"start": _month_start(*ym).isoformat(), "end": today.isoformat()}
        try:
            return {"start": date.fromisoformat(rest).isoformat(), "end": today.isoformat()}
        except ValueError:
            pass

    if re.fullmatch(r"20\d{2}", t):
        return {"year": t}
    if re.fullmatch(r"20\d{2}-\d{2}", t):
        return {"month": t}

    ym = _month_phrase_to_ym(t, today)
    if ym:
        return {"month": f"{ym[0]:04d}-{ym[1]:02d}"}

    raise ValueError(f"Unrecognized period phrase: {text!r}")


def resolve_period(period: "dict | str | None", today: date | None = None) -> tuple[date, date, str]:
    """Resolve a period spec to (start, end, human_label). All date math lives
    here so the model never computes dates. `today` is injectable for tests.

    Accepts a structured dict (preset/month/quarter/year/start-end), a free-form
    natural-language string ('last week', 'January', 'since March'), or a dict
    carrying a `text` field with such a string."""
    today = today or date.today()

    if isinstance(period, str):
        return resolve_period(_parse_nl_period(period, today), today)

    period = period or {}

    if period.get("text") and not any(
        period.get(k) for k in ("preset", "month", "quarter", "year", "start", "end")
    ):
        return resolve_period(_parse_nl_period(period["text"], today), today)

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


def spending_by_category(
    session: Session,
    user_id: int,
    period: dict | None = None,
    primary: str | None = None,
    today: date | None = None,
) -> dict:
    """Total spending broken down by primary category and subcategory.

    Excludes money movement (transfers, credit-card payments, investments) so
    'how much did I spend' is never inflated by offsetting transactions.
    """
    start, end, label = resolve_period(period, today)
    txns = [t for t in load_ledger(session, user_id) if _in_range(t, start, end) and is_spending_txn(t)]
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


def cashflow_summary(session: Session, user_id: int, period: dict | None = None, today: date | None = None) -> dict:
    """Money in vs out for the period. Debits here are ALL outflows (not just
    spending), so net reflects actual account movement; use spending_by_category
    for consumption-only totals."""
    start, end, label = resolve_period(period, today)
    txns = [t for t in load_ledger(session, user_id) if _in_range(t, start, end)]

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


def income_summary(session: Session, user_id: int, period: dict | None = None, today: date | None = None) -> dict:
    """Income for the period, by income category. Prefers confirmed income; if
    none is confirmed in the period, falls back to income candidates and flags
    the basis so the model can caveat the answer."""
    start, end, label = resolve_period(period, today)
    credits = [
        t for t in load_ledger(session, user_id)
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


def _spending_total(session: Session, user_id: int, period: dict | None, primary: str | None, today: date | None):
    start, end, label = resolve_period(period, today)
    txns = [t for t in load_ledger(session, user_id) if _in_range(t, start, end) and is_spending_txn(t)]
    if primary:
        txns = [t for t in txns if t["expense_category"] == primary]
    return round(sum(t["amount"] for t in txns), 2), {"start": start.isoformat(), "end": end.isoformat(), "label": label}


def compare_periods(
    session: Session,
    user_id: int,
    period_a: dict | None,
    period_b: dict | None,
    primary: str | None = None,
    today: date | None = None,
) -> dict:
    """Compare spending between two periods. delta and pct_change are period_b
    relative to period_a (positive = increase)."""
    a_total, a_meta = _spending_total(session, user_id, period_a, primary, today)
    b_total, b_meta = _spending_total(session, user_id, period_b, primary, today)
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


def recurring_charges(session: Session, user_id: int, primary: str | None = None, today: date | None = None) -> dict:
    """Detected recurring charges across the full ledger (today unused; kept for
    a uniform tool signature)."""
    txns = load_ledger(session, user_id)
    recurring = detect_recurring(txns)
    if primary:
        recurring = [r for r in recurring if r["category"] == primary]
    return {"recurring": recurring}


_SEARCH_HARD_CAP = 100


def search_transactions(
    session: Session,
    user_id: int,
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
    txns = load_ledger(session, user_id)

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


# ─── Anthropic tool schemas + dispatcher ──────────────────────────────────────

_PERIOD_SCHEMA = {
    "type": "object",
    "description": "A time period. Use exactly one style. If unsure how to map a "
                   "phrase the user typed, pass it verbatim as `text` (e.g. "
                   "'last week', 'January', 'since March', 'Q1 2026').",
    "properties": {
        "text": {"type": "string", "description": "Free-form natural-language period, resolved server-side."},
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
        "description": "Income for a period broken down by income category (salary, freelance, interest, rental, gig, other). Prefers confirmed income.",
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
    "spending_by_category": lambda s, uid, a, today: spending_by_category(s, uid, a.get("period"), a.get("primary"), today),
    "cashflow_summary": lambda s, uid, a, today: cashflow_summary(s, uid, a.get("period"), today),
    "income_summary": lambda s, uid, a, today: income_summary(s, uid, a.get("period"), today),
    "compare_periods": lambda s, uid, a, today: compare_periods(s, uid, a.get("period_a"), a.get("period_b"), a.get("primary"), today),
    "recurring_charges": lambda s, uid, a, today: recurring_charges(s, uid, a.get("primary"), today),
    "search_transactions": lambda s, uid, a, today: search_transactions(
        s, uid, a.get("period"), a.get("primary"), a.get("subcategory"),
        a.get("min_amount"), a.get("max_amount"), a.get("merchant_contains"),
        a.get("txn_type"), a.get("limit", 50), today),
}


def data_coverage(session: Session, user_id: int) -> dict:
    """Date range + distinct accounts the ledger covers, for the chat scope
    footer ("Based on your Jan–May 2026 data from N accounts")."""
    rows = session.exec(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.is_duplicate == False)   # noqa: E712
        .where(Transaction.is_ambiguous == False)    # noqa: E712
    ).all()
    if not rows:
        return {"date_range": None, "account_count": 0, "institutions": [], "transaction_count": 0}
    dates = [r.date for r in rows]
    institutions = sorted({r.institution for r in rows if r.institution})
    return {
        "date_range": {"from": str(min(dates)), "to": str(max(dates))},
        "account_count": len(institutions) or 1,
        "institutions": institutions,
        "transaction_count": len(rows),
    }


def starter_questions(session: Session, user_id: int) -> list[str]:
    """4–6 suggested questions, contextual to what the user actually imported."""
    txns = load_ledger(session, user_id)
    questions = [
        "What did I spend the most on last month?",
        "How much did I spend on dining last month?",
        "What subscriptions am I paying for?",
        "Did I save money last month?",
    ]
    income_cats = {
        t["income_category"] for t in txns
        if t["type"] == TransactionType.credit and (t["is_income_candidate"] or t["income_confirmed"])
    }
    if "freelance" in income_cats:
        questions.append("How much freelance income did I earn this year?")
    if "gig" in income_cats:
        questions.append("How much did I earn from gig work this year?")
    return questions[:6]


def dispatch_tool(session: Session, user_id: int, name: str, tool_input: dict, today: date | None = None) -> dict:
    """Run a named tool, returning its result dict or {'error': ...} on failure."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(session, user_id, tool_input or {}, today)
    except Exception as e:  # surfaced to the model, never crashes the loop
        return {"error": f"{type(e).__name__}: {e}"}
