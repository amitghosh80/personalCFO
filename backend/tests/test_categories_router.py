"""Tests for the category-management endpoints (PRD F3)."""
from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_session
from app.dependencies import get_current_user
from app.models.merchant_rule import MerchantRule
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


def _debit(session, desc, amount, **kw):
    t = Transaction(
        user_id=TEST_USER_ID,
        import_job_id="j1", date=date(2026, 5, 1), description=encrypt(desc),
        amount=amount, transaction_type=TransactionType.debit, source_file_hash="h", **kw,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def test_taxonomy_lists_primaries(session):
    try:
        res = _client(session).get("/api/categories/taxonomy")
        assert res.status_code == 200
        keys = {p["key"] for p in res.json()["primaries"]}
        assert {"food_and_drink", "housing", "transfer"} <= keys
    finally:
        app.dependency_overrides.clear()


def test_update_category_and_create_rule(session):
    t = _debit(session, "WHOLEFDS MKT 123", 80.0,
               expense_category="other", expense_subcategory="other",
               category_source="fallback", confidence_label="low")
    try:
        client = _client(session)
        res = client.patch(
            f"/api/categories/transaction/{t.id}",
            json={"primary": "food_and_drink", "subcategory": "groceries", "create_rule": True},
        )
        assert res.status_code == 200
        session.refresh(t)
        assert t.expense_category == "food_and_drink"
        assert t.category_source == "user"
        assert t.confidence_label == "high"
        # Rule persisted
        from sqlmodel import select
        assert session.exec(select(MerchantRule)).first() is not None
    finally:
        app.dependency_overrides.clear()


def test_apply_to_merchant_retags_other_existing_transactions(session):
    """AMI feedback: 'apply to merchant' must retag other transactions from the
    same merchant immediately, not just future imports."""
    t1 = _debit(session, "THE HALAL GUYS SLU 014020400000124 SEATTLE WA JASON@THGSEATTLE.COM", 15.0,
                expense_category="utilities", expense_subcategory="other")
    t2 = _debit(session, "THE HALAL GUYS SLU 014020400000124 SEATTLE WA JASON@THGSEATTLE.COM", 12.0,
                expense_category="utilities", expense_subcategory="other")
    try:
        client = _client(session)
        res = client.patch(
            f"/api/categories/transaction/{t1.id}",
            json={"primary": "food_and_drink", "subcategory": "restaurant", "create_rule": True},
        )
        assert res.status_code == 200
        assert res.json()["updated"] == 2
        session.refresh(t1)
        session.refresh(t2)
        assert t1.expense_category == "food_and_drink"
        assert t2.expense_category == "food_and_drink"
        assert t2.category_source == "user"
    finally:
        app.dependency_overrides.clear()


def test_update_rejects_invalid_category(session):
    t = _debit(session, "SOMETHING", 10.0, expense_category="other")
    try:
        res = _client(session).patch(
            f"/api/categories/transaction/{t.id}",
            json={"primary": "nope", "subcategory": "bad"},
        )
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_bulk_update(session):
    a = _debit(session, "AMAZON 1", 30.0, expense_category="other", category_source="fallback")
    b = _debit(session, "AMAZON 2", 40.0, expense_category="other", category_source="fallback")
    try:
        res = _client(session).post(
            "/api/categories/bulk",
            json={"transaction_ids": [a.id, b.id], "primary": "shopping",
                  "subcategory": "electronics", "create_rule": False},
        )
        assert res.status_code == 200
        assert res.json()["updated"] == 2
        session.refresh(a)
        session.refresh(b)
        assert a.expense_category == "shopping" and b.expense_category == "shopping"
    finally:
        app.dependency_overrides.clear()


def test_uncategorized_queue_sorted_desc(session):
    _debit(session, "BIG UNKNOWN", 500.0, expense_category="other",
           category_source="fallback", confidence_label="low")
    _debit(session, "SMALL UNKNOWN", 20.0, expense_category="other",
           category_source="fallback", confidence_label="low")
    _debit(session, "KNOWN", 999.0, expense_category="food_and_drink",
           category_source="rule", confidence_label="high")
    try:
        res = _client(session).get("/api/categories/uncategorized")
        assert res.status_code == 200
        rows = res.json()
        assert [r["amount"] for r in rows] == [500.0, 20.0]  # known one excluded, sorted desc
    finally:
        app.dependency_overrides.clear()


def test_uncategorized_alert_trips_on_spend(session):
    # 1 categorized $100, 1 uncategorized $400 -> 80% of spend uncategorized.
    _debit(session, "KNOWN", 100.0, expense_category="food_and_drink",
           category_source="rule", confidence_label="high")
    _debit(session, "UNKNOWN", 400.0, expense_category="other",
           category_source="fallback", confidence_label="low")
    try:
        res = _client(session).get("/api/categories/uncategorized/alert")
        body = res.json()
        assert body["over_threshold"] is True
        assert body["uncategorized_amount"] == 400.0
        assert body["message"] and "uncategorized" in body["message"]
    finally:
        app.dependency_overrides.clear()


def test_rules_list_and_delete(session):
    session.add(MerchantRule(user_id=TEST_USER_ID, merchant_pattern="WHOLEFDS", primary="food_and_drink",
                             subcategory="groceries"))
    session.commit()
    try:
        client = _client(session)
        res = client.get("/api/categories/rules")
        assert res.status_code == 200
        rule_id = res.json()[0]["id"]
        res = client.delete(f"/api/categories/rules/{rule_id}")
        assert res.status_code == 200
        assert client.get("/api/categories/rules").json() == []
    finally:
        app.dependency_overrides.clear()
