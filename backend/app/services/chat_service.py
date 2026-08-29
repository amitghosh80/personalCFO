"""Conversational layer: a bounded Claude tool-use loop over the analytics tools.

The model never states a financial figure it didn't get from a tool. All tools
are aggregate-first; search_transactions is the only one returning raw
descriptions and it is row-capped. The Anthropic client is injectable for tests.
"""
import json
from datetime import date

from sqlmodel import Session

from ..config import get_settings
from .analytics import TOOLS, data_coverage, dispatch_tool, uncategorized_status

SYSTEM_PROMPT = """You are the analyst inside a personal finance app. You answer \
questions about the user's imported bank and card transactions.

Rules you must follow:
- State only numbers returned by the tools. Never estimate, guess, or use outside \
knowledge to fill gaps. If you didn't get a number from a tool, you don't have it.
- Always anchor an answer to its period and scope, e.g. "In Q1 2026, across all \
imported accounts...".
- "Spending" excludes money movement (transfers, credit-card payments, \
investments). Use spending_by_category for spending questions and cashflow_summary \
for money-in-vs-out questions.
- For questions about "subscriptions" specifically, use search_transactions or \
spending_by_category with primary="subscriptions" — the app's own subscription \
category — so the answer reflects what's actually tagged as a subscription. Do \
NOT use recurring_charges for this: it detects statistically-recurring merchants \
across every category (loan installments, rent, utilities included) and is not \
scoped to the subscriptions category, so it will surface non-subscription bills. \
Reserve recurring_charges for when the user explicitly asks to find recurring or \
hidden/undetected charges across all spending.
- The imported data only covers the date range stated above. If a question uses a \
relative period ("last month", "this month", "this year") that falls partly or \
wholly outside that range, do not just report $0 — say the requested period is \
outside the imported data and answer for the covered range instead (e.g. the most \
recent month or quarter that has data). When the period is ambiguous, prefer \
querying the covered range over a relative preset.
- If the tools cannot answer, say so plainly and suggest what the user could import \
or confirm. Do not invent an answer.
- If asked which statement, billing cycle, or account page a transaction came from: \
the app never stores full statements or PDFs, only the parsed transaction fields \
(date, description, amount, category) — by design, for security and privacy. Say \
so plainly, and point the user to their bank/card's own portal or statement for \
that detail. Do not suggest re-importing or connecting the account, since the app \
already discards the source document after parsing and importing it again would \
not add statement-level detail.
- When a figure depends on auto-categorization or unconfirmed income, add a brief \
caveat (e.g. "based on auto-categorization").
- Give descriptive analysis only. Do not give financial, tax, or legal advice.
Be concise and use plain dollar figures."""


def _coverage_line(session: Session, user_id: int) -> str:
    """One-line description of the imported data window for the system prompt, so
    the model never answers a relative-period question against data it can't see."""
    cov = data_coverage(session, user_id)
    dr = cov.get("date_range")
    if not dr:
        return "No transactions have been imported yet."
    accounts = cov.get("account_count", 0)
    acct = f"{accounts} account" + ("s" if accounts != 1 else "")
    return (
        f"The imported data covers {dr['from']} to {dr['to']} "
        f"across {acct} ({cov.get('transaction_count', 0)} transactions). "
        f"There is no data outside this date range."
    )

_MAX_TOKENS = 2048
# Full history is resent on every call, so cost grows with conversation length
# unless bounded. Keep only the most recent turns; older context is dropped.
_MAX_HISTORY_MESSAGES = 20  # ~10 user/assistant exchanges


def _build_client():
    import anthropic
    key = get_settings().anthropic_api_key
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment")
    return anthropic.Anthropic(api_key=key)


_FOLLOWUP_SYSTEM_PROMPT = """Given one question-and-answer exchange from a personal \
finance chatbot, suggest 2-3 short, natural follow-up questions the user might ask \
next, specific to what was just discussed. Keep each under 12 words. Respond with \
ONLY a JSON array of strings — no prose, no markdown fences."""


def _generate_followups(client, model: str, question: str, answer: str) -> list[str]:
    """Best-effort contextual follow-ups for the answer just given. Failures
    (including a scripted test client running out of responses) never surface —
    an empty list just means no follow-up chips are shown."""
    if not answer:
        return []
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=200,
            system=_FOLLOWUP_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Q: {question}\nA: {answer}"}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(f) for f in parsed if str(f).strip()][:3]
    except Exception:
        pass
    return []


def answer_question(
    session: Session,
    user_id: int,
    question: str,
    history: list[dict] | None = None,
    *,
    client=None,
    model: str | None = None,
    today: date | None = None,
    max_iterations: int = 5,
    suppress_data_warning: bool = False,
) -> dict:
    """Run the tool-use loop and return {'answer', 'tools_used'}.

    `history` is a list of {'role','content'} dicts with string content.
    `client` and `model` are injectable; default to the configured Anthropic client.
    """
    client = client or _build_client()
    model = model or get_settings().chat_model
    effective_today = today or date.today()
    system = (
        f"Today's date is {effective_today.isoformat()}.\n"
        f"{_coverage_line(session, user_id)}\n\n{SYSTEM_PROMPT}"
    )

    trimmed_history = (history or [])[-_MAX_HISTORY_MESSAGES:]
    messages = list(trimmed_history) + [{"role": "user", "content": question}]
    tools_used: list[dict] = []
    last_text = ""

    def _finalize(answer: str, generate_followups: bool = True) -> dict:
        """Prepend a data-quality warning when the answer leans on spending tools
        and too much spending is still uncategorized to trust (AMI-33)."""
        used_spending_tool = any(
            t["name"] in ("spending_by_category", "cashflow_summary") for t in tools_used
        )
        if not suppress_data_warning and used_spending_tool:
            st = uncategorized_status(session, user_id)
            if st["over"]:
                pct = round(st["pct_count"] * 100)
                warn = (
                    f"⚠️ Your spending data may be incomplete — {pct}% of transactions "
                    f"are uncategorized. Review them for more accurate answers."
                )
                answer = f"{warn}\n\n{answer}" if answer else warn
        followups = _generate_followups(client, model, question, answer) if generate_followups else []
        return {"answer": answer, "tools_used": tools_used, "followups": followups}

    for _ in range(max_iterations):
        resp = client.messages.create(
            model=model,
            max_tokens=_MAX_TOKENS,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        assistant_content = []
        tool_uses = []
        text_parts = []
        for block in resp.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
                text_parts.append(block.text)
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use", "id": block.id,
                    "name": block.name, "input": block.input,
                })
                tool_uses.append(block)

        if assistant_content:
            messages.append({"role": "assistant", "content": assistant_content})
        if text_parts:
            last_text = "\n".join(text_parts).strip()

        if resp.stop_reason != "tool_use":
            return _finalize(last_text)

        tool_results = []
        for tu in tool_uses:
            result = dispatch_tool(session, user_id, tu.name, tu.input, today=effective_today)
            tools_used.append({"name": tu.name, "input": tu.input, "result": result})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result, default=str),
            })
        messages.append({"role": "user", "content": tool_results})

    # Iteration cap reached.
    fallback = "I couldn't fully resolve that with the available data tools."
    return _finalize((last_text + "\n\n" + fallback).strip() if last_text else fallback, generate_followups=False)
