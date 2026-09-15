import json
import re
import statistics
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime
from typing import Optional

from sqlmodel import Session, select

from ..models.insight import Insight, InsightType, Severity
from ..models.transaction import Transaction, TransactionType
from ..services.expense_categorizer import CATEGORY_DISPLAY
from ..services.analytics import (
    load_ledger,
    cashflow_summary,
    income_summary,
    spending_by_category,
    compare_periods,
    is_transfer as _is_transfer,
    is_spending_txn,
)

_load_txns = load_ledger

# ─── Constants ───────────────────────────────────────────────────────────────

_KNOWN_SUBS = {
    "NETFLIX", "SPOTIFY", "HULU", "DISNEY+", "AMAZON PRIME", "APPLE",
    "GOOGLE", "YOUTUBE", "MICROSOFT", "ADOBE", "DROPBOX", "ICLOUD",
    "HBO", "PEACOCK", "PARAMOUNT", "PANDORA", "TIDAL", "AUDIBLE",
}

_HIGH_FREQ = {
    "WALMART", "TARGET", "COSTCO", "KROGER", "SAFEWAY", "WHOLE FOODS",
    "TRADER JOE", "PUBLIX", "CVS", "WALGREENS", "CHEVRON", "SHELL",
    "BP", "EXXON", "ARCO", "MCDONALD", "STARBUCKS", "DUNKIN", "SUBWAY",
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _norm(desc: str) -> str:
    d = desc.upper()
    d = re.sub(r"\*\S+", " ", d)
    d = re.sub(r"#\d+", " ", d)
    d = re.sub(r"\d{3}[.\-]\d{3}[.\-]\d{4}", " ", d)
    d = re.sub(r"\b\d{5,}\b", " ", d)
    words = [w for w in d.split() if len(w) > 1]
    return " ".join(words[:3]).strip()


def _month_start(ym: str) -> date:
    y, m = map(int, ym.split("-"))
    return date(y, m, 1)


def _month_end(ym: str) -> date:
    y, m = map(int, ym.split("-"))
    return date(y, m, monthrange(y, m)[1])


def _fmt(ym: str) -> str:
    return datetime.strptime(ym, "%Y-%m").strftime("%B %Y")


def _conf_label(c: float) -> str:
    if c >= 0.80:
        return "high"
    elif c >= 0.55:
        return "medium"
    return "low"


def _longest_run(months: list[str]) -> int:
    if not months:
        return 0
    s = sorted(months)
    best = cur = 1
    for i in range(1, len(s)):
        y1, m1 = map(int, s[i - 1].split("-"))
        y2, m2 = map(int, s[i].split("-"))
        if (y2 - y1) * 12 + (m2 - m1) == 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def _insight(
    job_id: str,
    itype: str,
    title: str,
    explanation: str,
    severity: str,
    confidence: float,
    next_step: str,
    supporting: list[int],
    meta: dict,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> dict:
    conf = min(1.0, max(0.0, confidence))
    return {
        "import_job_id": job_id,
        "insight_type": itype,
        "title": title,
        "explanation": explanation,
        "severity": severity,
        "confidence": conf,
        "confidence_label": _conf_label(conf),
        "time_period_start": start,
        "time_period_end": end,
        "supporting_transaction_ids": json.dumps(supporting),
        "suggested_next_step": next_step,
        "is_dismissed": False,
        "created_at": datetime.utcnow(),
        "meta_json": json.dumps(meta),
    }


def _monthly_debit_buckets(txns: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for t in txns:
        if t["type"] == TransactionType.debit and not _is_transfer(t["description"]):
            buckets[t["month"]].append(t)
    return buckets


def _monthly_income_totals(txns: list[dict]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for t in txns:
        if t["type"] != TransactionType.credit:
            continue
        if t["income_confirmed"] is True:
            totals[t["month"]] += t["amount"]
        elif t["is_income_candidate"] and t["income_confirmed"] is None:
            totals[t["month"]] += t["amount"]
    return totals


# ─── Detector 1: Spending Increase ───────────────────────────────────────────

def _spending_increase(txns: list[dict], months: list[str], job_id: str) -> list[dict]:
    if len(months) < 2:
        return []
    current = months[-1]
    buckets = _monthly_debit_buckets(txns)
    cur_txns = buckets.get(current, [])
    cur_amt = sum(t["amount"] for t in cur_txns)

    prior = [m for m in months[:-1] if m in buckets]
    if not prior:
        return []
    baseline_slice = prior[-3:]
    baseline_avg = statistics.mean(
        sum(t["amount"] for t in buckets[m]) for m in baseline_slice
    )
    if baseline_avg == 0 or cur_amt == 0:
        return []

    pct = (cur_amt - baseline_avg) / baseline_avg * 100
    if pct < 20:
        return []

    delta = cur_amt - baseline_avg
    sev = (
        Severity.high if (pct >= 75 or delta >= 500)
        else Severity.medium if (pct >= 35 or delta >= 100)
        else Severity.low
    )
    conf = (0.30 if len(baseline_slice) >= 3 else 0.15) + 0.20 + (0.20 if len(cur_txns) >= 5 else 0) + 0.15 + 0.15
    fmt = _fmt(current)

    return [_insight(
        job_id, InsightType.spending_increase,
        f"Overall spending up {pct:.0f}% in {fmt}",
        (f"You spent ${cur_amt:,.2f} in {fmt}, compared to your {len(baseline_slice)}-month "
         f"average of ${baseline_avg:,.2f}. That's {pct:.1f}% more than usual — a ${delta:,.2f} difference."),
        sev, conf,
        f"Review your largest {fmt} transactions to identify what drove the ${delta:,.0f} increase.",
        [t["id"] for t in sorted(cur_txns, key=lambda x: x["amount"], reverse=True)[:20]],
        {"category": "Overall", "current_period_amount": round(cur_amt, 2),
         "baseline_amount": round(baseline_avg, 2), "pct_change": round(pct, 1),
         "driver_transaction_count": len(cur_txns)},
        _month_start(current), _month_end(current),
    )]


# ─── Detector 2: Spending Decrease ───────────────────────────────────────────

def _spending_decrease(txns: list[dict], months: list[str], job_id: str) -> list[dict]:
    if len(months) < 2:
        return []
    current = months[-1]
    buckets = _monthly_debit_buckets(txns)
    cur_txns = buckets.get(current, [])
    cur_amt = sum(t["amount"] for t in cur_txns)

    prior = [m for m in months[:-1] if m in buckets]
    if not prior:
        return []
    baseline_slice = prior[-3:]
    baseline_avg = statistics.mean(
        sum(t["amount"] for t in buckets[m]) for m in baseline_slice
    )
    if baseline_avg < 50 or cur_amt == 0:
        return []

    pct = (cur_amt - baseline_avg) / baseline_avg * 100
    if pct > -15:
        return []

    saved = baseline_avg - cur_amt
    conf = (0.30 if len(baseline_slice) >= 3 else 0.15) + 0.20 + (0.20 if len(cur_txns) >= 5 else 0) + 0.15 + 0.15
    fmt = _fmt(current)

    return [_insight(
        job_id, InsightType.spending_decrease,
        f"Spending down {abs(pct):.0f}% in {fmt}",
        (f"You spent ${cur_amt:,.2f} in {fmt}, compared to your {len(baseline_slice)}-month "
         f"average of ${baseline_avg:,.2f}. That's {abs(pct):.1f}% less than usual — ${saved:,.2f} saved."),
        Severity.low, conf,
        "Confirm this reduction is intentional and make sure you haven't missed any recurring bills.",
        [t["id"] for t in cur_txns[:20]],
        {"category": "Overall", "current_period_amount": round(cur_amt, 2),
         "baseline_amount": round(baseline_avg, 2), "pct_change": round(pct, 1)},
        _month_start(current), _month_end(current),
    )]


# ─── Detector 3: Income Change ────────────────────────────────────────────────

def _income_change(txns: list[dict], months: list[str], job_id: str) -> list[dict]:
    if len(months) < 2:
        return []
    current = months[-1]

    confirmed_by_month: dict[str, float] = defaultdict(float)
    candidate_by_month: dict[str, float] = defaultdict(float)
    income_txns_by_month: dict[str, list[dict]] = defaultdict(list)

    for t in txns:
        if t["type"] != TransactionType.credit:
            continue
        if t["income_confirmed"] is True:
            confirmed_by_month[t["month"]] += t["amount"]
            income_txns_by_month[t["month"]].append(t)
        elif t["is_income_candidate"] and t["income_confirmed"] is None:
            candidate_by_month[t["month"]] += t["amount"]
            income_txns_by_month[t["month"]].append(t)

    use_confirmed = bool(confirmed_by_month)
    income_by_month = (
        confirmed_by_month if use_confirmed
        else {m: confirmed_by_month.get(m, 0) + candidate_by_month.get(m, 0) for m in months}
    )

    cur_income = income_by_month.get(current, 0)
    prior_with_income = [m for m in months[:-1] if income_by_month.get(m, 0) > 0][-2:]
    if not prior_with_income or cur_income == 0:
        return []

    baseline = statistics.mean(income_by_month[m] for m in prior_with_income)
    if baseline == 0:
        return []

    pct = (cur_income - baseline) / baseline * 100
    if abs(pct) < 15:
        return []

    conf = (0.35 if use_confirmed else 0.15) + (0.25 if len(prior_with_income) >= 2 else 0.10) + 0.20 + 0.20
    fmt = _fmt(current)
    direction = "decrease" if pct < 0 else "increase"

    if pct < 0:
        sev = Severity.high if abs(pct) > 30 else Severity.medium
        title = f"Income appears lower in {fmt}"
        explanation = (
            f"Your {'confirmed ' if use_confirmed else ''}income for {fmt} was ${cur_income:,.2f}, "
            f"down from your {len(prior_with_income)}-month average of ${baseline:,.2f} "
            f"(a {abs(pct):.1f}% decrease)."
        )
        next_step = f"Review your {fmt} income transactions and confirm all income has been imported."
    else:
        sev = Severity.low
        title = f"Income up {pct:.0f}% in {fmt}"
        explanation = (
            f"Your {'confirmed ' if use_confirmed else ''}income for {fmt} was ${cur_income:,.2f}, "
            f"up from your {len(prior_with_income)}-month average of ${baseline:,.2f} "
            f"(a {pct:.1f}% increase)."
        )
        next_step = "Verify this increase reflects real income and determine whether it is recurring or a one-time event."

    return [_insight(
        job_id, InsightType.income_change, title, explanation, sev, conf, next_step,
        [t["id"] for t in income_txns_by_month.get(current, [])[:20]],
        {"current_income": round(cur_income, 2), "baseline_income": round(baseline, 2),
         "pct_change": round(pct, 1), "direction": direction},
        _month_start(current), _month_end(current),
    )]


# ─── Detector 4: Recurring Charge ────────────────────────────────────────────

def _recurring_charges(txns: list[dict], job_id: str) -> list[dict]:
    by_merchant: dict[str, list[dict]] = defaultdict(list)
    for t in txns:
        if t["type"] == TransactionType.debit and not _is_transfer(t["description"]):
            merchant = _norm(t["description"])
            if merchant:
                by_merchant[merchant].append(t)

    results = []
    for merchant, mtxns in by_merchant.items():
        by_month: dict[str, list[dict]] = defaultdict(list)
        for t in mtxns:
            by_month[t["month"]].append(t)

        m_months = sorted(by_month.keys())
        if _longest_run(m_months) < 2:
            continue

        month_avgs = [
            sum(t["amount"] for t in by_month[m]) / len(by_month[m])
            for m in m_months
        ]
        if not month_avgs:
            continue
        avg_amt = statistics.mean(month_avgs)
        if avg_amt == 0:
            continue

        # Require amounts within 10% of each other
        if any(abs(a - avg_amt) / avg_amt > 0.10 for a in month_avgs):
            continue

        run = _longest_run(m_months)
        sev = (
            Severity.high if avg_amt > 100
            else Severity.medium if avg_amt > 20
            else Severity.low
        )

        conf = (0.35 if run >= 3 else 0.20)
        stdev = statistics.stdev(month_avgs) if len(month_avgs) > 1 else 0
        var_ratio = stdev / avg_amt if avg_amt else 1
        conf += 0.25 if var_ratio < 0.05 else 0.15 if var_ratio < 0.10 else 0
        conf += 0.20 if any(s in merchant for s in _KNOWN_SUBS) else 0
        all_days = [t["date"].day for m in m_months for t in by_month[m]]
        conf += 0.20 if all_days and (max(all_days) - min(all_days)) <= 3 else 0

        annualized = avg_amt * 12
        display = merchant.title()
        supporting = [t["id"] for m in m_months for t in by_month[m]]

        results.append(_insight(
            job_id, InsightType.recurring_charge,
            f"Recurring charge detected: {display}",
            (f"{display} has charged approximately ${avg_amt:,.2f} per month for at least "
             f"{len(m_months)} months. Annualized cost: ${annualized:,.2f}/year."),
            sev, conf,
            f"Verify that {display} is still actively in use.",
            supporting[:20],
            {"merchant": display, "cadence": "monthly", "amount_per_period": round(avg_amt, 2),
             "occurrences_detected": len(m_months), "annualized_cost": round(annualized, 2)},
            _month_start(m_months[0]), _month_end(m_months[-1]),
        ))

    return results


# ─── Detector 5: Possible Duplicate Charge ───────────────────────────────────

def _duplicate_charges(txns: list[dict], job_id: str) -> list[dict]:
    debits = [t for t in txns if t["type"] == TransactionType.debit]
    results = []
    seen: set[tuple[int, int]] = set()

    for i, t1 in enumerate(debits):
        m1 = _norm(t1["description"])
        if not m1 or any(hf in m1 for hf in _HIGH_FREQ):
            continue
        for t2 in debits[i + 1:]:
            if abs((t2["date"] - t1["date"]).days) > 7:
                continue
            if _norm(t2["description"]) != m1:
                continue
            if t1["amount"] == 0:
                continue
            amt_diff = abs(t1["amount"] - t2["amount"]) / max(t1["amount"], t2["amount"])
            if amt_diff > 0.02:
                continue

            pair = (min(t1["id"], t2["id"]), max(t1["id"], t2["id"]))
            if pair in seen:
                continue
            seen.add(pair)

            days = abs((t2["date"] - t1["date"]).days)
            avg = (t1["amount"] + t2["amount"]) / 2
            sev = Severity.high if avg > 100 else Severity.medium if avg > 20 else Severity.low
            conf = (0.40 if amt_diff < 0.001 else 0.20) + (0.30 if days == 0 else 0.20 if days <= 1 else 0.10) + 0.20 + (0.10 if avg > 50 else 0)
            display = m1.title()
            dates = sorted([str(t1["date"]), str(t2["date"])])

            results.append(_insight(
                job_id, InsightType.duplicate_charge,
                f"Possible duplicate charge: {display}",
                (f"{display} was charged ${t1['amount']:,.2f} on {dates[0]} "
                 f"and ${t2['amount']:,.2f} on {dates[-1]}. "
                 f"These may be a billing error rather than two separate purchases."),
                sev, conf,
                f"Check your {display} billing history and contact support if both charges are confirmed.",
                [t1["id"], t2["id"]],
                {"merchant": display, "amount": round(avg, 2),
                 "transaction_dates": dates, "days_apart": days},
                min(t1["date"], t2["date"]), max(t1["date"], t2["date"]),
            ))
            if len(results) >= 5:
                return results
    return results


# ─── Detector 6: Large Unusual Expense ───────────────────────────────────────

def _large_expenses(txns: list[dict], job_id: str) -> list[dict]:
    debits = [t for t in txns if t["type"] == TransactionType.debit and not _is_transfer(t["description"])]
    if len(debits) < 30:
        return []

    amounts = sorted(t["amount"] for t in debits)
    median = statistics.median(amounts)
    p95 = amounts[int(0.95 * len(amounts))]
    p98 = amounts[int(0.98 * len(amounts))]

    results = []
    seen: set[int] = set()
    for t in sorted(debits, key=lambda x: x["amount"], reverse=True):
        if t["id"] in seen or t["amount"] < p95 or t["amount"] <= 2 * median:
            continue
        seen.add(t["id"])
        sev = Severity.high if t["amount"] >= p98 else Severity.medium
        multiple = t["amount"] / median if median else 0
        display = _norm(t["description"]).title() or "Unknown merchant"
        conf = 0.35 + 0.25 + 0.25 + (0.15 if multiple >= 2 else 0)

        results.append(_insight(
            job_id, InsightType.large_expense,
            f"Unusually large expense: ${t['amount']:,.2f} at {display}",
            (f"A ${t['amount']:,.2f} charge at {display} on {t['date']} is {multiple:.1f}× "
             f"your typical transaction amount (${median:,.2f} median)."),
            sev, conf,
            "Confirm this was an intended purchase and consider noting it as a one-time expense.",
            [t["id"]],
            {"merchant": display, "amount": round(t["amount"], 2),
             "user_median_transaction": round(median, 2),
             "user_p95_transaction": round(p95, 2),
             "multiple_of_median": round(multiple, 2)},
            t["date"], t["date"],
        ))
        if len(results) >= 5:
            break
    return results


# ─── Detector 7: Merchant Spike ──────────────────────────────────────────────

def _merchant_spike(txns: list[dict], months: list[str], job_id: str) -> list[dict]:
    if len(months) < 2:
        return []
    current = months[-1]
    prior3 = months[:-1][-3:]

    by_merchant_month: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for t in txns:
        if t["type"] == TransactionType.debit and not _is_transfer(t["description"]):
            m = _norm(t["description"])
            if m:
                by_merchant_month[m][t["month"]].append(t)

    results = []
    for merchant, month_data in by_merchant_month.items():
        cur_txns = month_data.get(current, [])
        if not cur_txns:
            continue
        prior_months_with_data = [m for m in prior3 if m in month_data]
        if len(prior_months_with_data) < 2:
            continue

        cur_amt = sum(t["amount"] for t in cur_txns)
        baseline = statistics.mean(
            sum(t["amount"] for t in month_data[m]) for m in prior_months_with_data
        )
        if baseline == 0:
            continue

        pct = (cur_amt - baseline) / baseline * 100
        delta = cur_amt - baseline
        if pct < 40 or delta < 50:
            continue

        sev = (
            Severity.high if (pct >= 150 or delta >= 500)
            else Severity.medium if (pct >= 75 or delta >= 200)
            else Severity.low
        )
        conf = (0.30 if len(prior_months_with_data) >= 3 else 0.15) + 0.25 + 0.25 + 0.20
        display = merchant.title()
        fmt = _fmt(current)

        results.append(_insight(
            job_id, InsightType.merchant_spike,
            f"{display} spending up {pct:.0f}% in {fmt}",
            (f"You spent ${cur_amt:,.2f} at {display} in {fmt}, compared to your "
             f"{len(prior_months_with_data)}-month average of ${baseline:,.2f} "
             f"(a {pct:.1f}% increase, ${delta:,.2f} more)."),
            sev, conf,
            f"Review {fmt} {display} charges to identify any large or unexpected transactions.",
            [t["id"] for t in cur_txns[:20]],
            {"merchant": display, "current_period_amount": round(cur_amt, 2),
             "baseline_amount": round(baseline, 2), "pct_change": round(pct, 1)},
            _month_start(current), _month_end(current),
        ))

    results.sort(key=lambda x: json.loads(x["meta_json"]).get("pct_change", 0), reverse=True)
    return results[:5]


# ─── Detector 8: Cashflow Risk ────────────────────────────────────────────────

def _cashflow_risk(txns: list[dict], months: list[str], job_id: str) -> list[dict]:
    if not months:
        return []
    current = months[-1]

    income_totals = _monthly_income_totals(txns)
    expense_totals = {
        m: sum(t["amount"] for t in txns if t["month"] == m and t["type"] == TransactionType.debit and not _is_transfer(t["description"]))
        for m in months
    }

    cur_income = income_totals.get(current, 0)
    cur_expense = expense_totals.get(current, 0)
    cur_net = cur_income - cur_expense

    if cur_income == 0 and cur_expense == 0:
        return []

    prior_net: Optional[float] = None
    if len(months) >= 2:
        p = months[-2]
        prior_net = income_totals.get(p, 0) - expense_totals.get(p, 0)

    is_negative = cur_net < 0
    is_thin = cur_income > 0 and 0 <= cur_net <= cur_income * 0.10
    is_narrowing = (
        prior_net is not None
        and prior_net > 0
        and cur_net >= 0
        and (prior_net - cur_net) / prior_net >= 0.30
    )

    if not (is_negative or is_thin or is_narrowing):
        return []

    use_confirmed = any(t["income_confirmed"] is True for t in txns if t["month"] == current and t["type"] == TransactionType.credit)
    conf = (0.35 if use_confirmed else 0.15) + 0.25 + 0.20 + (0.20 if len(months) >= 2 else 0)

    fmt = _fmt(current)
    all_ids = [t["id"] for t in txns if t["month"] == current][:20]

    if is_negative:
        variant = "negative"
        sev = Severity.high
        title = f"Cashflow risk: spending exceeded income in {fmt}"
        explanation = (
            f"Your income for {fmt} was ${cur_income:,.2f}, but total expenses were "
            f"${cur_expense:,.2f}, leaving a net outflow of ${abs(cur_net):,.2f}."
        )
        if prior_net is not None:
            explanation += f" Prior month net was ${prior_net:,.2f}."
        next_step = "Identify which expense categories drove the overage and determine if any are reducible next month."
    elif is_thin:
        variant = "thin"
        sev = Severity.medium
        title = f"Thin cashflow margin in {fmt}"
        margin_pct = cur_net / cur_income * 100 if cur_income else 0
        explanation = (
            f"Your net cashflow in {fmt} was ${cur_net:,.2f} on income of ${cur_income:,.2f} "
            f"— only {margin_pct:.1f}% of income remains after expenses. "
            f"A small unexpected expense could put you in the negative."
        )
        next_step = "Review your expenses to identify areas where you could build more buffer."
    else:
        variant = "narrowing"
        sev = Severity.medium
        narrowing_pct = (prior_net - cur_net) / prior_net * 100 if prior_net else 0
        title = f"Cashflow margin narrowing in {fmt}"
        explanation = (
            f"Your net cashflow was ${cur_net:,.2f} in {fmt}, down from ${prior_net:,.2f} "
            f"the prior month — a {narrowing_pct:.1f}% reduction in margin."
        )
        next_step = "Monitor your spending trend and identify which categories have grown."

    return [_insight(
        job_id, InsightType.cashflow_risk, title, explanation, sev, conf, next_step,
        all_ids,
        {"period": current, "confirmed_income": round(cur_income, 2),
         "total_expenses": round(cur_expense, 2), "net_cashflow": round(cur_net, 2),
         "prior_month_net_cashflow": round(prior_net, 2) if prior_net is not None else None,
         "variant": variant},
        _month_start(current), _month_end(current),
    )]


# ─── Detector 9: Transfer Detection ──────────────────────────────────────────

def _transfer_detected(txns: list[dict], job_id: str) -> list[dict]:
    _KW = re.compile(
        r"transfer|zelle|wire|ach|from\s+checking|to\s+savings|ext\s+trnsf",
        re.IGNORECASE,
    )
    credits = [t for t in txns if t["type"] == TransactionType.credit and t["income_confirmed"] is not False]
    debits = [t for t in txns if t["type"] == TransactionType.debit]

    results = []
    seen: set[int] = set()

    for credit in credits:
        if credit["id"] in seen:
            continue
        has_kw = bool(_KW.search(credit["description"]))

        for debit in debits:
            days = abs((credit["date"] - debit["date"]).days)
            if days > 3 or credit["amount"] == 0:
                continue
            diff = abs(credit["amount"] - debit["amount"]) / max(credit["amount"], debit["amount"])
            if diff > 0.01:
                continue

            debit_kw = bool(_KW.search(debit["description"]))
            if not has_kw and not debit_kw and days > 1:
                continue

            seen.add(credit["id"])
            conf = min(1.0, 0.40 + (0.20 if diff < 0.001 else 0) + (0.25 if has_kw else 0) + (0.15 if debit_kw else 0))
            basis = "amount_and_keyword" if (has_kw or debit_kw) else "amount"

            results.append(_insight(
                job_id, InsightType.transfer_detected,
                f"Likely transfer detected: ${credit['amount']:,.2f} on {credit['date']}",
                (f"A ${credit['amount']:,.2f} credit on {credit['date']} closely matches "
                 f"a ${debit['amount']:,.2f} debit on {debit['date']}. "
                 f"These may be an internal transfer rather than income or an expense."),
                Severity.low, conf,
                "Confirm these are internal transfers so they are excluded from your income and cashflow totals.",
                [credit["id"], debit["id"]],
                {"credit_transaction_id": credit["id"], "debit_transaction_id": debit["id"],
                 "amount": round(credit["amount"], 2), "days_apart": days, "match_basis": basis},
                min(credit["date"], debit["date"]), max(credit["date"], debit["date"]),
            ))
            break
        if len(results) >= 5:
            break
    return results


# ─── Detector 10: Subscription Creep ─────────────────────────────────────────

def _subscription_creep(txns: list[dict], months: list[str], job_id: str) -> list[dict]:
    if len(months) < 2:
        return []

    # Identify recurring merchants using same criteria as detector 4
    by_merchant: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for t in txns:
        if t["type"] == TransactionType.debit and not _is_transfer(t["description"]):
            m = _norm(t["description"])
            if m:
                by_merchant[m][t["month"]].append(t)

    recurring: set[str] = set()
    for merchant, month_data in by_merchant.items():
        m_months = sorted(month_data.keys())
        if _longest_run(m_months) < 2:
            continue
        avgs = [sum(t["amount"] for t in month_data[m]) / len(month_data[m]) for m in m_months]
        avg = statistics.mean(avgs) if avgs else 0
        if avg > 0 and all(abs(a - avg) / avg <= 0.15 for a in avgs):
            recurring.add(merchant)

    if len(recurring) < 3:
        return []

    monthly_total: dict[str, float] = defaultdict(float)
    monthly_merchants_set: dict[str, set[str]] = defaultdict(set)
    for t in txns:
        if t["type"] == TransactionType.debit and not _is_transfer(t["description"]):
            m = _norm(t["description"])
            if m in recurring:
                monthly_total[t["month"]] += t["amount"]
                monthly_merchants_set[t["month"]].add(m)

    current = months[-1]
    earliest = months[0]

    cur_total = monthly_total.get(current, 0)
    early_total = monthly_total.get(earliest, 0)
    if early_total == 0 or cur_total == 0:
        return []

    delta = cur_total - early_total
    if delta < 30:
        return []

    pct = delta / early_total * 100
    if pct < 20:
        return []

    sev = (
        Severity.high if (delta >= 250 or pct >= 75)
        else Severity.medium if (delta >= 100 or pct >= 35)
        else Severity.low
    )
    conf = (0.30 if len(months) >= 3 else 0.15) + (0.30 if len(recurring) >= 3 else 0.15) + 0.25 + 0.15

    new_merchants = monthly_merchants_set.get(current, set()) - monthly_merchants_set.get(earliest, set())
    new_names = [m.title() for m in list(new_merchants)[:3]]
    fmt_early = _fmt(earliest)
    fmt_cur = _fmt(current)

    explanation = (
        f"Your total recurring subscription spend has grown from ${early_total:,.2f}/month in {fmt_early} "
        f"to ${cur_total:,.2f}/month in {fmt_cur} — a {pct:.1f}% increase (${delta:,.2f} more)."
    )
    if new_names:
        explanation += f" New additions include {', '.join(new_names)}."

    all_ids = [t["id"] for t in txns if t["type"] == TransactionType.debit and _norm(t["description"]) in recurring]

    return [_insight(
        job_id, InsightType.subscription_creep,
        f"Subscription spend up ${delta:,.0f}/month since {fmt_early}",
        explanation, sev, conf,
        "Review your full subscription list and cancel any services you're not actively using.",
        all_ids[:20],
        {"earliest_month": earliest, "earliest_month_total": round(early_total, 2),
         "current_month_total": round(cur_total, 2), "absolute_delta": round(delta, 2),
         "pct_change": round(pct, 1), "new_merchants_detected": new_names},
        _month_start(earliest), _month_end(current),
    )]


# ─── Detector 11: Top Spending Category ──────────────────────────────────────

def _top_spending_category(txns: list[dict], months: list[str], job_id: str) -> list[dict]:
    if not months:
        return []
    current = months[-1]

    cat_totals: dict[str, float] = defaultdict(float)
    cat_txns: dict[str, list[dict]] = defaultdict(list)

    for t in txns:
        if t["month"] == current and t["type"] == TransactionType.debit and not _is_transfer(t["description"]):
            cat = t.get("expense_category") or "other"
            cat_totals[cat] += t["amount"]
            cat_txns[cat].append(t)

    if not cat_totals:
        return []

    total = sum(cat_totals.values())
    if total == 0:
        return []

    ranked = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
    top_cat, top_amt = ranked[0]
    top_pct = top_amt / total * 100
    top_name = CATEGORY_DISPLAY.get(top_cat, top_cat.title())
    fmt = _fmt(current)

    breakdown = [
        {"category": cat, "name": CATEGORY_DISPLAY.get(cat, cat.title()),
         "amount": round(amt, 2), "pct": round(amt / total * 100, 1)}
        for cat, amt in ranked[:5]
    ]
    breakdown_text = ", ".join(
        f"{d['name']} (${d['amount']:,.0f}, {d['pct']:.0f}%)" for d in breakdown[:3]
    )

    sev = Severity.medium if top_pct >= 40 else Severity.low
    conf = 0.75 if len(ranked) >= 3 else 0.55

    return [_insight(
        job_id, InsightType.top_spending_category,
        f"{top_name} is your top expense in {fmt}",
        (f"You spent ${top_amt:,.2f} on {top_name} in {fmt} — {top_pct:.0f}% of your "
         f"${total:,.2f} total spending. Top categories: {breakdown_text}."),
        sev, conf,
        f"Review your {top_name} transactions in {fmt} to see if there are areas to cut back.",
        [t["id"] for t in cat_txns[top_cat][:20]],
        {"top_category": top_cat, "top_category_name": top_name,
         "top_category_amount": round(top_amt, 2), "top_category_pct": round(top_pct, 1),
         "total_spending": round(total, 2), "breakdown": breakdown},
        _month_start(current), _month_end(current),
    )]


# ─── Detector 12: Category Spending Spike ────────────────────────────────────

def _category_spike(txns: list[dict], months: list[str], job_id: str) -> list[dict]:
    if len(months) < 2:
        return []
    current = months[-1]

    by_cat_month: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for t in txns:
        if t["type"] == TransactionType.debit and not _is_transfer(t["description"]):
            cat = t.get("expense_category") or "other"
            by_cat_month[cat][t["month"]].append(t)

    results = []
    for cat, month_data in by_cat_month.items():
        if cat == "other":
            continue  # too noisy without specific signal
        cur_txns = month_data.get(current, [])
        if not cur_txns:
            continue

        cur_amt = sum(t["amount"] for t in cur_txns)
        prior_months = [m for m in months[:-1][-3:] if m in month_data]
        if not prior_months:
            continue

        baseline = statistics.mean(sum(t["amount"] for t in month_data[m]) for m in prior_months)
        if baseline == 0:
            continue

        pct = (cur_amt - baseline) / baseline * 100
        delta = cur_amt - baseline
        if pct < 20 or delta < 30:
            continue

        sev = (
            Severity.high if (pct >= 75 or delta >= 300)
            else Severity.medium if (pct >= 35 or delta >= 100)
            else Severity.low
        )
        conf = (0.30 if len(prior_months) >= 3 else 0.20) + 0.30 + (0.20 if len(cur_txns) >= 3 else 0.10) + 0.20
        cat_name = CATEGORY_DISPLAY.get(cat, cat.title())
        fmt = _fmt(current)

        results.append(_insight(
            job_id, InsightType.category_spike,
            f"{cat_name} spending up {pct:.0f}% in {fmt}",
            (f"You spent ${cur_amt:,.2f} on {cat_name} in {fmt}, compared to your "
             f"{len(prior_months)}-month average of ${baseline:,.2f} "
             f"(a {pct:.1f}% increase, ${delta:,.2f} more)."),
            sev, conf,
            f"Review your {fmt} {cat_name} transactions to see what drove the ${delta:,.0f} increase.",
            [t["id"] for t in cur_txns[:20]],
            {"category": cat, "category_name": cat_name,
             "current_period_amount": round(cur_amt, 2),
             "baseline_amount": round(baseline, 2),
             "pct_change": round(pct, 1),
             "driver_transaction_count": len(cur_txns)},
            _month_start(current), _month_end(current),
        ))

    results.sort(key=lambda x: json.loads(x["meta_json"]).get("pct_change", 0), reverse=True)
    return results[:4]


# ─── Main entry point ─────────────────────────────────────────────────────────

def _dedup_key(d: dict) -> tuple:
    meta = json.loads(d.get("meta_json", "{}"))
    # Include category in key so multiple per-category insights can coexist
    cat = meta.get("category", meta.get("top_category", ""))
    return (d["insight_type"], cat, d.get("time_period_start"), d.get("time_period_end"))


def _run_detectors(txns: list[dict], job_id: str = "") -> list[dict]:
    """Run the full detector battery over a ledger and return candidate insight
    dicts. Pure: no dedup, no persistence. `job_id` only labels the dicts."""
    months = sorted(set(t["month"] for t in txns))
    # For debit-based detectors, use months that actually have debit activity
    debit_month_set = {
        t["month"] for t in txns
        if t["type"] == TransactionType.debit and not _is_transfer(t["description"])
    }
    debit_months = [m for m in months if m in debit_month_set]
    multi = len(debit_months) >= 2

    candidates: list[dict] = []

    # Non-comparative (always run)
    candidates.extend(_duplicate_charges(txns, job_id))
    candidates.extend(_large_expenses(txns, job_id))
    candidates.extend(_recurring_charges(txns, job_id))
    candidates.extend(_transfer_detected(txns, job_id))
    candidates.extend(_top_spending_category(txns, debit_months, job_id))

    # Comparative (≥2 months of debit activity)
    if multi:
        candidates.extend(_spending_increase(txns, debit_months, job_id))
        candidates.extend(_spending_decrease(txns, debit_months, job_id))
        candidates.extend(_income_change(txns, months, job_id))  # income uses all months
        candidates.extend(_merchant_spike(txns, debit_months, job_id))
        candidates.extend(_cashflow_risk(txns, debit_months, job_id))
        candidates.extend(_subscription_creep(txns, debit_months, job_id))
        candidates.extend(_category_spike(txns, debit_months, job_id))

    return candidates


def collect_signals(session: Session, user_id: int) -> list[dict]:
    """Whole-ledger detector signals as plain dicts, without persisting anything.

    This is the grounded candidate set the AI insight layer reasons over. The
    `import_job_id` field on each dict is a harmless empty-string label."""
    txns = _load_txns(session, user_id)
    if not txns:
        return []
    return _run_detectors(txns)


# ─── Proactive post-import observations (PRD F4) ─────────────────────────────
#
# The PRD asks the chatbot to surface 2–3 plain-language observations right after
# each import — at least one spending observation and one income/cashflow
# observation, each citing a real number. This is a thin selector over the same
# detector battery (the grounded signal source); it does not persist anything and
# is intentionally far narrower than the full insight feed.

_SPENDING_OBS_PRIORITY = [
    InsightType.spending_increase,
    InsightType.merchant_spike,
    InsightType.category_spike,
    InsightType.top_spending_category,
    InsightType.large_expense,
]


def proactive_observations(session: Session, user_id: int, job_id: str) -> list[dict]:
    """Return 2–3 grounded observations for the chat window after an import.

    Each observation is ``{kind, title, text}`` where ``kind`` is one of
    ``summary`` | ``spending`` | ``anomaly``. Always includes an income/cashflow
    summary scoped to the imported period, plus the most salient spending signal
    and (if present) one anomaly. Returns ``[]`` only when there is no data.
    """
    txns = _load_txns(session, user_id)
    if not txns:
        return []

    candidates = _run_detectors(txns, job_id)
    observations: list[dict] = []

    # 1) Income/cashflow summary, scoped to the months this import touched.
    job_rows = session.exec(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.import_job_id == job_id)
        .where(Transaction.is_duplicate == False)   # noqa: E712
        .where(Transaction.is_ambiguous == False)    # noqa: E712
    ).all()
    if job_rows:
        months = sorted({r.date.strftime("%Y-%m") for r in job_rows})
        latest = months[-1]
        cf = cashflow_summary(session, user_id, {"month": latest})
        net = cf["net_cashflow"]
        label = _fmt(latest)
        sign = "+" if net >= 0 else "-"
        observations.append({
            "kind": "summary",
            "title": f"Imported {len(job_rows)} transactions from {label}",
            "text": (f"This import added {len(job_rows)} transactions. Your net cash flow "
                     f"for {label} was {sign}${abs(net):,.2f} "
                     f"(${cf['total_credits']:,.2f} in, ${cf['total_debits']:,.2f} out)."),
        })

    # 2) Most salient spending observation.
    spending = None
    for itype in _SPENDING_OBS_PRIORITY:
        match = next((c for c in candidates if c["insight_type"] == itype), None)
        if match:
            spending = {"kind": "spending", "title": match["title"], "text": match["explanation"]}
            break
    if spending:
        observations.append(spending)

    # 3) One anomaly (possible duplicate charge), if distinct from above.
    dup = next((c for c in candidates if c["insight_type"] == InsightType.duplicate_charge), None)
    if dup and (not spending or dup["title"] != spending["title"]):
        observations.append({"kind": "anomaly", "title": dup["title"], "text": dup["explanation"]})

    return observations[:3]


# ─── Dashboard insights (AMI-48) ──────────────────────────────────────────────
#
# Top-3 proactive insights for the per-import summary page, picked from 5
# candidate types. Unlike the anomaly detectors above, these are always-computed
# current-state metrics (not gated on crossing an anomaly threshold) except where
# the ticket names an explicit threshold ("MoM change >20%", ">2x category
# average"). Each candidate is built directly on analytics.py tool functions so
# the cited numbers are the same ones the chatbot would return for the same
# question — nothing here re-derives ledger math independently.

_DASH_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _dash_top_category(session: Session, user_id: int, month: str, prior_month: Optional[str]) -> Optional[dict]:
    cur = spending_by_category(session, user_id, {"month": month})
    if not cur["by_primary"]:
        return None
    top = cur["by_primary"][0]
    total = cur["total_spending"]
    label = cur["period"]["label"]
    top_pct = (top["amount"] / total * 100) if total else 0

    pct_change = None
    if prior_month:
        cmp = compare_periods(session, user_id, {"month": prior_month}, {"month": month}, primary=top["category"])
        pct_change = cmp["pct_change"]

    if pct_change is not None:
        delta = cmp["delta"]
        direction = "up" if delta >= 0 else "down"
        prior_label = cmp["period_a"]["label"]
        title = f"{top['display']} is your top expense in {label}, {direction} {abs(pct_change):.0f}% from {prior_label}"
        text = (f"You spent ${top['amount']:,.2f} on {top['display']} in {label} — {top_pct:.0f}% of your "
                f"${total:,.2f} total spending, {direction} ${abs(delta):,.2f} from {prior_label}.")
        severity = "high" if abs(pct_change) >= 75 else "medium" if abs(pct_change) >= 35 else "low"
    else:
        title = f"{top['display']} is your top expense in {label}"
        text = (f"You spent ${top['amount']:,.2f} on {top['display']} in {label} — {top_pct:.0f}% of your "
                f"${total:,.2f} total spending.")
        severity = "medium" if top_pct >= 40 else "low"

    return {
        "type": "top_category_vs_prior",
        "title": title,
        "text": text,
        "question": f"What's driving my {top['display']} spending in {label}?",
        "severity": severity,
    }


def _dash_unusual_large_txn(ledger: list[dict], month: str) -> Optional[dict]:
    debits_by_cat: dict[str, list[dict]] = defaultdict(list)
    for t in ledger:
        if t["type"] == TransactionType.debit and not _is_transfer(t["description"]):
            debits_by_cat[t.get("expense_category") or "other"].append(t)

    cat_avg: dict[str, float] = {}
    for cat, items in debits_by_cat.items():
        if len(items) >= 3:
            cat_avg[cat] = sum(t["amount"] for t in items) / len(items)

    best: Optional[tuple] = None
    best_ratio = 2.0
    for t in ledger:
        if t["month"] != month or t["type"] != TransactionType.debit or _is_transfer(t["description"]):
            continue
        cat = t.get("expense_category") or "other"
        avg = cat_avg.get(cat)
        if not avg or avg <= 0:
            continue
        ratio = t["amount"] / avg
        if ratio > best_ratio:
            best_ratio = ratio
            best = (t, avg, cat)

    if not best:
        return None
    t, avg, cat = best
    display = CATEGORY_DISPLAY.get(cat, cat.title())
    merchant = _norm(t["description"]).title() or "Unknown merchant"

    return {
        "type": "unusual_large_transaction",
        "title": f"Unusually large {display} expense: ${t['amount']:,.2f} at {merchant}",
        "text": (f"A ${t['amount']:,.2f} charge at {merchant} on {t['date']} is {best_ratio:.1f}× "
                 f"your average {display} transaction (${avg:,.2f})."),
        "question": f"Tell me more about the ${t['amount']:,.2f} {merchant} charge.",
        "severity": "high" if best_ratio >= 3 else "medium",
    }


def _dash_mom_change(session: Session, user_id: int, month: str, prior_month: Optional[str]) -> Optional[dict]:
    if not prior_month:
        return None
    cmp = compare_periods(session, user_id, {"month": prior_month}, {"month": month})
    pct = cmp["pct_change"]
    if pct is None or abs(pct) < 20:
        return None

    direction = "up" if pct >= 0 else "down"
    change_word = "increase" if pct >= 0 else "decrease"
    label = cmp["period_b"]["label"]
    prior_label = cmp["period_a"]["label"]
    severity = "high" if abs(pct) >= 75 else "medium" if abs(pct) >= 35 else "low"

    return {
        "type": "mom_spending_change",
        "title": f"Overall spending {direction} {abs(pct):.0f}% in {label}",
        "text": (f"You spent ${cmp['period_b']['total']:,.2f} in {label}, compared to "
                 f"${cmp['period_a']['total']:,.2f} in {prior_label} — a {abs(pct):.0f}% {change_word}."),
        "question": f"Why did my spending change so much in {label}?",
        "severity": severity,
    }


def _dash_savings_rate(session: Session, user_id: int, month: str) -> Optional[dict]:
    income = income_summary(session, user_id, {"month": month})["total_income"]
    if income <= 0:
        return None
    spend_info = spending_by_category(session, user_id, {"month": month})
    spend = spend_info["total_spending"]
    label = spend_info["period"]["label"]
    rate = (income - spend) / income * 100

    if rate >= 0:
        title = f"You saved {rate:.0f}% of your income in {label}"
        text = f"You earned ${income:,.2f} and spent ${spend:,.2f} in {label} — a savings rate of {rate:.0f}%."
        severity = "low" if rate >= 20 else "medium"
    else:
        title = f"You spent more than you earned in {label}"
        text = f"You earned ${income:,.2f} but spent ${spend:,.2f} in {label} — {abs(rate):.0f}% over income."
        severity = "high"

    return {
        "type": "savings_rate",
        "title": title,
        "text": text,
        "question": "How can I improve my savings rate?",
        "severity": severity,
    }


def _dash_second_category(session: Session, user_id: int, month: str) -> Optional[dict]:
    """The #2 spending category for the month — a same-period fact (no prior-
    month baseline), so unlike _dash_top_category it's always safe to show
    even while the month is still partial."""
    cur = spending_by_category(session, user_id, {"month": month})
    if len(cur["by_primary"]) < 2:
        return None
    second = cur["by_primary"][1]
    total = cur["total_spending"]
    label = cur["period"]["label"]
    pct = (second["amount"] / total * 100) if total else 0

    return {
        "type": "second_category",
        "title": f"{second['display']} was your second-biggest expense in {label}",
        "text": (f"You spent ${second['amount']:,.2f} on {second['display']} in {label} — "
                 f"{pct:.0f}% of your ${total:,.2f} total spending."),
        "question": f"What's driving my {second['display']} spending in {label}?",
        "severity": "low",
    }


def _dash_avg_transaction(ledger: list[dict], month: str) -> Optional[dict]:
    """Purchase count and average size for the month — a same-period fact,
    safe to show even while the month is still partial."""
    debits = [t for t in ledger if t["month"] == month and is_spending_txn(t)]
    if len(debits) < 2:
        return None
    total = sum(t["amount"] for t in debits)
    avg = total / len(debits)
    label = _fmt(month)

    return {
        "type": "avg_transaction_size",
        "title": f"{len(debits)} purchases averaging ${avg:,.2f} each in {label}",
        "text": (f"You made {len(debits)} purchases in {label} totaling ${total:,.2f} — "
                 f"an average of ${avg:,.2f} per transaction."),
        "question": f"What did I spend the most on in {label}?",
        "severity": "low",
    }


def dashboard_insights(session: Session, user_id: int, job_id: str, limit: int = 3) -> list[dict]:
    """Top proactive insights for the per-import summary page. Computed fresh on
    each call (no persistence) — see AMI-48."""
    job_rows = session.exec(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.import_job_id == job_id)
        .where(Transaction.is_duplicate == False)   # noqa: E712
        .where(Transaction.is_ambiguous == False)    # noqa: E712
    ).all()
    if not job_rows:
        return []
    month = max(r.date.strftime("%Y-%m") for r in job_rows)
    ledger = _load_txns(session, user_id)
    return _insights_for_month(session, user_id, ledger, month, limit)


def latest_ledger_insights(session: Session, user_id: int, limit: int = 3) -> list[dict]:
    """Top proactive insights for the whole-ledger 'View import' page, scoped to
    the most recent month across every import rather than a single job — see
    AMI-48."""
    ledger = _load_txns(session, user_id)
    if not ledger:
        return []
    month = max(t["month"] for t in ledger)
    return _insights_for_month(session, user_id, ledger, month, limit)


def _insights_for_month(session: Session, user_id: int, ledger: list[dict], month: str, limit: int) -> list[dict]:
    all_months = sorted(set(t["month"] for t in ledger))
    idx = all_months.index(month) if month in all_months else -1
    prior_month = all_months[idx - 1] if idx > 0 else None

    # A month with fewer days of data than it actually has (the current
    # calendar month still in progress, or the last imported statement ending
    # mid-month) always looks like a huge swing against a fully-elapsed prior
    # month that isn't real. Drop the cross-month comparison for that case; a
    # same-month metric like savings rate is unaffected.
    month_dates = [t["date"] for t in ledger if t["month"] == month]
    latest_in_month = max(month_dates) if month_dates else None
    is_partial_month = (
        month == date.today().strftime("%Y-%m")
        or (latest_in_month is not None and latest_in_month.day != monthrange(latest_in_month.year, latest_in_month.month)[1])
    )
    comparison_prior_month = None if is_partial_month else prior_month

    candidates = [c for c in (
        _dash_top_category(session, user_id, month, comparison_prior_month),
        _dash_unusual_large_txn(ledger, month),
        _dash_mom_change(session, user_id, month, comparison_prior_month),
        _dash_savings_rate(session, user_id, month),
        _dash_second_category(session, user_id, month),
        _dash_avg_transaction(ledger, month),
    ) if c]

    candidates.sort(key=lambda c: _DASH_SEVERITY_RANK[c["severity"]])
    return [{k: v for k, v in c.items() if k != "severity"} for c in candidates[:limit]]


def generate_insights(session: Session, user_id: int, job_id: str) -> list[Insight]:
    txns = _load_txns(session, user_id)
    if not txns:
        return []

    candidates = _run_detectors(txns, job_id)

    # Deduplicate against existing non-dismissed insights
    existing = session.exec(
        select(Insight)
        .where(Insight.user_id == user_id)
        .where(Insight.is_dismissed == False)  # noqa: E712
    ).all()
    existing_keys = {_dedup_key({"insight_type": i.insight_type, "meta_json": i.meta_json,
                                  "time_period_start": i.time_period_start,
                                  "time_period_end": i.time_period_end}) for i in existing}

    new_insights: list[Insight] = []
    for d in candidates:
        key = _dedup_key(d)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        ins = Insight(**d, user_id=user_id)
        session.add(ins)
        new_insights.append(ins)

    if new_insights:
        session.commit()
        for ins in new_insights:
            session.refresh(ins)

    return new_insights
