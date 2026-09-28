# PersonalCFO — Conference Demo Script (Tuesday)

Persona: "Jordan" — salaried + freelance consultant, one checking account and
two credit cards. Statements cover **May–August 2026** (4 full months, no
partial-month data, so nothing trips the partial-month warning).

Files (in this folder), upload all three together in the Upload screen:
- `chase_checking_may_aug_2026.csv` — Chase checking
- `chase_visa_may_aug_2026.csv` — Chase Visa (everyday spending)
- `amex_travel_may_aug_2026.csv` — Amex Travel Rewards card

Verified against the actual parser/classifier before this doc was written:
all three are detected correctly (Chase/Chase/American Express), signs
resolve correctly, and all 12 income credits (8 payroll + 4 consulting fee)
classify automatically as salary / freelance.

Built-in story beats, so you don't have to remember what's "supposed" to
happen:
- **Payroll raise**: $2,500 → $2,700 per paycheck starting July (income +7%).
- **Freelance income**: steady $600/mo "CONSULTING FEE" — unlocks the
  freelance-income starter question.
- **Subscription creep**: Netflix + Spotify (May) → add Hulu (June) → add
  Disney+ (August). Recurring-charge and subscription-creep detectors both
  fire.
- **A caught duplicate charge**: Spotify billed twice on Aug 2 & 3 — a
  believable "oops, my card got double-charged" moment for the insight feed.
- **Dining creep**: $64.90 (May) → $144.80 (Aug), +123% over the period.
- **One big one-time purchase**: Best Buy $649 in August.
- **A real trip**: Delta $380 + Airbnb $340 + FX fee $9.60 in July (~$730),
  which also dents that month's savings rate.

---

## 0. Before you go on stage

- Log in fresh (or use an account with no existing transactions) so the
  Income Review screen isn't cluttered with old data.
- Have the 3 CSVs ready in one folder on the desktop/USB for fast drag-drop.
- Do one dry run within 24 hours of the talk — if conference wifi is bad,
  consider pre-uploading and just re-loading the Summary/Insights/AskCFO
  screens live instead of the raw upload.

## 1. Open — the problem (30 sec)

> "Everyone's finances live in five different bank exports nobody reads.
> PersonalCFO turns raw statements into answers you can actually ask
> follow-up questions about."

## 2. Live upload (2 min)

1. Drag all three CSVs onto the upload screen at once.
2. Call out as it processes: *"It's not just importing rows — it's detecting
   which bank each file came from and correcting the sign convention. Amex
   marks a purchase as positive; Chase marks it negative. You never have to
   know that."*
3. Land on **Income Review**: 12 credits are queued (2 payroll + 1 consulting
   fee, per month × 4 months), pre-classified as salary/freelance. Confirm a
   couple on stage to show the human-in-the-loop step, then bulk-confirm the
   rest.
4. Land on **Summary**: point at total credits/debits/net cash flow for the
   period.

## 3. Insight Feed (2 min)

Walk the feed and narrate whichever of these surface (order may vary):
- **Income change**: paycheck went from $2,500 to $2,700 (+8%) starting July.
- **Subscription creep**: 2 → 3 → 4 recurring streaming subscriptions over
  the period, now $55.95/mo total.
- **Duplicate charge**: Spotify charged twice on Aug 2 and Aug 3.
- **Category spike**: dining or shopping (Best Buy $649) called out for
  August.
- **Cashflow / savings rate**: healthy ~40–50% savings rate, with a dip in
  July from the trip.

## 4. AskCFO — the main event (3–4 min)

Ask these in order. Expected ballpark answers are based on the exact
seeded data (the app will phrase them naturally, numbers should match):

| Ask | Expected ballpark answer |
|---|---|
| "What did I spend the most on last month?" | Housing/rent (**$1,650**) is the single biggest line; food & drink (~**$533**) and shopping (~**$751**, driven by the Best Buy purchase) are close behind. |
| "How much did I spend on dining last month?" | **~$144.80** in August, up from **$64.90** in May — more than doubled over the period. |
| "What subscriptions am I paying for?" | Netflix $15.99, Spotify $10.99, Hulu $7.99, Disney+ $9.99 — **~$55.95/mo**, plus flags the duplicate Spotify charge. |
| "Did I save money last month?" | Yes — income **$6,000** vs. spend **~$3,446** in August, roughly a **42–43% savings rate**. |
| "Is my dining spending trending up?" / "Compare my dining spend this month to last month" | July → August dining up **~16%** ($125.10 → $144.80); May → August up **~123%**. |
| "How much freelance income did I earn this year?" | **~$2,400** ($600/mo × 4 months) — this chip only appears because freelance income was detected, good moment to point out the UI adapts to the data. |
| "Did I get a raise?" / "How has my income changed?" | Paycheck rose from $2,500 to $2,700 per pay period starting July — about **+7–8%** month over month income. |
| "What did I spend on my trip in July?" | Delta $380 + Airbnb $340 + foreign transaction fee $9.60 = **~$729.60**. |
| "Show me all my Amazon purchases" | Raw list of the 8 Amazon.com line items on the Amex card, May–August. |
| "Is there anything unusual in my spending?" | Should surface the duplicate Spotify charge and/or the one-off Best Buy purchase. |

Close with a freeform ask to show it's not scripted: *"What should I cut
back on?"* — a good note to end on since the model should point at dining
or the subscription creep, which you've already primed the audience to
recognize from the insight feed.

## 5. Close (30 sec)

> "That's the whole loop: drop in statements, review income in one screen,
> get insights automatically, and just ask the rest."

---

### If something looks off live

- If a number is slightly different from the table above, don't sweat it —
  the categorization/rounding may differ marginally from this manual
  precomputation; the *directions* (rent is biggest, dining doubled, income
  rose ~7%, ~40%+ savings rate, trip cost ~$730) are what matter and were
  computed directly from the CSVs.
- If upload fails on conference wifi, the files are small (under 60 rows
  total) — retry once, then fall back to the pre-seeded sandbox persona
  (`demo@personalcfo.internal`) for the Insights/AskCFO portion only.
