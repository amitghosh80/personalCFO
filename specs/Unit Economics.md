# Unit Economics & Infra Cost Model (v1)

Conservative, seed-stage cost projection for personalCFO's infrastructure — LLM
usage (chat + categorization) and hosting. Scope is **infra cost only**: no
revenue, pricing, CAC, or salaries. Growth assumptions are deliberately
pessimistic (slow-start, no paid acquisition); token/pricing assumptions are
deliberately overestimated (fewer round-trips or cheaper tokens would only
lower these numbers).

The full model is a runnable script — every number below comes from
[`unit_economics_model.py`](./unit_economics_model.py). To test a different
assumption, edit a constant at the top of that file and rerun:

```powershell
python specs/unit_economics_model.py
```

## Assumptions

| Category | Assumption | Why |
|---|---|---|
| Growth | Logistic S-curve, ceiling 2,500 registered users at month 18, midpoint month 10 | Seed-stage, word-of-mouth only, no paid acquisition — slow start, decelerating by month 18 rather than hockey-stick |
| Activation | 55% of registered users are MAU | Chat is pull-based (spec Non-Goal: no push); many registered users only import occasionally |
| Chat adoption | 40% of MAU ask ≥1 AskCFO question in a given month, 5 questions/month if they do | Matches the spec's own lagging target (≥40% of import sessions include a question) applied at monthly grain |
| Chat cost | 2 API round-trips/question (tool-loop typical case), 1,600 input + 500 output tokens/call, Sonnet pricing $3/$15 per M in/out | `chat_service.py` max_iterations=5 but 1-2 rounds is typical; token counts are deliberately generous (system prompt + schemas + trimmed 12-turn history) |
| Categorization | New users bring 40 unique merchants; cache hit rate ramps 20%→85% over 18 months; Haiku batches of 20, pricing $0.80/$4 per M in/out | `MerchantCategoryCache` is shared across users and hit rate should improve as the merchant catalog saturates on common US merchant strings |
| Hosting | Stepped tiers: $20/mo (months 1-3, hobby tiers) → $96/mo (months 4-9, Vercel Pro + Sentry Team + Railway growth) → $250/mo (months 10-13) → $400/mo (months 14-18) | Railway/Vercel/Sentry pricing is tiered, not continuous; steps model plan upgrades as traffic and DB size grow |

**Verify before relying on this for a real budget**: the $/M token prices are
placeholders for `claude-sonnet-4-6` / `claude-haiku-4-5` — confirm current
pricing before using this for fundraising or board materials.

## 18-Month Projection

| Mo | Registered | New users | MAU | Chat $ | Categ. $ | Hosting $ | Total $ | Cumulative $ | $/MAU |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1  | 103   | 103 | 57   | 2.78  | 0.41 | 20  | 23.19  | 23.19   | 0.410 |
| 2  | 143   | 41  | 79   | 3.88  | 0.15 | 20  | 24.03  | 47.22   | 0.305 |
| 3  | 199   | 55  | 109  | 5.37  | 0.20 | 20  | 25.57  | 72.79   | 0.234 |
| 4  | 273   | 74  | 150  | 7.38  | 0.25 | 96  | 103.63 | 176.42  | 0.691 |
| 5  | 370   | 97  | 204  | 10.02 | 0.31 | 96  | 106.33 | 282.75  | 0.522 |
| 6  | 495   | 124 | 272  | 13.38 | 0.38 | 96  | 109.76 | 392.51  | 0.404 |
| 7  | 648   | 154 | 356  | 17.54 | 0.43 | 96  | 113.97 | 506.48  | 0.320 |
| 8  | 830   | 181 | 456  | 22.45 | 0.48 | 96  | 118.93 | 625.41  | 0.261 |
| 9  | 1,033 | 204 | 568  | 27.97 | 0.50 | 96  | 124.47 | 749.87  | 0.219 |
| 10 | 1,250 | 217 | 688  | 33.83 | 0.49 | 250 | 284.31 | 1,034.19 | 0.414 |
| 11 | 1,467 | 217 | 807  | 39.68 | 0.45 | 250 | 290.13 | 1,324.32 | 0.360 |
| 12 | 1,670 | 204 | 919  | 45.20 | 0.38 | 250 | 295.59 | 1,619.91 | 0.322 |
| 13 | 1,852 | 181 | 1,019| 50.11 | 0.31 | 250 | 300.42 | 1,920.33 | 0.295 |
| 14 | 2,005 | 154 | 1,103| 54.27 | 0.23 | 400 | 454.50 | 2,374.83 | 0.412 |
| 15 | 2,130 | 124 | 1,171| 57.63 | 0.16 | 400 | 457.80 | 2,832.62 | 0.391 |
| 16 | 2,227 | 97  | 1,225| 60.27 | 0.11 | 400 | 460.38 | 3,293.00 | 0.376 |
| 17 | 2,301 | 74  | 1,266| 62.28 | 0.07 | 400 | 462.35 | 3,755.35 | 0.365 |
| 18 | 2,357 | 55  | 1,296| 63.77 | 0.04 | 400 | 463.81 | 4,219.16 | 0.358 |

**18-month cumulative infra spend: ~$4,220. Month-18 run rate: ~$464/month at ~1,300 MAU (~$0.36/MAU/month).**

## Takeaways

1. **Hosting tiers dominate, not LLM usage.** Chat + categorization cost together never exceed ~$65/month even at 1,300 MAU — the aggregate-first tool design (analytics.py does the math, the model only narrates) keeps token usage low per question. Cost is a step function driven by Railway/Vercel/Sentry plan upgrades, not usage.
2. **LLM cost per user is a rounding error.** ~$0.05/chatting-user/month for chat, ~$0.01/new-user for categorization. Doubling chat adoption or question volume would not change the conclusion.
3. **Categorization cost decays as the merchant cache saturates** (20%→85% hit rate assumed) — cost per new user drops over time even as new-user count grows, because most merchants a new user imports (Amazon, Starbucks, payroll ACH, etc.) have already been classified by an earlier user.
4. **The real cost lever is hosting-tier timing**, not token pricing. If growth is even slower than modeled, delay the $96 and $250 tier jumps accordingly; if it's this slow-start S-curve is accurate, budget for ~$500/month run rate by month 18.
5. **This is conservative on the growth axis and pessimistic on the cost axis simultaneously** — real infra spend is more likely to be lower than $4,220 over 18 months than higher, absent a paid-acquisition push not modeled here.
