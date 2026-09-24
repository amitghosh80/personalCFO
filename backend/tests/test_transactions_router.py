"""Tests for /api/import/{job_id}/summary — specifically the is_partial flag
on monthly_breakdown rows, which must be computed from the user's whole
ledger (every source_file_hash), not just the job being viewed."""
from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_session
from app.dependencies import get_current_user
from app.models.import_job import ImportJob, ImportStatus
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


def _job(session, job_id):
    job = ImportJob(id=job_id, user_id=TEST_USER_ID, status=ImportStatus.completed, file_count=1)
    session.add(job)
    return job


def _txn(job_id, d, source_file_hash, amount=50.0):
    return Transaction(
        user_id=TEST_USER_ID, import_job_id=job_id, date=d,
        description=encrypt("GROCERY STORE"), amount=amount,
        transaction_type=TransactionType.debit, source_file_hash=source_file_hash,
        expense_category="food_and_drink",
    )


def test_is_partial_uses_whole_ledger_not_just_this_job(session):
    # Two separate uploads (different jobs, different files) jointly cover
    # June: job-jun-a has the first half, job-jun-b the second half. Viewing
    # job-jun-a's own summary page must still show June as complete, because
    # completeness is judged across the whole ledger's files, not job-jun-a's
    # own transactions alone.
    _job(session, "job-jun-a")
    _job(session, "job-jun-b")
    session.add(_txn("job-jun-a", date(2026, 6, 1), "hashA"))
    session.add(_txn("job-jun-a", date(2026, 6, 15), "hashA"))
    session.add(_txn("job-jun-b", date(2026, 6, 16), "hashB"))
    session.add(_txn("job-jun-b", date(2026, 6, 30), "hashB"))
    session.commit()
    try:
        res = _client(session).get("/api/import/job-jun-a/summary")
        assert res.status_code == 200
        row = next(r for r in res.json()["monthly_breakdown"] if r["month"] == "2026-06")
        assert row["is_partial"] is False
    finally:
        app.dependency_overrides.clear()


def test_is_partial_true_when_job_file_ends_mid_month_with_no_followup(session):
    _job(session, "job-jul")
    session.add(_txn("job-jul", date(2026, 7, 1), "hashC"))
    session.add(_txn("job-jul", date(2026, 7, 15), "hashC"))
    session.commit()
    try:
        res = _client(session).get("/api/import/job-jul/summary")
        assert res.status_code == 200
        row = next(r for r in res.json()["monthly_breakdown"] if r["month"] == "2026-07")
        assert row["is_partial"] is True
    finally:
        app.dependency_overrides.clear()
