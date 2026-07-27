from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.routers.chat as chat_router
from app.main import app
from app.database import get_session
from app.dependencies import get_current_user
from tests.conftest import TEST_USER_ID


def _override_session(session):
    def _dep():
        yield session
    return _dep


def _apply_overrides(session):
    app.dependency_overrides[get_session] = _override_session(session)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=TEST_USER_ID)


def test_chat_endpoint_returns_answer(session, monkeypatch):
    def fake_answer(sess, user_id, question, history, **kwargs):
        return {"answer": f"echo: {question}", "tools_used": [{"name": "cashflow_summary", "input": {}}]}

    monkeypatch.setattr(chat_router, "answer_question", fake_answer)
    _apply_overrides(session)
    try:
        client = TestClient(app)
        res = client.post("/api/chat", json={"question": "hi", "history": []})
        assert res.status_code == 200
        body = res.json()
        assert body["answer"] == "echo: hi"
        assert body["tools_used"][0]["name"] == "cashflow_summary"
    finally:
        app.dependency_overrides.clear()


def test_chat_endpoint_503_when_key_missing(session, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment")

    monkeypatch.setattr(chat_router, "answer_question", boom)
    _apply_overrides(session)
    try:
        client = TestClient(app)
        res = client.post("/api/chat", json={"question": "hi", "history": []})
        assert res.status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_chat_endpoint_502_on_upstream_error(session, monkeypatch):
    def boom(*a, **k):
        raise ValueError("model exploded")

    monkeypatch.setattr(chat_router, "answer_question", boom)
    _apply_overrides(session)
    try:
        client = TestClient(app)
        res = client.post("/api/chat", json={"question": "hi", "history": []})
        assert res.status_code == 502
    finally:
        app.dependency_overrides.clear()
