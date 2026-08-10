"""
Reproducible unit-economics / infra-cost model for personalCFO.

Conservative, seed-stage assumptions: slow-start S-curve growth, pessimistic
(overestimated) per-call token usage, and stepped hosting-tier costs. Every
assumption is a named constant below — change a constant and rerun to get an
updated specs/Unit Economics.md table.

Run: python specs/unit_economics_model.py
"""
import math

MONTHS = 18

# --- Growth (logistic S-curve, slow start) ---
REGISTERED_CEILING = 2500   # L: registered-user ceiling reachable in 18mo, seed-stage, no paid acquisition
GROWTH_RATE = 0.35          # k: logistic steepness
MIDPOINT_MONTH = 10         # t0: month of fastest growth
ACTIVE_RATE = 0.55          # MAU / registered (chat is pull-based, not everyone opens the app monthly)

# --- Chat (claude-sonnet-4-6) usage ---
CHAT_ADOPTION = 0.40             # share of MAU asking >=1 AskCFO question this month
QUESTIONS_PER_CHAT_USER = 5      # questions/month for a user who chats at all
API_CALLS_PER_QUESTION = 2       # tool-loop round-trips (typical 1-2, per chat_service.py)
INPUT_TOKENS_PER_CALL = 1600     # system prompt + tool schemas + trimmed history + question
OUTPUT_TOKENS_PER_CALL = 500     # text + tool_use blocks, conservative (max_tokens cap is 2048)
SONNET_INPUT_PER_M = 3.00        # $/M input tokens (assumption, verify against current pricing)
SONNET_OUTPUT_PER_M = 15.00      # $/M output tokens (assumption, verify against current pricing)

# --- Categorization (claude-haiku-4-5) ---
MERCHANTS_PER_NEW_USER = 40      # distinct merchants in a new user's first import
CACHE_HIT_START = 0.20           # MerchantCategoryCache hit rate, month 1 (empty cache)
CACHE_HIT_END = 0.85             # hit rate by month 18 (catalog saturates on common merchants)
HAIKU_BATCH_SIZE = 20            # _BATCH in ai_categorizer.py
HAIKU_INPUT_TOKENS_PER_BATCH = 600
HAIKU_OUTPUT_TOKENS_PER_BATCH = 500
HAIKU_INPUT_PER_M = 0.80
HAIKU_OUTPUT_PER_M = 4.00

# --- Hosting/infra (stepped plan tiers; Railway backend+Postgres, Vercel frontend, Sentry) ---
def hosting_cost(month):
    if month <= 3:
        return 20        # Railway hobby only; Vercel + Sentry free tiers
    if month <= 9:
        return 96         # Railway usage grows ($50) + Vercel Pro ($20) + Sentry Team ($26)
    if month <= 13:
        return 250        # Railway scales with DB size/traffic
    return 400             # Railway scales further as registered users approach ceiling


def registered_users(month):
    return REGISTERED_CEILING / (1 + math.exp(-GROWTH_RATE * (month - MIDPOINT_MONTH)))


def cache_hit_rate(month):
    frac = (month - 1) / (MONTHS - 1)
    return CACHE_HIT_START + (CACHE_HIT_END - CACHE_HIT_START) * frac


def chat_cost_per_call():
    return (INPUT_TOKENS_PER_CALL / 1e6 * SONNET_INPUT_PER_M
            + OUTPUT_TOKENS_PER_CALL / 1e6 * SONNET_OUTPUT_PER_M)


def haiku_cost_per_batch():
    return (HAIKU_INPUT_TOKENS_PER_BATCH / 1e6 * HAIKU_INPUT_PER_M
            + HAIKU_OUTPUT_TOKENS_PER_BATCH / 1e6 * HAIKU_OUTPUT_PER_M)


def main():
    rows = []
    prev_registered = 0.0
    cumulative = 0.0
    cost_per_q = chat_cost_per_call() * API_CALLS_PER_QUESTION
    cost_per_batch = haiku_cost_per_batch()

    for m in range(1, MONTHS + 1):
        registered = registered_users(m)
        new_users = max(registered - prev_registered, 0.0)
        prev_registered = registered
        mau = registered * ACTIVE_RATE

        chat_users = mau * CHAT_ADOPTION
        chat_cost = chat_users * QUESTIONS_PER_CHAT_USER * cost_per_q

        hit_rate = cache_hit_rate(m)
        new_merchants = new_users * MERCHANTS_PER_NEW_USER * (1 - hit_rate)
        categorization_cost = (new_merchants / HAIKU_BATCH_SIZE) * cost_per_batch

        hosting = hosting_cost(m)
        total = chat_cost + categorization_cost + hosting
        cumulative += total
        cost_per_mau = total / mau if mau > 0 else 0.0

        rows.append(dict(
            month=m, registered=registered, new_users=new_users, mau=mau,
            chat_cost=chat_cost, categorization_cost=categorization_cost,
            hosting=hosting, total=total, cumulative=cumulative,
            cost_per_mau=cost_per_mau, hit_rate=hit_rate,
        ))

    header = (f"{'Mo':>3} {'Registered':>10} {'New':>6} {'MAU':>7} "
              f"{'Chat $':>8} {'Categ $':>8} {'Hosting $':>9} {'Total $':>8} "
              f"{'Cum $':>9} {'$/MAU':>7} {'CacheHit':>8}")
    print(header)
    for r in rows:
        print(f"{r['month']:>3} {r['registered']:>10.0f} {r['new_users']:>6.0f} {r['mau']:>7.0f} "
              f"{r['chat_cost']:>8.2f} {r['categorization_cost']:>8.2f} {r['hosting']:>9.2f} "
              f"{r['total']:>8.2f} {r['cumulative']:>9.2f} {r['cost_per_mau']:>7.3f} {r['hit_rate']:>8.2f}")

    print()
    print(f"18-month cumulative infra cost: ${rows[-1]['cumulative']:.2f}")
    print(f"Month 18 MAU: {rows[-1]['mau']:.0f}, month 18 registered: {rows[-1]['registered']:.0f}")
    print(f"Month 18 cost/MAU: ${rows[-1]['cost_per_mau']:.3f}")


if __name__ == "__main__":
    main()
