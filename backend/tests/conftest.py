"""Shared pytest fixtures: an isolated in-memory ledger and a row factory.

ENCRYPTION_KEY must be set before app.services.encryption is imported, so we
generate one and clear the settings cache at module import time.
"""
import os
from datetime import date as _date

import pytest
from cryptography.fernet import Fernet

# Must run before any app import that reads settings / builds Fernet.
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from sqlmodel import SQLModel, Session, create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.models.transaction import Transaction, TransactionType  # noqa: E402
from app.services.encryption import encrypt  # noqa: E402

get_settings.cache_clear()  # pick up the ENCRYPTION_KEY we just set


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",  # in-memory
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared connection so TestClient worker
                               # threads see the same in-memory DB/tables
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_txn(
    session,
    *,
    day: str,
    amount: float,
    txn_type: TransactionType,
    description: str,
    expense_category: str | None = None,
    expense_subcategory: str | None = None,
    is_income_candidate: bool = False,
    income_confirmed: bool | None = None,
    income_category: str | None = None,
    is_duplicate: bool = False,
    is_ambiguous: bool = False,
) -> Transaction:
    t = Transaction(
        import_job_id="job1",
        date=_date.fromisoformat(day),
        description=encrypt(description),
        amount=amount,
        transaction_type=txn_type,
        source_file_hash="hash1",
        expense_category=expense_category,
        expense_subcategory=expense_subcategory,
        is_income_candidate=is_income_candidate,
        income_confirmed=income_confirmed,
        income_category=income_category,
        is_duplicate=is_duplicate,
        is_ambiguous=is_ambiguous,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


@pytest.fixture
def make_txn(session):
    def _factory(**kwargs):
        return _make_txn(session, **kwargs)
    _factory.__self_session__ = session
    return _factory
