"""AMI-24: an app-wide signal that income review is incomplete (some candidate
income was skipped / left unreviewed), so the dashboard can show a persistent
banner linking back to review."""
from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_session
from app.dependencies import get_current_user
from app.models.transaction import Transaction, TransactionType
from app.services.encryption import encrypt
from tests.conftest import TEST_USER_ID


def _override(session):
    def _dep():
        yield session
    return _dep


def _client(session):
    app.dependency_overrides[get_session] = _override(session)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=TEST_USER_ID)
    return TestClient(app)


def _income(session, *, job, confirmed):
    session.add(Transaction(
        user_id=TEST_USER_ID,
        import_job_id=job, date=date(2026, 5, 1), description=encrypt("GUSTO PAYROLL"),
        amount=5000.0, transaction_type=TransactionType.credit, source_file_hash="h",
        is_income_candidate=True, income_confirmed=confirmed,
    ))
    session.commit()


def test_status_incomplete_when_candidate_unreviewed(session):
    _income(session, job="jobX", confirmed=None)  # skipped / not yet reviewed
    body = _client(session).get("/api/income/review-status").json()
    assert body["incomplete"] is True
    assert body["unreviewed_count"] == 1
    assert body["job_id"] == "jobX"


def test_status_clean_when_all_reviewed(session):
    _income(session, job="jobX", confirmed=True)
    body = _client(session).get("/api/income/review-status").json()
    assert body["incomplete"] is False
    assert body["unreviewed_count"] == 0
    assert body["job_id"] is None
