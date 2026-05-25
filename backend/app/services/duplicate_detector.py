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
