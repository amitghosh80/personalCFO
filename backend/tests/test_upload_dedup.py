"""Regression tests for same-file re-import.

Bug: `is_duplicate()` only flags an identical transaction when it comes from a
*different* source_file_hash, so re-uploading the exact same file (same hash)
slips through and duplicates the whole statement across import jobs. This is
what inflated askCFO's whole-ledger totals vs the per-job categorization view.
"""
import hashlib
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_session
from app.models.transaction import Transaction, TransactionType
from app.services.encryption import encrypt
from app.services.duplicate_detector import file_already_imported


def _override(session):
    def _dep():
        yield session
    return _dep


def _client(session):
    app.dependency_overrides[get_session] = _override(session)
    return TestClient(app)


def test_file_already_imported_detects_existing_hash(session):
    session.add(Transaction(
        import_job_id="j1", date=date(2026, 4, 1), description=encrypt("X"),
        amount=10.0, transaction_type=TransactionType.debit, source_file_hash="abc123",
    ))
    session.commit()
    assert file_already_imported(session, "abc123") is True
    assert file_already_imported(session, "not-seen-before") is False


def test_reupload_of_same_file_is_skipped(session):
    content = b"date,description,amount\n2026-04-01,ALDERWOOD WATER,276.87\n"
    file_hash = hashlib.sha256(content).hexdigest()
    # Simulate the identical file having been imported earlier.
    session.add(Transaction(
        import_job_id="prev", date=date(2026, 4, 1),
        description=encrypt("ALDERWOOD WATER"), amount=276.87,
        transaction_type=TransactionType.debit, source_file_hash=file_hash,
    ))
    session.commit()

    res = _client(session).post(
        "/api/upload",
        files={"files": ("statement.csv", content, "text/csv")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total_transactions"] == 0
    fr = body["file_results"][0]
    assert fr.get("transactions_saved", 0) == 0
    assert "already imported" in fr.get("error", "").lower()
    # The skip must point back to the existing import so the UI isn't a dead end.
    assert fr.get("existing_job_id") == "prev"
    assert body.get("existing_job_id") == "prev"
