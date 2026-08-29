"""Tests for /api/feedback, including the Linear bug-creation side effect."""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_session
from app.dependencies import get_current_user
from app.routers import feedback as feedback_router
from tests.conftest import TEST_USER_ID


def _override(session):
    def _dep():
        yield session
    return _dep


def _client(session):
    app.dependency_overrides[get_session] = _override(session)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=TEST_USER_ID, email="test@example.com"
    )
    return TestClient(app)


def test_submit_feedback_creates_linear_bug(session, monkeypatch):
    calls = []
    monkeypatch.setattr(feedback_router, "create_bug_issue", lambda title, desc: calls.append((title, desc)))
    client = _client(session)
    try:
        res = client.post(
            "/api/feedback",
            data={"category": "general", "message": "The apply-to-merchant button does nothing.", "page_url": "/transactions"},
        )
        assert res.status_code == 200
        assert len(calls) == 1
        title, description = calls[0]
        assert "apply-to-merchant" in title
        assert "**Category:** general" in description
        assert "**Page:** /transactions" in description
        assert "test@example.com" in description
        assert "The apply-to-merchant button does nothing." in description
    finally:
        app.dependency_overrides.clear()


def test_submit_feedback_creates_linear_bug_even_for_feature_category(session, monkeypatch):
    """Every category (general/bug/feature) gets a Bug-labeled Linear issue —
    the app's own category field is unrelated to the Linear label."""
    calls = []
    monkeypatch.setattr(feedback_router, "create_bug_issue", lambda title, desc: calls.append((title, desc)))
    client = _client(session)
    try:
        res = client.post("/api/feedback", data={"category": "feature", "message": "Add dark mode please."})
        assert res.status_code == 200
        assert len(calls) == 1
    finally:
        app.dependency_overrides.clear()


def test_submit_feedback_rejects_invalid_category(session, monkeypatch):
    monkeypatch.setattr(feedback_router, "create_bug_issue", lambda *a, **k: None)
    client = _client(session)
    try:
        res = client.post("/api/feedback", data={"category": "nonsense", "message": "hi"})
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_submit_feedback_rejects_empty_message(session, monkeypatch):
    monkeypatch.setattr(feedback_router, "create_bug_issue", lambda *a, **k: None)
    client = _client(session)
    try:
        res = client.post("/api/feedback", data={"category": "general", "message": "   "})
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_submit_feedback_with_attachment_notes_filename_in_linear_description(session, monkeypatch):
    calls = []
    monkeypatch.setattr(feedback_router, "create_bug_issue", lambda title, desc: calls.append((title, desc)))
    client = _client(session)
    try:
        res = client.post(
            "/api/feedback",
            data={"category": "bug", "message": "Screenshot attached."},
            files={"attachment": ("screenshot.png", b"\x89PNG\r\n\x1a\n\x00\x00", "image/png")},
        )
        assert res.status_code == 200
        _, description = calls[0]
        assert "screenshot.png" in description
    finally:
        app.dependency_overrides.clear()


