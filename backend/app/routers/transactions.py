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
    job = _require_job(session, job_id)

    txns = session.exec(
        select(Transaction).where(Transaction.import_job_id == job_id)
    ).all()

    credits = [t for t in txns if t.transaction_type == TransactionType.credit]
    debits = [t for t in txns if t.transaction_type == TransactionType.debit]
    confirmed_income = [t for t in txns if t.income_confirmed is True]
    unreviewed_income = [t for t in txns if t.is_income_candidate and t.income_confirmed is None]

    return {
        "import_job_id": job_id,
        "status": job.status,
        "total_transactions": len(txns),
        "total_credits": round(sum(t.amount for t in credits), 2),
        "total_debits": round(sum(t.amount for t in debits), 2),
        "net_cash_flow": round(sum(t.amount for t in credits) - sum(t.amount for t in debits), 2),
        "confirmed_income": round(sum(t.amount for t in confirmed_income), 2),
        "confirmed_income_count": len(confirmed_income),
        "unreviewed_income_count": len(unreviewed_income),
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
