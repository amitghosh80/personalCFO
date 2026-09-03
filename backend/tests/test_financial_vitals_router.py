"""Tests for /api/financial-vitals: validation, idempotency, and per-user
isolation for the Financial Vitals Interview (AMI-66)."""
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlmodel import select

from app.main import app
from app.database import get_session
from app.dependencies import get_current_user
from app.models.financial_vitals import FinancialVitals
from tests.conftest import TEST_USER_ID

OTHER_USER_ID = 2

VALID_PAYLOAD = {
    "take_home_pay_monthly": 6000.00,
    "rent_or_mortgage_monthly": 1800.00,
    "car_payment_monthly": 450.00,
    "food_monthly": 800.00,
    "transportation_monthly": 200.00,
    "other_monthly": 3200.00,
}


def _override(session):
    def _dep():
        yield session
    return _dep


def _client(session, user_id=TEST_USER_ID):
    app.dependency_overrides[get_session] = _override(session)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=user_id, email=f"user{user_id}@example.com"
    )
    return TestClient(app)


def test_put_saves_and_returns_normalized_record(session):
    client = _client(session)
    try:
        res = client.put("/api/financial-vitals", json=VALID_PAYLOAD)
        assert res.status_code == 200
        body = res.json()
        assert body["source"] == "user_estimate"
        assert body["take_home_pay_monthly"] == 6000.00
        assert body["rent_or_mortgage_monthly"] == 1800.00
        assert body["car_payment_monthly"] == 450.00
        assert body["food_monthly"] == 800.00
        assert body["transportation_monthly"] == 200.00
        assert body["other_monthly"] == 3200.00
        assert body["monthly_spend_estimate"] == 4200.00
        assert body["completed_at"]
    finally:
        app.dependency_overrides.clear()


def test_put_is_idempotent_and_does_not_duplicate_rows(session):
    client = _client(session)
    try:
        client.put("/api/financial-vitals", json=VALID_PAYLOAD)
        updated = dict(VALID_PAYLOAD, other_monthly=3500.00)
        res = client.put("/api/financial-vitals", json=updated)
        assert res.status_code == 200
        assert res.json()["monthly_spend_estimate"] == 4500.00

        rows = session.exec(
            select(FinancialVitals).where(FinancialVitals.user_id == TEST_USER_ID)
        ).all()
        assert len(rows) == 1
    finally:
        app.dependency_overrides.clear()


def test_put_rejects_zero_take_home_pay(session):
    client = _client(session)
    try:
        res = client.put("/api/financial-vitals", json=dict(VALID_PAYLOAD, take_home_pay_monthly=0))
        assert res.status_code == 422
        assert session.exec(select(FinancialVitals)).first() is None
    finally:
        app.dependency_overrides.clear()


def test_put_rejects_negative_rent(session):
    client = _client(session)
    try:
        res = client.put("/api/financial-vitals", json=dict(VALID_PAYLOAD, rent_or_mortgage_monthly=-1))
        assert res.status_code == 422
        assert session.exec(select(FinancialVitals)).first() is None
    finally:
        app.dependency_overrides.clear()


def test_put_rejects_over_one_million(session):
    client = _client(session)
    try:
        res = client.put("/api/financial-vitals", json=dict(VALID_PAYLOAD, other_monthly=1000001))
        assert res.status_code == 422
        assert session.exec(select(FinancialVitals)).first() is None
    finally:
        app.dependency_overrides.clear()


def test_put_rejects_more_than_two_decimal_places(session):
    client = _client(session)
    try:
        res = client.put("/api/financial-vitals", json=dict(VALID_PAYLOAD, car_payment_monthly=450.123))
        assert res.status_code == 422
        assert session.exec(select(FinancialVitals)).first() is None
    finally:
        app.dependency_overrides.clear()


def test_put_accepts_zero_rent_and_car_payment(session):
    client = _client(session)
    try:
        res = client.put(
            "/api/financial-vitals",
            json=dict(VALID_PAYLOAD, rent_or_mortgage_monthly=0, car_payment_monthly=0),
        )
        assert res.status_code == 200
        assert res.json()["rent_or_mortgage_monthly"] == 0
        assert res.json()["car_payment_monthly"] == 0
    finally:
        app.dependency_overrides.clear()


def test_put_rejects_zero_combined_spend(session):
    """Each of food/transportation/other may individually be zero, but the
    combined total must still be positive (there's no meaningful estimate
    otherwise)."""
    client = _client(session)
    try:
        res = client.put(
            "/api/financial-vitals",
            json=dict(VALID_PAYLOAD, food_monthly=0, transportation_monthly=0, other_monthly=0),
        )
        assert res.status_code == 422
        assert session.exec(select(FinancialVitals)).first() is None
    finally:
        app.dependency_overrides.clear()


def test_put_accepts_zero_food_and_transportation_if_other_covers_spend(session):
    client = _client(session)
    try:
        res = client.put(
            "/api/financial-vitals",
            json=dict(VALID_PAYLOAD, food_monthly=0, transportation_monthly=0, other_monthly=4200.00),
        )
        assert res.status_code == 200
        assert res.json()["monthly_spend_estimate"] == 4200.00
    finally:
        app.dependency_overrides.clear()


def test_get_returns_404_when_no_vitals_saved(session):
    client = _client(session)
    try:
        res = client.get("/api/financial-vitals")
        assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_returns_saved_record(session):
    client = _client(session)
    try:
        client.put("/api/financial-vitals", json=VALID_PAYLOAD)
        res = client.get("/api/financial-vitals")
        assert res.status_code == 200
        assert res.json()["take_home_pay_monthly"] == 6000.00
    finally:
        app.dependency_overrides.clear()


def test_user_cannot_read_another_users_vitals(session):
    client_a = _client(session, user_id=TEST_USER_ID)
    try:
        client_a.put("/api/financial-vitals", json=VALID_PAYLOAD)
    finally:
        app.dependency_overrides.clear()

    client_b = _client(session, user_id=OTHER_USER_ID)
    try:
        res = client_b.get("/api/financial-vitals")
        assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_user_cannot_overwrite_another_users_vitals(session):
    client_a = _client(session, user_id=TEST_USER_ID)
    try:
        client_a.put("/api/financial-vitals", json=VALID_PAYLOAD)
    finally:
        app.dependency_overrides.clear()

    client_b = _client(session, user_id=OTHER_USER_ID)
    try:
        client_b.put("/api/financial-vitals", json=dict(VALID_PAYLOAD, take_home_pay_monthly=9999.00))
    finally:
        app.dependency_overrides.clear()

    row_a = session.exec(
        select(FinancialVitals).where(FinancialVitals.user_id == TEST_USER_ID)
    ).first()
    assert row_a.take_home_pay_monthly_cents == 600000
