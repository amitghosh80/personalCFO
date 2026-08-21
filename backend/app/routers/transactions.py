from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import get_current_user
from ..models.import_job import ImportJob, ImportStatus
from ..models.insight import Insight
from ..models.transaction import IncomeCategory, Transaction, TransactionType
from ..models.user import User
from ..services.encryption import decrypt
from ..services.income_classifier import exclude_from_review

router = APIRouter(prefix="/api", tags=["transactions"])


class IncomeConfirmationRequest(BaseModel):
    transaction_ids: list[int]
    confirmed: bool
    income_category: Optional[str] = None  # IncomeCategory value


def _serialize(t: Transaction) -> dict:
    return {
        "id": t.id,
        "import_job_id": t.import_job_id,
        "date": str(t.date),
        "description": decrypt(t.description),
        "amount": t.amount,
        "transaction_type": t.transaction_type,
        "currency": t.currency,
        "institution": t.institution,
        "account_last4": t.account_last4,
        "is_income_candidate": t.is_income_candidate,
        "income_category": t.income_category,
        "income_confirmed": t.income_confirmed,
        "expense_category": t.expense_category,
        "expense_subcategory": t.expense_subcategory,
        "category_source": t.category_source,
        "category_confidence": t.category_confidence,
        "confidence_label": t.confidence_label,
        "is_transfer": t.is_transfer,
        "transfer_status": t.transfer_status,
        "is_ambiguous": t.is_ambiguous,
        "is_duplicate": t.is_duplicate,
    }


@router.get("/transactions")
def list_transactions(
    import_job_id: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    query = select(Transaction).where(Transaction.user_id == current_user.id)
    if import_job_id:
        query = query.where(Transaction.import_job_id == import_job_id)
    query = query.order_by(Transaction.date.desc())
    return [_serialize(t) for t in session.exec(query).all()]


@router.get("/import/{job_id}/income-review")
def get_income_candidates(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _require_job(session, current_user.id, job_id)

    query = (
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .where(Transaction.import_job_id == job_id)
        .where(Transaction.transaction_type == TransactionType.credit)
        .order_by(Transaction.is_income_candidate.desc(), Transaction.amount.desc())
    )

    results = []
    for t in session.exec(query).all():
        row = _serialize(t)
        # Hide non-candidate credits that are definitively not income and add no
        # review value (CC payment confirmations, sign-inverted outflows, metadata).
        if not t.is_income_candidate and exclude_from_review(row["description"]):
            continue
        results.append(row)
    return results


@router.patch("/import/{job_id}/income-review")
def confirm_income(
    job_id: str,
    body: IncomeConfirmationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _require_job(session, current_user.id, job_id)

    updated = 0
    for txn_id in body.transaction_ids:
        txn = session.get(Transaction, txn_id)
        if not txn or txn.user_id != current_user.id or txn.import_job_id != job_id:
            raise HTTPException(status_code=404, detail=f"Transaction {txn_id} not found in job {job_id}")
        txn.income_confirmed = body.confirmed
        if body.income_category:
            txn.income_category = body.income_category
        if body.confirmed:
            txn.is_income_candidate = True
        session.add(txn)
        updated += 1

    session.commit()
    return {"updated": updated}


@router.get("/summary")
def get_ledger_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Whole-ledger spending-by-category-per-month dashboard across all imports
    (the "View import" tab). Same math as the chat tools."""
    from ..services.analytics import monthly_summary
    return monthly_summary(session, current_user.id)


@router.get("/income/review-status")
def income_review_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Whether any auto-detected income is still unreviewed (skipped or not yet
    confirmed/denied), so the app can show a persistent 'income incomplete'
    banner linking back to review (PRD F2 / AMI-24)."""
    rows = session.exec(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .where(Transaction.is_income_candidate == True)   # noqa: E712
        .where(Transaction.income_confirmed == None)        # noqa: E711
        .where(Transaction.is_duplicate == False)           # noqa: E712
        .order_by(Transaction.id.desc())
    ).all()
    return {
        "incomplete": len(rows) > 0,
        "unreviewed_count": len(rows),
        # Link the banner to the most recent import that still needs review.
        "job_id": rows[0].import_job_id if rows else None,
    }


@router.get("/import/{job_id}/summary")
def get_import_summary(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from collections import defaultdict
    from ..services.expense_categorizer import CATEGORY_DISPLAY, is_spending
    from ..services.income_classifier import INCOME_DISPLAY

    job = _require_job(session, current_user.id, job_id)
    txns = session.exec(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .where(Transaction.import_job_id == job_id)
    ).all()

    # Build month-keyed buckets (YYYY-MM)
    buckets: dict[str, dict] = defaultdict(lambda: {"income": 0.0, "expenses": 0.0})
    # month -> category -> total spent
    cat_buckets: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    # month -> income category -> {amount, count}
    income_cat_buckets: dict[str, dict[str, dict]] = defaultdict(
        lambda: defaultdict(lambda: {"amount": 0.0, "count": 0})
    )
    # income category -> {amount, count}, same shape as the chatbot's income_summary tool
    income_by_cat: dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "count": 0})
    has_unreviewed = False
    income_dates: list = []

    for t in txns:
        key = t.date.strftime("%Y-%m")
        if t.transaction_type == TransactionType.debit:
            cat = t.expense_category or "other"
            # Skip money movement (credit-card payments, transfers, investments):
            # counting a CC payment as an expense double-counts the card's own
            # imported purchases. Mirrors the analytics layer's spending filter.
            if not is_spending(cat):
                continue
            buckets[key]["expenses"] += t.amount
            cat_buckets[key][cat] += t.amount
        elif t.transaction_type == TransactionType.credit:
            # Confirmed income, or auto-detected candidate not yet reviewed
            is_income = t.income_confirmed is True or (t.is_income_candidate and t.income_confirmed is None)
            if not is_income:
                continue
            buckets[key]["income"] += t.amount
            if t.income_confirmed is None:
                has_unreviewed = True
            income_cat = t.income_category or "other"
            income_by_cat[income_cat]["amount"] += t.amount
            income_by_cat[income_cat]["count"] += 1
            income_cat_buckets[key][income_cat]["amount"] += t.amount
            income_cat_buckets[key][income_cat]["count"] += 1
            income_dates.append(t.date)

    def _top_categories(month: str) -> list[dict]:
        # Ranked descending, not truncated — the frontend decides how many to show.
        ranked = sorted(cat_buckets[month].items(), key=lambda kv: kv[1], reverse=True)
        return [
            {
                "category": cat,
                "display": CATEGORY_DISPLAY.get(cat, cat.title()),
                "amount": round(amount, 2),
            }
            for cat, amount in ranked
        ]

    def _top_income_categories(month: str) -> list[dict]:
        ranked = sorted(income_cat_buckets[month].items(), key=lambda kv: kv[1]["amount"], reverse=True)
        return [
            {
                "category": cat,
                "display": INCOME_DISPLAY.get(cat, cat.title()),
                "amount": round(v["amount"], 2),
                "count": v["count"],
            }
            for cat, v in ranked
        ]

    monthly_breakdown = [
        {
            "month": month,
            "income": round(data["income"], 2),
            "expenses": round(data["expenses"], 2),
            "net": round(data["income"] - data["expenses"], 2),
            "top_categories": _top_categories(month),
            "income_by_category": _top_income_categories(month),
        }
        for month, data in sorted(buckets.items())
    ]

    income_by_category = [
        {
            "category": cat,
            "display": INCOME_DISPLAY.get(cat, cat.title()),
            "amount": round(v["amount"], 2),
            "count": v["count"],
        }
        for cat, v in sorted(income_by_cat.items(), key=lambda kv: kv[1]["amount"], reverse=True)
    ]

    return {
        "import_job_id": job_id,
        "status": job.status,
        "total_transactions": len(txns),
        "monthly_breakdown": monthly_breakdown,
        "income_includes_unreviewed": has_unreviewed,
        "total_income": round(sum(v["amount"] for v in income_by_cat.values()), 2),
        "income_by_category": income_by_category,
        "income_date_range": {
            "from": str(min(income_dates)) if income_dates else None,
            "to": str(max(income_dates)) if income_dates else None,
        },
        "duplicate_count": sum(1 for t in txns if t.is_duplicate),
        "ambiguous_count": sum(1 for t in txns if t.is_ambiguous),
        "date_range": {
            "from": str(min(t.date for t in txns)) if txns else None,
            "to": str(max(t.date for t in txns)) if txns else None,
        },
    }


@router.get("/import/{job_id}/observations")
def get_proactive_observations(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """The PRD F4 post-import observations (2–3 grounded notes) for the chat
    window. Each observation cites a real number from the user's data."""
    from ..services.insight_engine import proactive_observations
    _require_job(session, current_user.id, job_id)
    return {"observations": proactive_observations(session, current_user.id, job_id)}


@router.delete("/data")
def clear_all_data(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete every transaction, import job, and insight for the
    current user so they can start their ledger over from scratch. Merchant
    categorization rules are left in place since they're a learned preference,
    not import data."""
    txns = session.exec(select(Transaction).where(Transaction.user_id == current_user.id)).all()
    jobs = session.exec(select(ImportJob).where(ImportJob.user_id == current_user.id)).all()
    insights = session.exec(select(Insight).where(Insight.user_id == current_user.id)).all()

    for row in (*txns, *jobs, *insights):
        session.delete(row)
    session.commit()

    return {
        "transactions_deleted": len(txns),
        "import_jobs_deleted": len(jobs),
        "insights_deleted": len(insights),
    }


def _require_job(session: Session, user_id: int, job_id: str) -> ImportJob:
    job = session.get(ImportJob, job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status_code=404, detail=f"Import job {job_id} not found")
    return job
