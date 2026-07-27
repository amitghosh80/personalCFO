"""Category management endpoints (PRD F3).

Covers the user-facing half of categorization: the taxonomy for dropdowns,
inline + bulk re-categorization (optionally creating a reusable merchant rule),
rule management, the uncategorized review queue, and the uncategorized-threshold
alert. The auto-categorization pipeline itself lives in ``ai_categorizer`` and
``expense_categorizer``.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import get_current_user
from ..models.merchant_rule import MerchantRule
from ..models.transaction import Transaction, TransactionType
from ..models.user import User
from ..services.ai_categorizer import normalize_merchant
from ..services.encryption import decrypt
from ..services.expense_categorizer import (
    TAXONOMY,
    is_spending,
    primary_display,
    subcategory_display,
)

router = APIRouter(prefix="/api/categories", tags=["categories"])

# Uncategorized-alert thresholds (PRD F3): trip if either is exceeded.
_PCT_COUNT_THRESHOLD = 0.10   # >10% of non-income transactions
_PCT_SPEND_THRESHOLD = 0.15   # >15% of spend dollars


class CategoryUpdate(BaseModel):
    primary: str
    subcategory: str
    create_rule: bool = False


class BulkCategoryUpdate(BaseModel):
    transaction_ids: list[int]
    primary: str
    subcategory: str
    create_rule: bool = False


def _validate(primary: str, subcategory: str) -> None:
    if primary not in TAXONOMY or subcategory not in TAXONOMY[primary]:
        raise HTTPException(status_code=422, detail=f"Invalid category: {primary} > {subcategory}")


def _is_uncategorized(t: Transaction) -> bool:
    return (t.expense_category in (None, "other")) or (t.confidence_label == "low")


def _apply_user_category(t: Transaction, primary: str, subcategory: str) -> None:
    t.expense_category = primary
    t.expense_subcategory = subcategory
    t.category_source = "user"
    t.category_confidence = 1.0
    t.confidence_label = "high"


def _maybe_create_rule(session: Session, user_id: int, description: str, primary: str, subcategory: str) -> None:
    pattern = normalize_merchant(description)
    if not pattern:
        return
    existing = session.exec(
        select(MerchantRule)
        .where(MerchantRule.user_id == user_id)
        .where(MerchantRule.merchant_pattern == pattern)
    ).first()
    if existing:
        existing.primary = primary
        existing.subcategory = subcategory
        session.add(existing)
    else:
        session.add(MerchantRule(user_id=user_id, merchant_pattern=pattern, primary=primary, subcategory=subcategory))


@router.get("/taxonomy")
def get_taxonomy():
    """The full two-level taxonomy with display names, for category pickers."""
    return {
        "primaries": [
            {
                "key": p,
                "display": primary_display(p),
                "is_spending": is_spending(p),
                "subcategories": [
                    {"key": s, "display": subcategory_display(s)} for s in subs
                ],
            }
            for p, subs in TAXONOMY.items()
        ]
    }


@router.patch("/transaction/{txn_id}")
def update_category(
    txn_id: int,
    body: CategoryUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _validate(body.primary, body.subcategory)
    txn = session.get(Transaction, txn_id)
    if not txn or txn.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"Transaction {txn_id} not found")

    _apply_user_category(txn, body.primary, body.subcategory)
    session.add(txn)
    if body.create_rule:
        _maybe_create_rule(session, current_user.id, decrypt(txn.description), body.primary, body.subcategory)
    session.commit()
    return {"updated": 1, "rule_created": body.create_rule}


@router.post("/bulk")
def bulk_update_category(
    body: BulkCategoryUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _validate(body.primary, body.subcategory)
    updated = 0
    rule_done = False
    for txn_id in body.transaction_ids:
        txn = session.get(Transaction, txn_id)
        if not txn or txn.user_id != current_user.id:
            raise HTTPException(status_code=404, detail=f"Transaction {txn_id} not found")
        _apply_user_category(txn, body.primary, body.subcategory)
        session.add(txn)
        if body.create_rule and not rule_done:
            _maybe_create_rule(session, current_user.id, decrypt(txn.description), body.primary, body.subcategory)
            rule_done = True
        updated += 1
    session.commit()
    return {"updated": updated, "rule_created": rule_done}


@router.get("/uncategorized")
def uncategorized_queue(
    import_job_id: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Low-confidence / uncategorized debits, sorted by amount descending, for
    the batch-review queue."""
    query = (
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .where(Transaction.transaction_type == TransactionType.debit)
        .where(Transaction.is_duplicate == False)  # noqa: E712
    )
    if import_job_id:
        query = query.where(Transaction.import_job_id == import_job_id)

    rows = [t for t in session.exec(query).all() if _is_uncategorized(t)]
    rows.sort(key=lambda t: t.amount, reverse=True)
    return [
        {
            "id": t.id,
            "date": str(t.date),
            "description": decrypt(t.description),
            "amount": t.amount,
            "expense_category": t.expense_category,
            "confidence_label": t.confidence_label,
        }
        for t in rows
    ]


@router.get("/uncategorized/alert")
def uncategorized_alert(
    import_job_id: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Threshold alert: trips when uncategorized exceeds 10% of non-income
    transactions OR 15% of spend dollars (PRD F3)."""
    query = (
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .where(Transaction.transaction_type == TransactionType.debit)
        .where(Transaction.is_duplicate == False)  # noqa: E712
    )
    if import_job_id:
        query = query.where(Transaction.import_job_id == import_job_id)
    debits = [t for t in session.exec(query).all() if is_spending(t.expense_category or "other")]

    total_count = len(debits)
    total_spend = sum(t.amount for t in debits)
    unc = [t for t in debits if _is_uncategorized(t)]
    unc_count = len(unc)
    unc_spend = sum(t.amount for t in unc)

    pct_count = (unc_count / total_count) if total_count else 0.0
    pct_spend = (unc_spend / total_spend) if total_spend else 0.0
    over = pct_count > _PCT_COUNT_THRESHOLD or pct_spend > _PCT_SPEND_THRESHOLD

    message = None
    if over:
        message = (
            f"${unc_spend:,.0f} ({pct_spend * 100:.0f}% of your spending) is uncategorized "
            f"— this will affect the accuracy of your insights. Review now."
        )
    return {
        "over_threshold": over,
        "uncategorized_count": unc_count,
        "uncategorized_amount": round(unc_spend, 2),
        "total_count": total_count,
        "total_spend": round(total_spend, 2),
        "pct_count": round(pct_count, 4),
        "pct_spend": round(pct_spend, 4),
        "message": message,
    }


@router.get("/rules")
def list_rules(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rules = session.exec(
        select(MerchantRule)
        .where(MerchantRule.user_id == current_user.id)
        .order_by(MerchantRule.created_at.desc())
    ).all()
    return [
        {
            "id": r.id,
            "merchant_pattern": r.merchant_pattern,
            "primary": r.primary,
            "subcategory": r.subcategory,
            "display": f"{primary_display(r.primary)} › {subcategory_display(r.subcategory)}",
            "created_at": str(r.created_at),
            "match_count": r.match_count,
        }
        for r in rules
    ]


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rule = session.get(MerchantRule, rule_id)
    if not rule or rule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    session.delete(rule)
    session.commit()
    return {"deleted": 1}
