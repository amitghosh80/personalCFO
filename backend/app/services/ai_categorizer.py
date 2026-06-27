"""AI categorization for the long tail of merchants the rule engine can't place.

Per-import pipeline order: rules (``expense_categorizer``) → user rules
(``MerchantRule``) → this AI fallback. Every distinct merchant is sent to the
model at most once: results are cached in ``MerchantCategoryCache`` keyed by a
normalized merchant string, so re-imports and repeat merchants never re-hit the
model. The model is constrained to the existing taxonomy; anything off-taxonomy
or below the confidence floor stays ``other`` ("Uncategorized") at low confidence.

The Anthropic client is injectable so the pipeline is testable without a key.
"""
import re

from sqlmodel import Session, select

from ..config import get_settings
from ..models.merchant_category import MerchantCategoryCache
from ..models.merchant_rule import MerchantRule
from ..models.transaction import Transaction, TransactionType
from ..services.encryption import decrypt
from ..services.expense_categorizer import TAXONOMY, NON_SPENDING

# Keep batches small enough that the tool-call JSON for the whole batch fits
# comfortably under _MAX_TOKENS — otherwise the response is truncated and the
# items list comes back empty, silently dropping every merchant to "other".
_MAX_TOKENS = 4096
_BATCH = 20
_HIGH, _MEDIUM = 0.90, 0.70

# Categories the AI may assign: spending primaries only ("other" = Uncategorized).
# Money-movement primaries are detected deterministically by rules, never by AI.
_ALLOWED: dict[str, list[str]] = {
    p: subs for p, subs in TAXONOMY.items() if p not in NON_SPENDING
}
_VALID_PAIRS: set[tuple[str, str]] = {
    (p, s) for p, subs in _ALLOWED.items() for s in subs
}


def normalize_merchant(description: str) -> str:
    """Collapse a raw description to a stable merchant key (store numbers/refs
    stripped) so 'STARBUCKS #123' and 'STARBUCKS #456' share one cache entry."""
    d = description.upper()
    d = re.sub(r"\*\S+", " ", d)
    d = re.sub(r"#\d+", " ", d)
    d = re.sub(r"\d{3}[.\-]\d{3}[.\-]\d{4}", " ", d)
    d = re.sub(r"\b\d{4,}\b", " ", d)
    words = [w for w in d.split() if len(w) > 1]
    return " ".join(words[:4]).strip()


def confidence_label(c: float) -> str:
    if c >= _HIGH:
        return "high"
    if c >= _MEDIUM:
        return "medium"
    return "low"


def _build_client():
    import anthropic
    key = get_settings().anthropic_api_key
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment")
    return anthropic.Anthropic(api_key=key)


_SUBMIT_TOOL = {
    "name": "submit_categorizations",
    "description": "Return the category for every merchant you were given.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "merchant": {"type": "string"},
                        "primary": {"type": "string"},
                        "subcategory": {"type": "string"},
                        "confidence": {"type": "number", "description": "0.0–1.0"},
                    },
                    "required": ["merchant", "primary", "subcategory", "confidence"],
                },
            }
        },
        "required": ["items"],
    },
}


def _taxonomy_text() -> str:
    return "\n".join(
        f"- {p}: {', '.join(subs)}" for p, subs in _ALLOWED.items()
    )


_SYSTEM = (
    "You categorize US bank/credit-card transaction merchants into a fixed "
    "two-level taxonomy. Use ONLY these primary categories and their "
    "subcategories — never invent a category:\n\n{taxonomy}\n\n"
    "For each merchant return primary, subcategory, and a confidence 0.0–1.0. "
    "If you cannot tell, use primary 'other', subcategory 'other', and a low "
    "confidence. Call submit_categorizations exactly once with all items."
)


def _classify_merchants(client, model: str, merchants: list[str]) -> dict[str, tuple[str, str, float]]:
    """Ask the model to categorize a batch of merchant strings.

    Returns merchant -> (primary, subcategory, confidence). Off-taxonomy or
    missing answers fall back to ('other', 'other', 0.3)."""
    if not merchants:
        return {}

    listing = "\n".join(f"{i+1}. {m}" for i, m in enumerate(merchants))
    resp = client.messages.create(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM.format(taxonomy=_taxonomy_text()),
        tools=[_SUBMIT_TOOL],
        tool_choice={"type": "tool", "name": "submit_categorizations"},
        messages=[{"role": "user", "content": f"Categorize these merchants:\n{listing}"}],
    )

    items = []
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_categorizations":
            items = block.input.get("items", [])
            break

    out: dict[str, tuple[str, str, float]] = {}
    for it in items:
        merchant = it.get("merchant", "")
        primary = it.get("primary", "other")
        sub = it.get("subcategory", "other")
        try:
            conf = float(it.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        if (primary, sub) not in _VALID_PAIRS:
            primary, sub, conf = "other", "other", min(conf, 0.4)
        out[merchant] = (primary, sub, conf)

    # Any merchant the model omitted → conservative fallback.
    for m in merchants:
        out.setdefault(m, ("other", "other", 0.3))
    return out


def _apply(txn: Transaction, primary: str, sub: str, source: str, conf: float) -> None:
    txn.expense_category = primary
    txn.expense_subcategory = sub
    txn.category_source = source
    txn.category_confidence = round(conf, 3)
    txn.confidence_label = confidence_label(conf)


def categorize_job(session: Session, job_id: str, *, client=None, model: str | None = None) -> dict:
    """Resolve every still-uncategorized debit in a job via user rules, the
    merchant cache, then the AI model. Commits and returns a small summary.

    Safe to call without an API key: rule/cache hits still apply; remaining rows
    stay 'other' at low confidence (surfaced in the uncategorized queue)."""
    rows = session.exec(
        select(Transaction)
        .where(Transaction.import_job_id == job_id)
        .where(Transaction.transaction_type == TransactionType.debit)
        .where(Transaction.is_duplicate == False)        # noqa: E712
        .where(Transaction.category_source == "fallback")
    ).all()
    if not rows:
        return {"resolved_by_rule": 0, "resolved_by_cache": 0, "resolved_by_ai": 0, "uncategorized": 0}

    user_rules = session.exec(select(MerchantRule)).all()

    by_rule = by_cache = by_ai = 0
    needs_ai: dict[str, list[Transaction]] = {}

    for t in rows:
        desc = decrypt(t.description)
        key = normalize_merchant(desc)

        # 1) user correction rules (substring match on the normalized key)
        rule = next((r for r in user_rules if r.merchant_pattern and r.merchant_pattern.upper() in desc.upper()), None)
        if rule:
            _apply(t, rule.primary, rule.subcategory, "user", 1.0)
            rule.match_count += 1
            session.add(rule)
            session.add(t)
            by_rule += 1
            continue

        # 2) merchant cache (a prior confident decision for this merchant)
        cached = session.get(MerchantCategoryCache, key) if key else None
        if cached:
            _apply(t, cached.primary, cached.subcategory, cached.source, 0.95)
            session.add(t)
            by_cache += 1
            continue

        # 3) defer to the AI model, grouped by merchant key
        if key:
            needs_ai.setdefault(key, []).append(t)

    if needs_ai:
        if client is None and get_settings().anthropic_api_key:
            try:
                client = _build_client()
            except Exception:
                client = None
        if client is not None:
            model = model or get_settings().ai_categorizer_model
            keys = list(needs_ai.keys())
            for i in range(0, len(keys), _BATCH):
                batch = keys[i:i + _BATCH]
                results = _classify_merchants(client, model, batch)
                for key in batch:
                    primary, sub, conf = results.get(key, ("other", "other", 0.3))
                    for t in needs_ai[key]:
                        _apply(t, primary, sub, "ai", conf)
                        session.add(t)
                    by_ai += len(needs_ai[key])
                    if (primary, sub) != ("other", "other"):
                        session.merge(MerchantCategoryCache(
                            merchant_key=key, primary=primary, subcategory=sub, source="ai"))
        else:
            # No key: leave as low-confidence Uncategorized for the review queue.
            for txns in needs_ai.values():
                for t in txns:
                    t.category_confidence = 0.0
                    t.confidence_label = "low"
                    session.add(t)

    session.commit()
    uncategorized = sum(
        1 for t in rows
        if (t.expense_category in (None, "other")) or t.confidence_label == "low"
    )
    return {
        "resolved_by_rule": by_rule,
        "resolved_by_cache": by_cache,
        "resolved_by_ai": by_ai,
        "uncategorized": uncategorized,
    }
