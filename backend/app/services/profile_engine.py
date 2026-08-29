"""Financial Profile (Flow 5): evergreen metrics recomputed from the full ledger.

Six standing metrics — committed monthly spend, average monthly burn, average
monthly income, fixed vs. discretionary baseline, savings rate, and fees &
interest paid — rendered as the top-of-page module on the View Important page.
These are computed views, not stored events: every call recomputes from
scratch off `load_ledger`. No new tables, no dismiss semantics.
"""
import calendar
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlmodel import Session

from ..models.transaction import TransactionType
from .analytics import load_ledger, is_transfer, _norm as _normalize_merchant
from .expense_categorizer import primary_display

# ─── Pattern lists ─────────────────────────────────────────────────────────────

_FIXED_OBLIGATION = [
    r"\bmortgage\b",
    r"\brent\b",
    r"\blease\s*payment\b",
    r"\b(car|auto)\s*loan\b",
    r"\bloan\s*pay(mt|ment)?\b",
    r"\belectric(ity)?\b",
    r"\bpg&e\b",
    r"\butilit(y|ies)\b",
    r"\bwater\s*(bill|utility|dept|department)\b",
    r"\bsewer\b",
    r"\btrash\s*(collection|service)?\b",
    r"\binternet\b",
    r"\bbroadband\b",
    r"\bcable\s*(tv|bill)?\b",
    r"\bcomcast\b", r"\bxfinity\b", r"\bspectrum\b",
    r"\bat&t\b", r"\bverizon\b", r"\bt-mobile\b", r"\bcox\s*communications\b",
    r"\bphone\s*bill\b",
    r"\binsurance\b", r"\bpremium\b",
    r"\btuition\b",
    r"\bchildcare\b", r"\bday\s*care\b", r"\bdaycare\b",
]

_PENALTY_FEE = [
    r"\boverdraft\b",
    r"\bnsf\b",
    r"non-?sufficient\s*funds",
    r"\blate\s*(fee|payment\s*(fee|charge))\b",
]
_BANK_FEE = [
    r"\bmonthly\s*(service|maintenance)\s*fee\b",
    r"\bmaintenance\s*fee\b",
    r"\bservice\s*fee\b",
    r"\batm\s*fee\b",
    r"\bwire\s*(transfer\s*)?fee\b",
    r"\btransfer\s*fee\b",
]
_CARD_FEE = [
    r"\bannual\s*fee\b",
    r"\bforeign\s*transaction\s*fee\b",
    r"\bcash\s*advance\s*fee\b",
]
_INTEREST_CHARGE = [
    r"\binterest\s*charge(d)?\b",
    r"\bfinance\s*charge\b",
    r"\bpurchase\s*interest\b",
]

_FEE_SUBTYPES: list[tuple[str, list[str]]] = [
    ("penalty_fees", _PENALTY_FEE),
    ("bank_fees", _BANK_FEE),
    ("card_fees", _CARD_FEE),
    ("interest", _INTEREST_CHARGE),
]

_FEE_INTEREST = [p for _, patterns in _FEE_SUBTYPES for p in patterns]

_FEE_SUBTYPE_DISPLAY = {
    "penalty_fees": "overdraft and late fees",
    "bank_fees": "bank fees",
    "card_fees": "card fees",
    "interest": "credit card interest",
}

# ─── Cadence ───────────────────────────────────────────────────────────────────

_CADENCE_DAYS = {
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "quarterly": 91,
    "annual": 365,
}
_CADENCE_MULTIPLIER = {
    "weekly": 4.33,
    "biweekly": 2.17,
    "monthly": 1.0,
    "quarterly": 1 / 3,
    "annual": 1 / 12,
}


def _classify_cadence(avg_gap_days: float) -> str | None:
    if 5 <= avg_gap_days <= 9:
        return "weekly"
    if 12 <= avg_gap_days <= 17:
        return "biweekly"
    if 26 <= avg_gap_days <= 35:
        return "monthly"
    if 80 <= avg_gap_days <= 100:
        return "quarterly"
    if 350 <= avg_gap_days <= 380:
        return "annual"
    return None


# Cadences anchored to a calendar day (as opposed to weekly/biweekly, which are
# anchored to a day of the week and already constrained by their tight gap window).
_DAY_ANCHORED_CADENCES = {"monthly", "quarterly", "annual"}
_DAY_ANCHOR_TOLERANCE_DAYS = 2


def _days_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def _day_anchor_distance(d1: date, d2: date) -> int:
    """Calendar-day distance between two dates' day-of-month, treating both
    ends of shorter/longer months as the same anchor (e.g. the 31st and the
    28th in February both mean "last day of the month")."""
    day_diff = abs(d1.day - d2.day)
    end_diff = abs((_days_in_month(d1) - d1.day) - (_days_in_month(d2) - d2.day))
    return min(day_diff, end_diff)


# ─── Shared helpers ────────────────────────────────────────────────────────────

def _matches_any(desc: str, patterns: list[str]) -> bool:
    return any(re.search(p, desc, re.IGNORECASE) for p in patterns)


def _fee_subtype(description: str) -> str | None:
    for subtype, patterns in _FEE_SUBTYPES:
        if _matches_any(description, patterns):
            return subtype
    return None


def _conf_label(c: float) -> str:
    if c >= 0.80:
        return "high"
    if c >= 0.55:
        return "medium"
    return "low"


def _ok(confidence: float, headline: str, narrative: str, payload: dict) -> dict:
    confidence = max(0.0, min(confidence, 1.0))
    return {
        "status": "ok",
        "confidence": round(confidence, 2),
        "confidence_label": _conf_label(confidence),
        "headline": headline,
        "narrative": narrative,
        "payload": payload,
    }


def _insufficient(requirement: str) -> dict:
    return {"status": "insufficient_data", "requirement": requirement}


def _complete_months(ledger: list[dict], today: date) -> list[str]:
    """Months strictly before the current (partial) month that have ledger data."""
    current_month = today.strftime("%Y-%m")
    return sorted({t["month"] for t in ledger if t["month"] < current_month})


def _debit_totals_by_month(ledger: list[dict]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for t in ledger:
        if t["type"] == TransactionType.debit and not is_transfer(t["description"]):
            totals[t["month"]] += t["amount"]
    return totals


# ─── Recurring commitment detection (shared by metrics 1 and 4) ───────────────

# Categories where "one charge per cycle" is the norm — bills and obligations.
# Categories like food_and_drink, shopping, or transportation have many
# independent, variably-timed purchases per month; a pair that coincidentally
# matches amount/cadence there is far more likely to be noise than a real
# commitment, so they're excluded rather than left for the cadence/amount
# checks to (unreliably) sort out.
_COMMITMENT_ELIGIBLE_CATEGORIES = frozenset({
    "housing", "utilities", "subscriptions", "insurance", "debt_payments", "credit_card_payment",
})


def detect_commitments(ledger: list[dict], today: date) -> list[dict]:
    """Debits grouped by normalized merchant, classified by cadence (weekly /
    biweekly / monthly / quarterly / annual), with amounts stable within 10% and
    at least 2 occurrences. A commitment is dropped once two consecutive expected
    charges have been missed."""
    by_merchant: dict[str, list[dict]] = defaultdict(list)
    for t in ledger:
        if t["type"] != TransactionType.debit or is_transfer(t["description"]):
            continue
        if t["expense_category"] not in _COMMITMENT_ELIGIBLE_CATEGORIES:
            continue
        key = _normalize_merchant(t["description"])
        if key:
            by_merchant[key].append(t)

    # Judge "missed expected periods" against the most recent date the ledger
    # actually has data for, not the real calendar date. An import that's a
    # few months stale would otherwise make every commitment — including ones
    # still genuinely active — look cancelled.
    ledger_dates = [t["date"] for t in ledger]
    reference_date = min(today, max(ledger_dates)) if ledger_dates else today

    commitments = []
    for merchant, raw_items in by_merchant.items():
        for items in _cluster_amounts(raw_items):
            items = sorted(items, key=lambda x: x["date"])
            if len(items) < 2:
                continue
            amounts = [i["amount"] for i in items]
            median = statistics.median(amounts)
            if median <= 0:
                continue
            amt_var_ratio = max(abs(a - median) for a in amounts) / median
            if amt_var_ratio > 0.10:
                continue

            gaps = [(items[i]["date"] - items[i - 1]["date"]).days for i in range(1, len(items))]
            if not gaps:
                continue
            avg_gap = statistics.mean(gaps)
            cadence = _classify_cadence(avg_gap)
            if cadence is None:
                continue

            # A real subscription/bill lands on (near) the same calendar day every
            # period. Reject clusters whose average gap happens to fall in a cadence
            # window but whose dates don't actually anchor to a consistent day —
            # e.g. two coincidentally similar-priced purchases ~30 days apart.
            if cadence in _DAY_ANCHORED_CADENCES:
                anchor_date = items[0]["date"]
                if any(
                    _day_anchor_distance(anchor_date, i["date"]) > _DAY_ANCHOR_TOLERANCE_DAYS
                    for i in items[1:]
                ):
                    continue

            gap_stdev = statistics.stdev(gaps) if len(gaps) > 1 else 0.0
            cadence_ambiguous = (gap_stdev / avg_gap) >= 0.25 if avg_gap else True

            cadence_days = _CADENCE_DAYS[cadence]
            last_date = items[-1]["date"]
            next_expected = last_date + timedelta(days=cadence_days)
            # Missed two consecutive expected periods without a new occurrence: drop.
            if reference_date > last_date + timedelta(days=2 * cadence_days):
                continue

            conf = 0.40 if len(items) >= 3 else 0.20
            conf += 0.35 if amt_var_ratio < 0.05 else 0.20
            conf += 0.25 if not cadence_ambiguous else 0.0

            cats = [i["expense_category"] or "other" for i in items]
            category = max(set(cats), key=cats.count)

            commitments.append({
                "merchant": merchant.title(),
                "merchant_key": merchant,
                "cadence": cadence,
                "amount_per_period": round(median, 2),
                "monthly_equivalent": round(median * _CADENCE_MULTIPLIER[cadence], 2),
                "next_expected_charge": next_expected.isoformat(),
                "occurrences_detected": len(items),
                "supporting_transaction_ids": [i["id"] for i in items],
                "occurrences": [
                    {
                        "id": i["id"],
                        "date": i["date"].isoformat(),
                        "amount": round(i["amount"], 2),
                        "description": i["description"],
                    }
                    for i in items
                ],
                "confidence": round(min(conf, 1.0), 2),
                "confidence_label": _conf_label(min(conf, 1.0)),
                "cadence_ambiguous": cadence_ambiguous,
                "category": category,
            })

    commitments.sort(key=lambda c: c["monthly_equivalent"], reverse=True)
    return commitments


def _cluster_amounts(items: list[dict], rel_tol: float = 0.10) -> list[list[dict]]:
    """Split one merchant's transactions into clusters of near-identical amounts.

    Some billers (Apple, Google) reuse one generic descriptor for multiple
    distinct subscriptions at different price points. Without this, those
    price points get merged into a single group and rejected outright for
    amount instability, hiding commitments that are individually perfectly
    stable."""
    items_sorted = sorted(items, key=lambda t: t["amount"])
    clusters: list[list[dict]] = [[items_sorted[0]]]
    for t in items_sorted[1:]:
        prev_amount = clusters[-1][-1]["amount"]
        if prev_amount > 0 and abs(t["amount"] - prev_amount) / prev_amount <= rel_tol:
            clusters[-1].append(t)
        else:
            clusters.append([t])
    return clusters


# ─── Metric 1: Committed Monthly Spend ─────────────────────────────────────────

def _committed_monthly_spend(ledger: list[dict], today: date) -> dict:
    months = sorted({t["month"] for t in ledger})
    if len(months) < 2:
        return _insufficient("Import at least 2 complete months of statements to detect recurring commitments.")

    commitments = detect_commitments(ledger, today)
    total = sum(c["monthly_equivalent"] for c in commitments)
    annualized = total * 12

    conf = 0.30 if len(months) >= 3 else 0.0
    conf += 0.30 if commitments and all(c["confidence_label"] == "high" for c in commitments) else 0.0
    conf += 0.20 if len(commitments) >= 3 else 0.0
    conf += 0.20 if not any(c["cadence_ambiguous"] for c in commitments) else 0.0

    headline = f"Committed monthly spend: ${total:,.0f}/month (${annualized:,.0f}/year)"
    count = len(commitments)
    if count:
        smallest, largest = commitments[-1], commitments[0]
        narrative = (
            f"You have {count} active recurring commitment{'s' if count != 1 else ''}, "
            f"from {smallest['merchant']} (${smallest['amount_per_period']:,.2f}) to "
            f"{largest['merchant']} (${largest['amount_per_period']:,.2f})."
        )
        if count >= 3 and total:
            top3_share = sum(c["monthly_equivalent"] for c in commitments[:3]) / total * 100
            narrative += f" The three largest account for {top3_share:.0f}% of the total."
    else:
        narrative = "No recurring commitments detected yet."

    payload_commitments = [
        {k: v for k, v in c.items() if k not in ("merchant_key",)}
        for c in commitments
    ]

    return _ok(conf, headline, narrative, {
        "committed_monthly_total": round(total, 2),
        "committed_annualized_total": round(annualized, 2),
        "commitment_count": count,
        "commitments": payload_commitments,
    })


# ─── Metric 2: Average Monthly Burn ────────────────────────────────────────────

def _average_monthly_burn(ledger: list[dict], today: date) -> dict:
    complete = _complete_months(ledger, today)
    if len(complete) < 1:
        return _insufficient("Import at least 1 complete month of statements.")

    totals = _debit_totals_by_month(ledger)
    window3 = complete[-3:]
    burn_3mo = statistics.mean(totals.get(m, 0.0) for m in window3)

    burn_6mo = None
    if len(complete) >= 6:
        window6 = complete[-6:]
        burn_6mo = statistics.mean(totals.get(m, 0.0) for m in window6)

    current_month = today.strftime("%Y-%m")
    month_to_date = totals.get(current_month, 0.0)

    window_vals = [totals.get(m, 0.0) for m in window3]
    mean_window = statistics.mean(window_vals) if window_vals else 0.0
    variance_ratio = (statistics.stdev(window_vals) / mean_window) if len(window_vals) > 1 and mean_window else 0.0

    conf = 0.35 if len(complete) >= 3 else 0.0
    conf += 0.15 if len(complete) >= 6 else 0.0
    conf += 0.25  # transfers excluded by construction
    conf += 0.25 if variance_ratio < 0.25 else 0.0

    headline = f"Average monthly burn: ${burn_3mo:,.0f}"
    narrative = (
        f"Over the last {len(window3)} complete month{'s' if len(window3) != 1 else ''} "
        f"you've spent an average of ${burn_3mo:,.0f}/month."
    )
    if burn_6mo is not None:
        narrative += f" Your 6-month average is ${burn_6mo:,.0f}."
    narrative += f" {today.strftime('%B')} to date: ${month_to_date:,.0f}."

    return _ok(conf, headline, narrative, {
        "burn_3mo": round(burn_3mo, 2),
        "burn_6mo": round(burn_6mo, 2) if burn_6mo is not None else None,
        "month_to_date": round(month_to_date, 2),
        "months_in_window": len(window3),
        "monthly_series": [{"month": m, "total_debits": round(totals.get(m, 0.0), 2)} for m in window3],
    })


# ─── Shared income basis (metrics 3 and 5) ────────────────────────────────────

def _income_basis(ledger: list[dict], today: date) -> dict:
    complete = _complete_months(ledger, today)
    credits = [t for t in ledger if t["type"] == TransactionType.credit]
    confirmed = [t for t in credits if t["income_confirmed"] is True]

    used_fallback = False
    if confirmed:
        income_txns = confirmed
    else:
        used_fallback = True
        income_txns = [t for t in credits if t["is_income_candidate"] and t["income_confirmed"] is None]

    by_month: dict[str, list[dict]] = defaultdict(list)
    for t in income_txns:
        by_month[t["month"]].append(t)

    qualifying_months = sorted(m for m in complete if by_month.get(m))
    current_month = today.strftime("%Y-%m")
    month_to_date = sum(t["amount"] for t in by_month.get(current_month, []))

    return {
        "by_month": by_month,
        "qualifying_months": qualifying_months,
        "used_fallback": used_fallback,
        "month_to_date": month_to_date,
    }


def _consistent_sources(by_month: dict[str, list[dict]], window: list[str]) -> bool:
    if len(window) < 2:
        return False
    per_month_sources = [
        {_normalize_merchant(t["description"]) for t in by_month[m]} for m in window
    ]
    if not all(per_month_sources):
        return False
    return bool(set.intersection(*per_month_sources))


def _income_sources(window_txns: list[dict], window_months: list[str]) -> list[dict]:
    by_source: dict[str, list[dict]] = defaultdict(list)
    for t in window_txns:
        by_source[_normalize_merchant(t["description"])].append(t)

    sources = []
    for key, items in by_source.items():
        items = sorted(items, key=lambda x: x["date"])
        total = sum(i["amount"] for i in items)
        monthly_avg = total / len(window_months) if window_months else 0.0
        cats = [i["income_category"] for i in items]
        category = max(set(cats), key=cats.count)

        if len(items) >= 2:
            gaps = [(items[i]["date"] - items[i - 1]["date"]).days for i in range(1, len(items))]
            cadence = _classify_cadence(statistics.mean(gaps)) or "irregular"
        else:
            cadence = "irregular"

        by_month_amt: dict[str, float] = defaultdict(float)
        for i in items:
            by_month_amt[i["month"]] += i["amount"]
        appears_every_month = set(by_month_amt.keys()).issuperset(set(window_months))
        month_amounts = list(by_month_amt.values())
        median = statistics.median(month_amounts) if month_amounts else 0.0
        stable_amounts = median > 0 and all(abs(a - median) <= 0.15 * median for a in month_amounts)
        stability = "stable" if appears_every_month and stable_amounts else "variable"

        sources.append({
            "source": key.title(),
            "income_category": category,
            "cadence": cadence,
            "monthly_avg": round(monthly_avg, 2),
            "stability": stability,
            "supporting_transaction_ids": [i["id"] for i in items],
        })

    sources.sort(key=lambda s: s["monthly_avg"], reverse=True)
    return sources


# ─── Metric 3: Average Monthly Income ──────────────────────────────────────────

def _average_monthly_income(ledger: list[dict], today: date) -> dict:
    basis = _income_basis(ledger, today)
    qualifying = basis["qualifying_months"]
    if not qualifying:
        return _insufficient("Import at least 1 month with confirmed or candidate income transactions.")

    by_month = basis["by_month"]
    window3 = qualifying[-3:]
    totals3 = {m: sum(t["amount"] for t in by_month[m]) for m in window3}
    income_3mo = statistics.mean(totals3.values())

    income_6mo = None
    if len(qualifying) >= 6:
        window6 = qualifying[-6:]
        income_6mo = statistics.mean(sum(t["amount"] for t in by_month[m]) for m in window6)

    window_txns = [t for m in window3 for t in by_month[m]]

    by_cat: dict[str, float] = defaultdict(float)
    for t in window_txns:
        by_cat[t["income_category"]] += t["amount"]
    by_category = [
        {"income_category": cat, "monthly_avg": round(total / len(window3), 2)}
        for cat, total in sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)
    ]

    sources = _income_sources(window_txns, window3)
    consistent = _consistent_sources(by_month, window3)

    conf = 0.0 if basis["used_fallback"] else 0.35
    conf += 0.25 if len(qualifying) >= 3 else 0.0
    conf += 0.20 if consistent else 0.0
    conf += 0.20  # transfers/refunds excluded by construction (income classifier)
    if basis["used_fallback"]:
        conf = max(conf - 0.20, 0.0)

    headline = f"Average monthly income: ${income_3mo:,.0f}"
    narrative = (
        f"Over the last {len(window3)} complete month{'s' if len(window3) != 1 else ''} "
        f"you've earned an average of ${income_3mo:,.0f}/month"
        f"{' (based on unconfirmed income candidates)' if basis['used_fallback'] else ' in confirmed income'}."
    )
    if sources:
        top = sources[0]
        narrative += f" ${top['monthly_avg']:,.0f} comes from {top['source']} ({top['cadence']}, {top['stability']})."
    narrative += f" {today.strftime('%B')} to date: ${basis['month_to_date']:,.0f}."

    return _ok(conf, headline, narrative, {
        "income_3mo": round(income_3mo, 2),
        "income_6mo": round(income_6mo, 2) if income_6mo is not None else None,
        "month_to_date": round(basis["month_to_date"], 2),
        "months_in_window": len(window3),
        "used_income_fallback": basis["used_fallback"],
        "by_category": by_category,
        "sources": sources,
        "monthly_series": [{"month": m, "confirmed_income": round(totals3[m], 2)} for m in window3],
    })


# ─── Metric 4: Fixed vs. Discretionary Baseline ────────────────────────────────

def _fixed_vs_discretionary(ledger: list[dict], today: date) -> dict:
    complete = _complete_months(ledger, today)
    if len(complete) < 2:
        return _insufficient("Import at least 2 complete months of statements.")

    commitments = detect_commitments(ledger, today)
    commitment_keys = {c["merchant_key"] for c in commitments}

    window = complete[-3:]
    window_set = set(window)

    fixed_by_month: dict[str, float] = defaultdict(float)
    discretionary_by_month: dict[str, float] = defaultdict(float)
    fixed_by_category: dict[str, float] = defaultdict(float)
    total_txn_count = 0
    uncategorized_count = 0

    for t in ledger:
        if t["type"] != TransactionType.debit or t["month"] not in window_set:
            continue
        if is_transfer(t["description"]):
            continue
        total_txn_count += 1
        if t["expense_category"] in (None, "other"):
            uncategorized_count += 1

        is_fixed = (
            _normalize_merchant(t["description"]) in commitment_keys
            or _matches_any(t["description"], _FIXED_OBLIGATION)
        )
        if is_fixed:
            fixed_by_month[t["month"]] += t["amount"]
            fixed_by_category[t["expense_category"] or "other"] += t["amount"]
        else:
            discretionary_by_month[t["month"]] += t["amount"]

    fixed_monthly_avg = sum(fixed_by_month.get(m, 0.0) for m in window) / len(window)
    discretionary_monthly_avg = sum(discretionary_by_month.get(m, 0.0) for m in window) / len(window)
    total_avg = fixed_monthly_avg + discretionary_monthly_avg
    fixed_pct = (fixed_monthly_avg / total_avg * 100) if total_avg else 0.0

    has_housing = (
        any(c["category"] == "housing" for c in commitments)
        or fixed_by_category.get("housing", 0) > 0
    )
    uncategorized_ratio = (uncategorized_count / total_txn_count) if total_txn_count else 1.0

    conf = 0.30 if len(window) >= 3 else 0.0
    conf += 0.25 if has_housing else 0.0
    conf += 0.25 if fixed_monthly_avg > 0 else 0.0
    conf += 0.20 if uncategorized_ratio < 0.30 else 0.0

    fixed_breakdown = [
        {"group": primary_display(cat), "monthly_avg": round(total / len(window), 2)}
        for cat, total in sorted(fixed_by_category.items(), key=lambda kv: kv[1], reverse=True)
    ]

    headline = f"Your baseline: {fixed_pct:.0f}% fixed, {100 - fixed_pct:.0f}% discretionary"
    narrative = (
        f"Of your ${total_avg:,.0f} average monthly spend, ${fixed_monthly_avg:,.0f} is structurally "
        f"committed. Your burn-rate floor is ${fixed_monthly_avg:,.0f} — the minimum a month costs you "
        "even with zero discretionary spending."
    )

    return _ok(conf, headline, narrative, {
        "fixed_monthly_avg": round(fixed_monthly_avg, 2),
        "discretionary_monthly_avg": round(discretionary_monthly_avg, 2),
        "fixed_pct": round(fixed_pct, 1),
        "burn_rate_floor": round(fixed_monthly_avg, 2),
        "fixed_breakdown": fixed_breakdown,
    })


# ─── Metric 5: Savings Rate ─────────────────────────────────────────────────────

def _savings_rate(ledger: list[dict], today: date) -> dict:
    basis = _income_basis(ledger, today)
    qualifying = basis["qualifying_months"]
    if not qualifying:
        return _insufficient("Import at least 1 complete month with confirmed or candidate income.")

    by_month_income = basis["by_month"]
    debit_totals = _debit_totals_by_month(ledger)
    window = qualifying[-3:]

    monthly_series = []
    for m in window:
        income = sum(t["amount"] for t in by_month_income[m])
        spend = debit_totals.get(m, 0.0)
        net = income - spend
        rate = (net / income) if income else 0.0
        monthly_series.append({"month": m, "income": round(income, 2), "spend": round(spend, 2), "rate": round(rate, 3)})

    window_income_total = sum(row["income"] for row in monthly_series)
    window_spend_total = sum(row["spend"] for row in monthly_series)
    window_net_total = window_income_total - window_spend_total
    savings_rate_3mo = (window_net_total / window_income_total) if window_income_total else 0.0

    consistent = _consistent_sources(by_month_income, window)

    conf = 0.0 if basis["used_fallback"] else 0.35
    conf += 0.25 if len(qualifying) >= 3 else 0.0
    conf += 0.20 if consistent else 0.0
    conf += 0.20  # transfers excluded by construction
    if basis["used_fallback"]:
        conf = max(conf - 0.20, 0.0)

    pct = savings_rate_3mo * 100
    headline = f"Savings rate: {pct:.0f}%"
    narrative = (
        f"Over the last {len(window)} complete month{'s' if len(window) != 1 else ''} you earned "
        f"${window_income_total:,.0f} in {'' if basis['used_fallback'] else 'confirmed '}income and spent "
        f"${window_spend_total:,.0f}, keeping ${window_net_total:,.0f} — a {pct:.0f}% savings rate."
    )

    return _ok(conf, headline, narrative, {
        "savings_rate_3mo": round(savings_rate_3mo, 3),
        "window_income_total": round(window_income_total, 2),
        "window_spend_total": round(window_spend_total, 2),
        "window_net_total": round(window_net_total, 2),
        "months_in_window": len(window),
        "used_income_fallback": basis["used_fallback"],
        "monthly_series": monthly_series,
    })


# ─── Metric 6: Fees & Interest Paid ────────────────────────────────────────────

def _fees_and_interest(ledger: list[dict], today: date) -> dict:
    if not ledger:
        return _insufficient("Import at least one statement.")

    debits = [t for t in ledger if t["type"] == TransactionType.debit]
    matched = [(t, _fee_subtype(t["description"])) for t in debits]
    matched = [(t, s) for t, s in matched if s]

    year_start = date(today.year, 1, 1)
    ytd = [(t, s) for t, s in matched if t["date"] >= year_start]
    ytd_total = sum(t["amount"] for t, _ in ytd)

    months = sorted({t["month"] for t in ledger})
    trailing_12mo_total = None
    if len(months) >= 12:
        cutoff = today - timedelta(days=365)
        trailing = [(t, s) for t, s in matched if t["date"] >= cutoff]
        trailing_12mo_total = sum(t["amount"] for t, _ in trailing)

    by_subtype: dict[str, dict] = defaultdict(lambda: {"ytd_total": 0.0, "transaction_count": 0})
    for t, s in ytd:
        by_subtype[s]["ytd_total"] += t["amount"]
        by_subtype[s]["transaction_count"] += 1

    breakdown = [
        {"sub_type": s, "ytd_total": round(v["ytd_total"], 2), "transaction_count": v["transaction_count"]}
        for s, v in sorted(by_subtype.items(), key=lambda kv: kv[1]["ytd_total"], reverse=True)
    ]

    conf = 0.40  # explicit-keyword matches only, no fuzzy matching
    conf += 0.25 if len(months) >= 6 else 0.0
    conf += 0.20  # curated patterns avoid ambiguous merchant-name matches
    clean_decrypt = all(t["description"] for t, _ in ytd)
    conf += 0.15 if clean_decrypt else 0.0

    if ytd_total == 0:
        headline = "Fees & interest paid: $0 this year"
        narrative = "No bank fees or interest charges detected this year."
    else:
        top = breakdown[0]
        headline = f"Fees & interest paid: ${ytd_total:,.0f} this year"
        narrative = (
            f"You've paid ${ytd_total:,.0f} in fees and interest YTD, largely "
            f"{_FEE_SUBTYPE_DISPLAY.get(top['sub_type'], top['sub_type'])} (${top['ytd_total']:,.0f})."
        )

    return _ok(conf, headline, narrative, {
        "ytd_total": round(ytd_total, 2),
        "trailing_12mo_total": round(trailing_12mo_total, 2) if trailing_12mo_total is not None else None,
        "breakdown": breakdown,
        "supporting_transaction_ids": [t["id"] for t, _ in ytd],
    })


# ─── Orchestrator ──────────────────────────────────────────────────────────────

def get_financial_profile(session: Session, user_id: int, today: date | None = None) -> dict:
    today = today or date.today()
    ledger = load_ledger(session, user_id)
    months_available = len({t["month"] for t in ledger})

    return {
        "computed_at": datetime.utcnow().isoformat() + "Z",
        "ledger_months_available": months_available,
        "metrics": {
            "committed_monthly_spend": _committed_monthly_spend(ledger, today),
            "average_monthly_burn": _average_monthly_burn(ledger, today),
            "average_monthly_income": _average_monthly_income(ledger, today),
            "fixed_vs_discretionary": _fixed_vs_discretionary(ledger, today),
            "savings_rate": _savings_rate(ledger, today),
            "fees_and_interest": _fees_and_interest(ledger, today),
        },
    }
