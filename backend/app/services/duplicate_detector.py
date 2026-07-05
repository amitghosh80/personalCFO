from datetime import date as DateType
from sqlmodel import Session, select
from ..models.transaction import Transaction, TransactionType


def is_duplicate(
    session: Session,
    txn_date: DateType,
    amount: float,
    txn_type: TransactionType,
    source_file_hash: str,
) -> bool:
    """True if an identical transaction (date + amount + type) exists from a different source file."""
    statement = (
        select(Transaction)
        .where(Transaction.date == txn_date)
        .where(Transaction.amount == amount)
        .where(Transaction.transaction_type == txn_type)
        .where(Transaction.source_file_hash != source_file_hash)
    )
    return session.exec(statement).first() is not None


def file_already_imported(session: Session, source_file_hash: str) -> bool:
    """True if any transaction from this exact file (by content hash) is already
    persisted.

    Guards against re-uploading an identical file: `is_duplicate()` only flags
    identical transactions from a *different* source_file_hash, so a same-file
    re-import would otherwise slip through and duplicate the whole statement
    across import jobs.
    """
    statement = select(Transaction).where(
        Transaction.source_file_hash == source_file_hash
    )
    return session.exec(statement).first() is not None


def existing_job_for_file(session: Session, source_file_hash: str) -> str | None:
    """The import job this file's transactions already live in (most recent),
    so a skipped re-upload can route the user to their existing import summary
    instead of dead-ending."""
    row = session.exec(
        select(Transaction)
        .where(Transaction.source_file_hash == source_file_hash)
        .order_by(Transaction.id.desc())
    ).first()
    return row.import_job_id if row else None
