from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..database import get_session
from ..models.import_job import ImportJob, ImportStatus
from ..models.transaction import IncomeCategory, Transaction, TransactionType
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
        "is_ambiguous": t.is_ambiguous,
        "is_duplicate": t.is_duplicate,
    }


@router.get("/transactions")
def list_transactions(
    import_job_id: Optional[str] = None,
    session: Session = Depends(get_session),
):
    query = select(Transaction)
    if import_job_id:
        query = query.where(Transaction.import_job_id == import_job_id)
    query = query.order_by(Transaction.date.desc())
    return [_serialize(t) for t in session.exec(query).all()]


@router.get("/import/{job_id}/income-review")
def get_income_candidates(job_id: str, session: Session = Depends(get_session)):
    _require_job(session, job_id)

    query = (
        select(Transaction)
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
):
    _require_job(session, job_id)

    updated = 0
    for txn_id in body.transaction_ids:
        txn = session.get(Transaction, txn_id)
        if not txn or txn.import_job_id != job_id:
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


@router.get("/import/{job_id}/summary")
def get_import_summary(job_id: str, session: Session = Depends(get_session)):
    from collections import defaultdict
    from ..services.expense_categorizer import CATEGORY_DISPLAY, ExpenseCategory

    # How many expense categories to surface per month
    TOP_N_CATEGORIES = 5

    job = _require_job(session, job_id)
    txns = session.exec(
        select(Transaction).where(Transaction.import_job_id == job_id)
    ).all()

    # Build month-keyed buckets (YYYY-MM)
    buckets: dict[str, dict] = defaultdict(lambda: {"income": 0.0, "expenses": 0.0})
    # month -> category -> total spent
    cat_buckets: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    has_unreviewed = False

    for t in txns:
        key = t.date.strftime("%Y-%m")
        if t.transaction_type == TransactionType.debit:
            buckets[key]["expenses"] += t.amount
            cat = t.expense_category or ExpenseCategory.other
            cat_buckets[key][cat] += t.amount
        elif t.transaction_type == TransactionType.credit:
            # Confirmed income, or auto-detected candidate not yet reviewed
            if t.income_confirmed is True:
                buckets[key]["income"] += t.amount
            elif t.is_income_candidate and t.income_confirmed is None:
                buckets[key]["income"] += t.amount
                has_unreviewed = True

    def _top_categories(month: str) -> list[dict]:
        ranked = sorted(cat_buckets[month].items(), key=lambda kv: kv[1], reverse=True)
        return [
            {
                "category": cat,
                "display": CATEGORY_DISPLAY.get(cat, cat.title()),
                "amount": round(amount, 2),
            }
            for cat, amount in ranked[:TOP_N_CATEGORIES]
        ]

    monthly_breakdown = [
        {
            "month": month,
            "income": round(data["income"], 2),
            "expenses": round(data["expenses"], 2),
            "net": round(data["income"] - data["expenses"], 2),
            "top_categories": _top_categories(month),
        }
        for month, data in sorted(buckets.items())
    ]

    return {
        "import_job_id": job_id,
        "status": job.status,
        "total_transactions": len(txns),
        "monthly_breakdown": monthly_breakdown,
        "income_includes_unreviewed": has_unreviewed,
        "duplicate_count": sum(1 for t in txns if t.is_duplicate),
        "ambiguous_count": sum(1 for t in txns if t.is_ambiguous),
        "date_range": {
            "from": str(min(t.date for t in txns)) if txns else None,
            "to": str(max(t.date for t in txns)) if txns else None,
        },
    }


def _require_job(session: Session, job_id: str) -> ImportJob:
    job = session.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Import job {job_id} not found")
    return job
