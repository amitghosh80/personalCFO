"""Tests for the sandbox demo (Jordan persona): seeding is idempotent, and
every endpoint works with NO Authorization header at all."""
from fastapi.testclient import TestClient
from sqlmodel import select

import app.routers.sandbox as sandbox_router
from app.main import app
from app.database import get_session
from app.models.transaction import Transaction
from app.models.user import User
from app.services.demo_seed import DEMO_USER_EMAIL, ensure_demo_data


def _override_session(session):
    def _dep():
        yield session
    return _dep


def _client(session, monkeypatch):
    monkeypatch.setattr(sandbox_router, "_demo_user_id_cache", None)
    app.dependency_overrides[get_session] = _override_session(session)
    return TestClient(app)


def test_ensure_demo_data_is_idempotent(session):
    ensure_demo_data(session)
    users = session.exec(select(User).where(User.email == DEMO_USER_EMAIL)).all()
    txns_first = session.exec(select(Transaction).where(Transaction.user_id == users[0].id)).all()
    assert len(users) == 1
    assert len(txns_first) > 30  # comfortably past detector thresholds

    ensure_demo_data(session)  # second call must be a no-op
    users_again = session.exec(select(User).where(User.email == DEMO_USER_EMAIL)).all()
    txns_again = session.exec(select(Transaction).where(Transaction.user_id == users_again[0].id)).all()
    assert len(users_again) == 1
    assert len(txns_again) == len(txns_first)


def test_sandbox_financial_profile_requires_no_auth(session, monkeypatch):
    ensure_demo_data(session)
    client = _client(session, monkeypatch)
    try:
        res = client.get("/api/sandbox/financial-profile")
        assert res.status_code == 200
        body = res.json()
        assert body["source"] == "ledger"
        assert body["estimated"] is False
    finally:
        app.dependency_overrides.clear()


def test_sandbox_transactions_requires_no_auth(session, monkeypatch):
    ensure_demo_data(session)
    client = _client(session, monkeypatch)
    try:
        res = client.get("/api/sandbox/transactions")
        assert res.status_code == 200
        body = res.json()
        assert isinstance(body, list)
        assert len(body) > 30
        assert "description" in body[0]
        assert "amount" in body[0]
    finally:
        app.dependency_overrides.clear()


def test_sandbox_insights_requires_no_auth(session, monkeypatch):
    ensure_demo_data(session)
    client = _client(session, monkeypatch)
    try:
        res = client.get("/api/sandbox/insights")
        assert res.status_code == 200
        assert isinstance(res.json()["insights"], list)
    finally:
        app.dependency_overrides.clear()


def test_sandbox_chat_starters_requires_no_auth(session, monkeypatch):
    ensure_demo_data(session)
    client = _client(session, monkeypatch)
    try:
        res = client.get("/api/sandbox/chat/starters")
        assert res.status_code == 200
        assert isinstance(res.json()["questions"], list)
    finally:
        app.dependency_overrides.clear()


def test_sandbox_chat_returns_answer_when_mocked(session, monkeypatch):
    ensure_demo_data(session)

    def fake_answer(sess, user_id, question, history, **kwargs):
        return {"answer": f"echo: {question}", "tools_used": []}

    monkeypatch.setattr(sandbox_router, "answer_question", fake_answer)
    client = _client(session, monkeypatch)
    try:
        res = client.post("/api/sandbox/chat", json={"question": "What's my rent?", "history": []})
        assert res.status_code == 200
        assert res.json()["answer"] == "echo: What's my rent?"
    finally:
        app.dependency_overrides.clear()


def test_sandbox_chat_503_when_key_missing(session, monkeypatch):
    ensure_demo_data(session)

    def boom(*a, **k):
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment")

    monkeypatch.setattr(sandbox_router, "answer_question", boom)
    client = _client(session, monkeypatch)
    try:
        res = client.post("/api/sandbox/chat", json={"question": "hi", "history": []})
        assert res.status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_sandbox_chat_enforces_shared_daily_limit(session, monkeypatch):
    from types import SimpleNamespace

    ensure_demo_data(session)

    def fake_answer(sess, user_id, question, history, **kwargs):
        return {"answer": "ok", "tools_used": []}

    monkeypatch.setattr(sandbox_router, "answer_question", fake_answer)
    monkeypatch.setattr(sandbox_router, "get_settings", lambda: SimpleNamespace(sandbox_chat_daily_limit=2))
    client = _client(session, monkeypatch)
    try:
        for _ in range(2):
            res = client.post("/api/sandbox/chat", json={"question": "hi", "history": []})
            assert res.status_code == 200

        res = client.post("/api/sandbox/chat", json={"question": "hi", "history": []})
        assert res.status_code == 429
    finally:
        app.dependency_overrides.clear()


def test_sandbox_never_requires_authorization_header(session, monkeypatch):
    """Sanity check: no test above ever set an Authorization header, and none
    of them 401'd — confirming this router has no auth dependency."""
    ensure_demo_data(session)
    client = _client(session, monkeypatch)
    try:
        res = client.get("/api/sandbox/financial-profile", headers={})
        assert res.status_code != 401
    finally:
        app.dependency_overrides.clear()
