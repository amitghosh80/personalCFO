"""Cross-account transfer detection (PRD F1, P0).

After every file in an import job is persisted, pair debit/credit transactions
that represent the user moving money between their *own* accounts, so neither
side inflates spending or income.

Pairing criteria (PRD):
  * amounts within $1.00 of each other,
  * dates within 5 business days,
  * the debit matches an own-account transfer description pattern, and the
    credit either matches one too or is an exact-amount match within 2 business
    days (covers counterpart legs whose wording differs), and
  * the two legs come from different source files (i.e. different accounts).

A paired transfer has both legs marked ``is_transfer`` / ``transfer_status =
"paired"`` and re-categorized so existing analytics exclude them.

A transfer-pattern debit with no counterpart in the job is *not* auto-excluded;
it is flagged ``transfer_status = "unconfirmed"`` so the UI can ask the user
"is this a payment to yourself?" (PRD F1 unpaired-transfer flagging).
"""
import re
from datetime import date, timedelta

from sqlmodel import Session, select

from ..models.transaction import Transaction, TransactionType
from ..services.encryption import decrypt

_AMOUNT_TOLERANCE = 1.00
_MAX_BUSINESS_DAYS = 5

# Own-account transfer wording. Deliberately narrower than analytics.is_transfer:
# we want explicit "to/from my other account" movement, not every ACH/Zelle.
_TRANSFER_RE = re.compile(
    r"online\s+transfer\s+(to|from)|"
    r"transfer\s+to\s+savings|transfer\s+from\s+checking|"
    r"\btransfer\s+(to|from)\b|"
    r"\bto\s+savings\b|\bfrom\s+checking\b|"
    r"\bzelle\s+to\s+self\b|"
    r"\bext\s+trnsfr\b|"
    r"deposit\s+transfer\s+from|withdrawal\s+transfer\s+to",
    re.IGNORECASE,
)


def looks_like_transfer(description: str) -> bool:
    return bool(_TRANSFER_RE.search(description))


def _business_days_between(d1: date, d2: date) -> int:
    if d1 > d2:
        d1, d2 = d2, d1
    days = 0
    cur = d1
    while cur < d2:
        cur += timedelta(days=1)
        if cur.weekday() < 5:  # Mon–Fri
            days += 1
    return days


def _mark_paired(debit: Transaction, credit: Transaction) -> None:
    debit.is_transfer = True
    debit.transfer_status = "paired"
    debit.transfer_pair_id = credit.id
    # Re-categorize so spending_by_category / is_spending_txn exclude it.
    debit.expense_category = "transfer"
    debit.expense_subcategory = "internal"
    debit.category_source = "transfer"

    credit.is_transfer = True
    credit.transfer_status = "paired"
    credit.transfer_pair_id = debit.id
    # Remove from income consideration entirely.
    credit.is_income_candidate = False
    credit.income_confirmed = False
    credit.income_category = None


def detect_and_mark(session: Session, job_id: str) -> dict:
    """Pair cross-account transfers within a job and flag unpaired ones.

    Mutates and ``session.add``s the affected rows but does NOT commit — the
    caller owns the transaction boundary. Returns ``{"paired", "unconfirmed"}``.
    """
    rows = session.exec(
        select(Transaction)
        .where(Transaction.import_job_id == job_id)
        .where(Transaction.is_duplicate == False)  # noqa: E712
    ).all()

    entries = [(t, decrypt(t.description)) for t in rows]
    debits = [(t, d) for t, d in entries if t.transaction_type == TransactionType.debit]
    credits = [(t, d) for t, d in entries if t.transaction_type == TransactionType.credit]

    used_credit_ids: set[int] = set()
    paired = 0
    unconfirmed = 0

    for dt, ddesc in debits:
        if not looks_like_transfer(ddesc):
            continue

        match = None
        for ct, cdesc in credits:
            if ct.id in used_credit_ids:
                continue
            if ct.source_file_hash == dt.source_file_hash:
                continue  # same statement → not a cross-account transfer
            if abs(ct.amount - dt.amount) > _AMOUNT_TOLERANCE:
                continue
            bdays = _business_days_between(dt.date, ct.date)
            if bdays > _MAX_BUSINESS_DAYS:
                continue
            credit_ok = looks_like_transfer(cdesc) or (
                abs(ct.amount - dt.amount) < 0.01 and bdays <= 2
            )
            if not credit_ok:
                continue
            match = ct
            break

        if match is not None:
            used_credit_ids.add(match.id)
            _mark_paired(dt, match)
            session.add(dt)
            session.add(match)
            paired += 1
        else:
            dt.transfer_status = "unconfirmed"
            session.add(dt)
            unconfirmed += 1

    return {"paired": paired, "unconfirmed": unconfirmed}
