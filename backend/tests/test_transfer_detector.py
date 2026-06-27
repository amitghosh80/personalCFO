"""Tests for cross-account transfer detection (PRD F1 P0)."""
from datetime import date

from sqlmodel import Session, SQLModel, create_engine

from app.models.transaction import Transaction, TransactionType
from app.services.encryption import encrypt
from app.services.transfer_detector import detect_and_mark


def _engine():
    eng = create_engine("sqlite://")
    SQLModel.metadata.create_all(eng)
    return eng


def _txn(job_id, d, desc, amount, ttype, file_hash, **kw):
    return Transaction(
        import_job_id=job_id, date=d, description=encrypt(desc), amount=amount,
        transaction_type=ttype, source_file_hash=file_hash, **kw,
    )


def _add(session, *txns):
    for t in txns:
        session.add(t)
    session.flush()  # assign ids, mirroring the upload flow


def test_pairs_cross_account_transfer():
    """PRD acceptance: $1,000 'TRANSFER TO SAVINGS' debit (checking) and $1,000
    'TRANSFER FROM CHECKING' credit (savings) are paired and both excluded."""
    eng = _engine()
    with Session(eng) as session:
        debit = _txn("j1", date(2026, 5, 4), "ONLINE TRANSFER TO SAVINGS", 1000.0,
                     TransactionType.debit, "checking.csv")
        credit = _txn("j1", date(2026, 5, 5), "TRANSFER FROM CHECKING", 1000.0,
                      TransactionType.credit, "savings.csv",
                      is_income_candidate=True, income_category="other")
        _add(session, debit, credit)

        summary = detect_and_mark(session, "j1")
        session.commit()
        session.refresh(debit)
        session.refresh(credit)

    assert summary == {"paired": 1, "unconfirmed": 0}
    assert debit.is_transfer and debit.transfer_status == "paired"
    assert debit.transfer_pair_id == credit.id
    assert debit.expense_category == "transfer"
    assert credit.is_transfer and credit.transfer_status == "paired"
    assert credit.transfer_pair_id == debit.id
    # Removed from income consideration
    assert credit.is_income_candidate is False
    assert credit.income_confirmed is False


def test_unpaired_transfer_is_flagged_not_excluded():
    """A transfer-pattern debit with no counterpart is flagged 'unconfirmed',
    not auto-excluded."""
    eng = _engine()
    with Session(eng) as session:
        debit = _txn("j1", date(2026, 5, 4), "WIRE TRANSFER TO ACME", 3000.0,
                     TransactionType.debit, "checking.csv")
        _add(session, debit)
        summary = detect_and_mark(session, "j1")
        session.commit()
        session.refresh(debit)

    assert summary == {"paired": 0, "unconfirmed": 1}
    assert debit.transfer_status == "unconfirmed"
    assert debit.is_transfer is False  # not excluded until the user confirms


def test_same_file_not_paired():
    """Two legs in the same statement aren't a cross-account transfer."""
    eng = _engine()
    with Session(eng) as session:
        debit = _txn("j1", date(2026, 5, 4), "TRANSFER TO SAVINGS", 500.0,
                     TransactionType.debit, "same.csv")
        credit = _txn("j1", date(2026, 5, 4), "TRANSFER FROM CHECKING", 500.0,
                      TransactionType.credit, "same.csv")
        _add(session, debit, credit)
        summary = detect_and_mark(session, "j1")

    assert summary["paired"] == 0


def test_amount_and_date_tolerance_respected():
    """Amounts >$1 apart or >5 business days apart don't pair."""
    eng = _engine()
    with Session(eng) as session:
        debit = _txn("j1", date(2026, 5, 4), "TRANSFER TO SAVINGS", 1000.0,
                     TransactionType.debit, "checking.csv")
        far_credit = _txn("j1", date(2026, 5, 20), "TRANSFER FROM CHECKING", 1000.0,
                          TransactionType.credit, "savings.csv")
        off_amount = _txn("j1", date(2026, 5, 5), "TRANSFER FROM CHECKING", 1002.0,
                          TransactionType.credit, "savings.csv")
        _add(session, debit, far_credit, off_amount)
        summary = detect_and_mark(session, "j1")

    assert summary["paired"] == 0
    assert summary["unconfirmed"] == 1


def test_non_transfer_debit_ignored():
    """An ordinary expense never gets a transfer flag, even with a matching credit."""
    eng = _engine()
    with Session(eng) as session:
        debit = _txn("j1", date(2026, 5, 4), "WHOLE FOODS MARKET", 80.0,
                     TransactionType.debit, "checking.csv")
        credit = _txn("j1", date(2026, 5, 4), "REFUND WHOLE FOODS", 80.0,
                      TransactionType.credit, "card.csv")
        _add(session, debit, credit)
        summary = detect_and_mark(session, "j1")
        session.commit()
        session.refresh(debit)

    assert summary == {"paired": 0, "unconfirmed": 0}
    assert debit.transfer_status is None
