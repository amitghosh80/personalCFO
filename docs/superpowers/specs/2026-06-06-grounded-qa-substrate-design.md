# Grounded Q&A Substrate + Conversational Chat

**Date:** 2026-06-06
**Status:** Design approved — ready for implementation plan
**Sub-project:** #1 of 3 (the others: proactive insight layer, forecasting & what-if)

## Context

PersonalCFO is being built as a real product for others, not just a personal tool.
The AI wedge is a combination of three surfaces: a **conversational analyst**, a
**proactive CFO/coach**, and **forecasting & planning**. These three surfaces share
~80% of their plumbing — a trustworthy data layer, a retrieval/tool mechanism so the
LLM queries real numbers instead of hallucinating them, and a grounding contract that
keeps the model honest. They differ only in *who initiates* (pull / push / time-shift).

This spec covers **sub-project #1: the shared grounded-Q&A substrate**, delivered with
**conversational chat as its first surface**. Building this slice forces the shared
substrate into existence and ships immediate, demoable value. The proactive and
forecasting surfaces get their own specs later and reuse this substrate.

### Why this slice first

Every one of the three surfaces collapses the moment a number is wrong. For a product
others must trust, accurate understanding is not the wedge — it is the price of
admission. The substrate makes correctness structural: the model never computes or
invents financial figures; it orchestrates deterministic tools that do.

### Current codebase reality (relevant facts)

- **No LLM is wired up yet.** `insight_engine.py` (rule-based, regex + statistics) and
  `expense_categorizer.py` (deterministic Plaid-style taxonomy) are the current
  "AI" features. The only Anthropic touchpoint is an unused `anthropic_api_key` setting.
- **No user/auth model.** `Transaction` rows are keyed by `import_job_id` and
  `source_file_hash`. Because duplicate detection dedupes across files, the
  `transaction` table already accumulates the user's full ledger in one place. A
  single-user, whole-ledger model is therefore sufficient for this slice.
- **Descriptions are Fernet-encrypted at rest** (`Transaction.description: bytes`) and
  decrypted in-process when needed.
- `insight_engine.py` already implements aggregation logic (spending by category,
  recurring detection, cashflow) but bakes it directly into `Insight`-object production.
- `expense_categorizer.py` defines `NON_SPENDING` and `is_spending()` to exclude money
  movement (credit-card payments, transfers, investments) from spending totals.

## Decisions (locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Audience | Real product for others | Differentiation + trust are the goals |
| First slice | Grounded-Q&A substrate + chat surface | Forces shared substrate; immediate value |
| Data-exposure posture | **Aggregate-first** | Minimizes PII off-box, keeps math deterministic, strongest trust story, lower token cost |
| Grounding mechanism | **Curated analytic tools** (typed tool-calling) | Deterministic math, aggregate-first by construction, safe, testable, extensible |
| Ledger scope | Whole `transaction` table (single user) | Auth/multi-tenancy deferred |
| Server state | Stateless; conversation history held client-side and replayed | Simplest correct first slice |
| Chat model | `chat_model` setting, default Claude Sonnet 4.6 | Strong tool orchestration, faster/cheaper than Opus for interactive chat |

## Architecture

The substrate is a **tool-calling loop** between Claude and the existing data layer.
Every number in an answer originates from a deterministic tool — the model orchestrates,
it does not calculate.

```
User question ──► POST /api/chat (question + conversation history)
                      │
                      ▼
        ┌─────────────────────────────┐
        │   Chat orchestrator          │  tool-calling loop:
        │   services/chat_service.py   │  model → tool calls → results → model → answer
        └─────────────────────────────┘
                      │ calls
                      ▼
        ┌─────────────────────────────┐
        │   Analytic tools             │  typed, aggregate-first, deterministic
        │   services/analytics.py      │  shared with insight_engine
        └─────────────────────────────┘
                      │ queries
                      ▼
            transaction table (whole ledger, decrypted in-process)
```

### New backend components

- **`services/analytics.py`** — pure aggregation functions backing the tools. Extracted
  from / shared with `insight_engine.py` so both call the same trustworthy math (one
  source of truth for "spending by category," "recurring sets," "cashflow," etc.).
- **`services/chat_service.py`** — runs the Anthropic tool-calling loop; owns the system
  prompt and the grounding contract; bounds iterations.
- **`routers/chat.py`** — `POST /api/chat`.
- **`config.py`** — add `chat_model` (default `claude-sonnet-4-6`).

### New frontend components

- **`app/chat/page.tsx`** + **`components/ChatInterface.tsx`** — message thread, input
  box, multi-turn within a session.
- **`lib/api.ts`** — `sendChatMessage(question, history)`.
- **`lib/types.ts`** — `ChatMessage`, `ChatResponse` types.

### Targeted refactor (in-scope, justified)

`insight_engine.py` currently couples aggregation to `Insight`-object production. Extract
the pure aggregation helpers into `analytics.py` and have the insight engine call them.
This gives one source of truth for the math that both the rule-based insights and the
chat tools depend on. Scope the refactor to the helpers the tools need — no unrelated
restructuring.

## The Tool Surface

A small, typed, extensible set. Each tool is aggregate-first and returns **structured
data** (not prose). Starting set:

| Tool | Inputs | Returns |
|------|--------|---------|
| `spending_by_category` | period (month / quarter / explicit range), optional primary category | totals per primary + subcategory, txn counts; spending-only (excludes transfers, CC payments, investments) |
| `cashflow_summary` | period | total credits, debits, net, confirmed income, broken out by month |
| `compare_periods` | optional category, period A, period B | side-by-side totals, delta, % change |
| `recurring_charges` | optional category | recurring merchants, cadence, amount, last-seen (reuses recurring detection) |
| `income_summary` | period | confirmed income by category (salary / interest / rental / gig) |
| `search_transactions` | filters: date range, category, amount min/max, merchant substring; **capped result count** | line-item rows — the only tool returning raw descriptions |

### Tool principles

- **Periods resolve server-side.** "last quarter," "May," "this year" → concrete date
  ranges in code; the model never does date arithmetic.
- **Consistent spending definition.** Every aggregate tool excludes non-spending money
  movement via the existing `NON_SPENDING` / `is_spending()`, so "how much did I spend"
  is always honest and never double-counts a CC payment against the card's own imports.
- **One PII door.** `search_transactions` is the only tool that returns raw descriptions,
  and it is bounded by a result cap. Everything else returns aggregates only. This makes
  the aggregate-first guarantee structural, not a matter of prompt discipline.
- **Extensible.** Forecasting / what-if tools (sub-project #3) slot in here later without
  re-architecting the loop.

## Request Flow

One user turn:

1. Frontend sends `{ question, history }` to `POST /api/chat`.
2. `chat_service` calls Claude with the system prompt + tool definitions + history.
3. Claude emits one or more tool calls → orchestrator runs them against `analytics.py`
   → returns structured results to the model.
4. Loop repeats until Claude produces a final answer. **Bounded** at a max iteration
   count (e.g. 5) to prevent runaway loops.
5. Response returns `{ answer, tools_used }`. The UI surfaces which tools/periods backed
   the answer (e.g. *"based on: spending_by_category (Q1 2026)"*) — visible grounding
   builds trust.

## The Grounding Contract (system-prompt rules)

- State **only** numbers returned by tools. Never estimate, never fill gaps from general
  knowledge.
- Always anchor an answer to its **period and scope** ("In Q1 2026, across all imported
  accounts…").
- If the tools cannot answer, **say so plainly** and suggest what data/import would be
  needed — never guess.
- When a figure depends on categorization, attach a light caveat where relevant
  (e.g. *"based on auto-categorization; a few merchants are uncategorized"*). This is the
  seam where category accuracy and user trust connect.
- **Descriptive analysis only** in this slice — no financial / legal / tax advice.
  Recommendations are deliberately sub-project #2's job.

## Error Handling

- **Tool exceptions** return a structured error object to the model (not a crash), so it
  can gracefully report it couldn't compute that figure.
- **Anthropic API failures** surface a clean, retryable message to the UI.
- **Iteration cap reached** → model returns its best grounded answer with a note, rather
  than looping.

## Testing & Evaluation

Two layers, mirroring the existing income-classification regression discipline.

1. **Deterministic unit tests for `analytics.py`** — a fixture DB of known transactions;
   assert each tool returns exact expected aggregates. If the math is right, the chat is
   grounded.
2. **Q&A eval harness** — natural-language questions paired with (a) the tool(s) we
   expect the model to call and (b) the correct numeric answer computed independently
   from the fixture. Run against the real tool-calling loop; assert the model selects
   sane tools and its stated numbers match ground truth. Catches grounding regressions
   (invented numbers, wrong period, ignored tools).

Conventions: fixtures live in `backend/tests/`; the harness is documented in `CLAUDE.md`
and added as a **run-before-commit** trigger for `chat_service.py` and `analytics.py`
(alongside the existing classification-suite trigger).

## Scope Boundaries (explicitly OUT of this slice)

- **Auth / multi-tenancy** — single-user, whole-ledger.
- **Proactive LLM insights** — sub-project #2 (reuses this substrate).
- **Forecasting / what-if** — sub-project #3 (adds projection tools).
- **Chat persistence, response streaming, voice** — later polish pass.
- **Financial / tax / legal advice** — descriptive analysis only here.

## Success Criteria

- A user can ask, in natural language, factual questions about their imported finances
  ("How much did I spend on dining last quarter vs the one before?") and get answers
  whose numbers exactly match independent computation over the same ledger.
- No answer states a financial figure not returned by a tool (verified by the eval).
- Only `search_transactions` ever sends raw descriptions off-box, and it is bounded.
- The aggregation math powering insights and chat is a single shared source of truth.
- The tool surface accepts new tools without changing the orchestration loop.
