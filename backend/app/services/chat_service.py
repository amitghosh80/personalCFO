"""Conversational layer: a bounded Claude tool-use loop over the analytics tools.

The model never states a financial figure it didn't get from a tool. All tools
are aggregate-first; search_transactions is the only one returning raw
descriptions and it is row-capped. The Anthropic client is injectable for tests.
"""
import json
from datetime import date

from sqlmodel import Session

from ..config import get_settings
from .analytics import TOOLS, data_coverage, dispatch_tool

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
- The imported data only covers the date range stated above. If a question uses a \
relative period ("last month", "this month", "this year") that falls partly or \
wholly outside that range, do not just report $0 — say the requested period is \
outside the imported data and answer for the covered range instead (e.g. the most \
recent month or quarter that has data). When the period is ambiguous, prefer \
querying the covered range over a relative preset.
- If the tools cannot answer, say so plainly and suggest what the user could import \
or confirm. Do not invent an answer.
- When a figure depends on auto-categorization or unconfirmed income, add a brief \
caveat (e.g. "based on auto-categorization").
- Give descriptive analysis only. Do not give financial, tax, or legal advice.
Be concise and use plain dollar figures."""


def _coverage_line(session: Session) -> str:
    """One-line description of the imported data window for the system prompt, so
    the model never answers a relative-period question against data it can't see."""
    cov = data_coverage(session)
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


def _build_client():
    import anthropic
    key = get_settings().anthropic_api_key
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment")
    return anthropic.Anthropic(api_key=key)


def answer_question(
    session: Session,
    question: str,
    history: list[dict] | None = None,
    *,
    client=None,
    model: str | None = None,
    today: date | None = None,
    max_iterations: int = 5,
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
        f"{_coverage_line(session)}\n\n{SYSTEM_PROMPT}"
    )

    messages = list(history or []) + [{"role": "user", "content": question}]
    tools_used: list[dict] = []
    last_text = ""

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
            return {"answer": last_text, "tools_used": tools_used}

        tool_results = []
        for tu in tool_uses:
            tools_used.append({"name": tu.name, "input": tu.input})
            result = dispatch_tool(session, tu.name, tu.input, today=effective_today)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result, default=str),
            })
        messages.append({"role": "user", "content": tool_results})

    # Iteration cap reached.
    fallback = "I couldn't fully resolve that with the available data tools."
    return {"answer": (last_text + "\n\n" + fallback).strip() if last_text else fallback,
            "tools_used": tools_used}
