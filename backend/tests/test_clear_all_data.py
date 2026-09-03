"""Tests for DELETE /api/data, including the AMI-66 fix: wiping the ledger
must re-arm the first-run choice screen for a user who dismissed it before
ever completing the Financial Vitals interview."""
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_session
from app.dependencies import get_current_user
from app.models.user import User
from tests.conftest import TEST_USER_ID


def _override(session):
    def _dep():
        yield session
    return _dep


def _make_user(session, dismissed_at=None):
    user = User(
        id=TEST_USER_ID,
        email="user@example.com",
        hashed_password="x",
        vitals_prompt_dismissed_at=dismissed_at,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _client(session, user):
    app.dependency_overrides[get_session] = _override(session)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_clear_all_data_resets_vitals_prompt_dismissal(session):
    user = _make_user(session, dismissed_at=datetime(2026, 1, 1))
    client = _client(session, user)
    try:
        res = client.delete("/api/data")
        assert res.status_code == 200
    finally:
        app.dependency_overrides.clear()

    reloaded = session.get(User, TEST_USER_ID)
    assert reloaded.vitals_prompt_dismissed_at is None


def test_clear_all_data_is_a_noop_when_not_previously_dismissed(session):
    user = _make_user(session, dismissed_at=None)
    client = _client(session, user)
    try:
        res = client.delete("/api/data")
        assert res.status_code == 200
    finally:
        app.dependency_overrides.clear()

    reloaded = session.get(User, TEST_USER_ID)
    assert reloaded.vitals_prompt_dismissed_at is None
