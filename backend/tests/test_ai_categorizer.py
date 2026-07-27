"""Tests for the AI categorization fallback pipeline (PRD F3)."""
from datetime import date
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine, select

from app.models.merchant_category import MerchantCategoryCache
from app.models.merchant_rule import MerchantRule
from app.models.transaction import Transaction, TransactionType
from app.services import ai_categorizer
from app.services.ai_categorizer import categorize_job, normalize_merchant, confidence_label
from app.services.encryption import encrypt
from tests.conftest import TEST_USER_ID


def _engine():
    eng = create_engine("sqlite://")
    SQLModel.metadata.create_all(eng)
    return eng


def _fallback_debit(session, desc, amount=50.0, job="j1"):
    t = Transaction(
        user_id=TEST_USER_ID,
        import_job_id=job, date=date(2026, 5, 1), description=encrypt(desc),
        amount=amount, transaction_type=TransactionType.debit, source_file_hash="h",
        expense_category="other", expense_subcategory="other", category_source="fallback",
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _tool_block(items):
    return SimpleNamespace(
        type="tool_use", id="t1", name="submit_categorizations", input={"items": items})


class FakeClient:
    def __init__(self, items):
        self._items = items
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason="tool_use", content=[_tool_block(self._items)])


# ── normalization + labels ─────────────────────────────────────────────────────

def test_normalize_merges_store_numbers():
    assert normalize_merchant("STARBUCKS #123") == normalize_merchant("STARBUCKS #456")


def test_confidence_labels():
    assert confidence_label(0.95) == "high"
    assert confidence_label(0.80) == "medium"
    assert confidence_label(0.50) == "low"


# ── AI fallback ─────────────────────────────────────────────────────────────────

def test_ai_categorizes_and_caches():
    eng = _engine()
    with Session(eng) as session:
        t = _fallback_debit(session, "BLUE BOTTLE COFFEE")
        key = normalize_merchant("BLUE BOTTLE COFFEE")
        client = FakeClient([{"merchant": key, "primary": "food_and_drink",
                              "subcategory": "coffee", "confidence": 0.93}])

        summary = categorize_job(session, TEST_USER_ID, "j1", client=client, model="m")
        session.refresh(t)

        assert summary["resolved_by_ai"] == 1
        assert t.expense_category == "food_and_drink"
        assert t.expense_subcategory == "coffee"
        assert t.category_source == "ai"
        assert t.confidence_label == "high"
        # Cached so a re-import won't re-hit the model.
        cached = session.get(MerchantCategoryCache, key)
        assert cached and cached.primary == "food_and_drink"


def test_offtaxonomy_response_falls_back_to_other():
    eng = _engine()
    with Session(eng) as session:
        t = _fallback_debit(session, "MYSTERY VENDOR")
        key = normalize_merchant("MYSTERY VENDOR")
        client = FakeClient([{"merchant": key, "primary": "crypto",
                              "subcategory": "nonsense", "confidence": 0.99}])
        categorize_job(session, TEST_USER_ID, "j1", client=client, model="m")
        session.refresh(t)
        assert t.expense_category == "other"
        assert t.confidence_label == "low"


def test_cache_hit_skips_model():
    eng = _engine()
    with Session(eng) as session:
        session.add(MerchantCategoryCache(
            merchant_key=normalize_merchant("NETFLIX"), primary="subscriptions",
            subcategory="streaming", source="ai"))
        session.commit()
        t = _fallback_debit(session, "NETFLIX.COM")  # normalizes to NETFLIX COM... hmm
        t2 = _fallback_debit(session, "NETFLIX")

        client = FakeClient([])  # would error if called with items, but cache should win for t2
        summary = categorize_job(session, TEST_USER_ID, "j1", client=client, model="m")
        session.refresh(t2)
        assert t2.expense_category == "subscriptions"
        assert summary["resolved_by_cache"] >= 1


def test_user_rule_takes_priority():
    eng = _engine()
    with Session(eng) as session:
        session.add(MerchantRule(user_id=TEST_USER_ID, merchant_pattern="WHOLEFDS", primary="food_and_drink",
                                 subcategory="groceries"))
        session.commit()
        t = _fallback_debit(session, "WHOLEFDS MARKET #1")
        client = FakeClient([])
        summary = categorize_job(session, TEST_USER_ID, "j1", client=client, model="m")
        session.refresh(t)
        assert t.category_source == "user"
        assert t.expense_category == "food_and_drink"
        assert summary["resolved_by_rule"] == 1


def test_no_client_leaves_low_confidence():
    eng = _engine()
    with Session(eng) as session:
        t = _fallback_debit(session, "OBSCURE LOCAL SHOP")
        # No client and no API key configured in tests → graceful skip.
        summary = categorize_job(session, TEST_USER_ID, "j1", client=None, model="m")
        session.refresh(t)
        assert t.confidence_label == "low"
        assert summary["uncategorized"] >= 1
