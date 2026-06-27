"""Tests for F4 chat wiring: coverage footer, starter questions, observations."""
from fastapi.testclient import TestClient

import app.routers.chat as chat_router
from app.main import app
from app.database import get_session
from app.models.import_job import ImportJob, ImportStatus
from app.models.transaction import TransactionType
from app.services.analytics import data_coverage, starter_questions


def _override(session):
    def _dep():
        yield session
    return _dep


def test_data_coverage_reports_range_and_accounts(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-01-05", amount=100.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink")
    make_txn(day="2026-03-20", amount=50.0, txn_type=TransactionType.debit,
             description="SHELL", expense_category="transportation")
    cov = data_coverage(s)
    assert cov["date_range"] == {"from": "2026-01-05", "to": "2026-03-20"}
    assert cov["transaction_count"] == 2


def test_starter_questions_include_freelance_when_present(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-02-01", amount=2000.0, txn_type=TransactionType.credit,
             description="STRIPE TRANSFER", is_income_candidate=True, income_category="freelance")
    qs = starter_questions(s)
    assert 4 <= len(qs) <= 6
    assert any("freelance" in q.lower() for q in qs)


def test_chat_response_includes_coverage(session, monkeypatch):
    monkeypatch.setattr(
        chat_router, "answer_question",
        lambda *a, **k: {"answer": "ok", "tools_used": []},
    )
    app.dependency_overrides[get_session] = _override(session)
    try:
        res = TestClient(app).post("/api/chat", json={"question": "hi", "history": []})
        assert res.status_code == 200
        assert "coverage" in res.json()
    finally:
        app.dependency_overrides.clear()


def test_starters_endpoint(session):
    app.dependency_overrides[get_session] = _override(session)
    try:
        res = TestClient(app).get("/api/chat/starters")
        assert res.status_code == 200
        assert len(res.json()["questions"]) >= 4
    finally:
        app.dependency_overrides.clear()


def test_observations_endpoint(make_txn):
    s = make_txn.__self_session__
    s.add(ImportJob(id="job1", file_count=1, status=ImportStatus.completed))
    make_txn(day="2026-05-02", amount=6000.0, txn_type=TransactionType.credit,
             description="ADP PAYROLL", is_income_candidate=True,
             income_confirmed=True, income_category="salary")
    make_txn(day="2026-05-05", amount=900.0, txn_type=TransactionType.debit,
             description="WHOLE FOODS", expense_category="food_and_drink")
    s.commit()

    app.dependency_overrides[get_session] = _override(s)
    try:
        res = TestClient(app).get("/api/import/job1/observations")
        assert res.status_code == 200
        obs = res.json()["observations"]
        assert len(obs) >= 1
        assert any(o["kind"] == "summary" for o in obs)
    finally:
        app.dependency_overrides.clear()
