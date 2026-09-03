# Feature Spec: Financial Vitals Interview

## Summary

Give first-time signed-in users a useful alternative to statement upload: a two-minute interview that creates an estimated Financial Profile immediately. The user can answer the interview or import statements in parallel. The existing Financial Profile surface displays the estimates with a persistent `Estimated` treatment until real ledger data is available.

The interview is not a separate dashboard or a throwaway onboarding result. It is an alternate input source for the existing evergreen Financial Profile described in `specs/Financial Profile.md`.

## Problem

Today, a newly signed-in user is sent to Import Statements and the only meaningful action is uploading a bank or credit-card statement. Uploading financial documents is a high-friction first action. Users who are curious about the product but not ready to find and upload a statement have no way to reach the product's core value.

## Goals

- Let a new signed-in user see a populated Financial Profile without uploading a statement.
- Make the first value moment take no more than two minutes for a user with four approximate numbers.
- Preserve the existing import flow as a first-class parallel path.
- Make every estimate visibly and repeatedly distinguishable from statement-derived numbers.
- Turn the gap between an estimate and actual data into a specific import prompt.
- Persist the answers so the profile remains available on later sessions and can be edited.

## Success Metrics

Instrument these events and report them by signup cohort:

- `vitals_prompt_viewed`: percentage of newly signed-in users shown the choice screen.
- `vitals_started`: percentage of prompted users who start the interview.
- `vitals_completed`: percentage of starters who save all four answers.
- `profile_estimated_viewed`: percentage of completers who view the estimated Profile.
- `statement_import_started`: percentage of new signups who begin an upload within 7 days.
- `statement_import_completed`: percentage of new signups who complete an upload within 7 days.
- `estimated_to_import_7d`: percentage of interview completers who complete an upload within 7 days.

Initial product targets, to be validated after launch:

- At least 35% of new signed-in users start either import or interview from the first-run choice screen.
- At least 60% of interview starters complete it.
- Interview completers have a higher 7-day import conversion rate than users who see upload-only onboarding. Use a randomized holdout of 10% of eligible users for this comparison if the existing analytics infrastructure supports it.

These targets are measurement targets, not reasons to block launch if instrumentation is working.

## Users And Eligibility

The experience is for authenticated users whose account has no persisted vitals and no non-duplicate ledger transactions.

- Show the first-run choice screen on `/app` for eligible users.
- Do not show it again after the user completes or explicitly dismisses it. Persist dismissal.
- If the user has already imported statements, go directly to the current import page.
- If the user starts the interview and leaves before saving, show the choice screen again on the next visit. Do not persist partial answers.
- If the user has saved vitals but has not imported statements, route them to the estimated Profile on later visits, with a clear `Import statements` CTA.
- The import action must remain available from the choice screen, the estimated Profile, and the main navigation.

## First-Run Choice Screen

Replace the eligible user's upload-only first-run presentation with two equal, non-blocking choices:

1. **Import a statement**
   - Existing uploader and supported-file behavior remain unchanged.
   - Supporting copy: `See what your money is actually doing.`

2. **Answer a few questions**
   - Supporting copy: `Get a rough Financial Profile in about 2 minutes.`

The screen must not imply that the interview is required before import. The user can switch paths at any time.

Recommended primary copy:

> See your financial picture today
> Import a statement for real numbers, or answer four quick questions to get an estimate now.

The screen should include a privacy reassurance that answers are used to calculate the user's profile and can be edited later. Do not request bank credentials or statement data in the interview.

## Interview Flow

Use four steps or one clearly segmented form. Each step has one question, an amount input, a short explanation, and Back/Continue controls. Show progress as `1 of 4`, etc.

Questions:

1. **What is your monthly take-home pay?**
2. **How much do you pay for rent or mortgage each month?**
3. **How much is your car payment each month?**
4. **About how much do you spend each month in total?**

Input rules:

- Currency input accepts positive values with up to two decimal places.
- Rent/mortgage and car payment accept `0` and offer a visible `I do not have this` shortcut that sets zero.
- Take-home pay and total monthly spend must be greater than zero.
- Reject negative values, malformed currency, values above `$1,000,000` per month, and values with more than two decimal places.
- Normalize and store amounts as decimal cents, not floating-point values.
- Do not ask for annual income, pay cadence, household size, location, debt balance, assets, or category-level spending in this MVP.
- Answers are user estimates, not verified financial facts. Avoid financial advice or normative copy.

Completion behavior:

- The final action is `See my estimated profile` and saves the four answers atomically.
- On success, navigate to `/profile`.
- On network or server failure, keep the entered values in local component state, show an actionable error, and allow retry. Do not show a partially saved profile.
- Back navigation preserves entered values during the current session.
- Browser refresh during an incomplete interview may lose unsaved values; no draft persistence is required for MVP.

## Estimated Metric Definitions

The estimate uses only the four saved inputs. All values are monthly estimates.

| Profile metric | Estimated value | Display rule |
|---|---:|---|
| Committed Monthly Spend | `rent_or_mortgage + car_payment` | Monthly and annualized values; label as estimated commitment floor |
| Average Monthly Burn | `monthly_spend` | Show as estimated monthly burn |
| Average Monthly Income | `take_home_pay` | Show as estimated take-home income, not gross income |
| Fixed vs. Discretionary | Fixed = committed spend; discretionary = `max(monthly_spend - fixed, 0)` | Show percentages against estimated spend |
| Savings Rate | `(take_home_pay - monthly_spend) / take_home_pay` | Show the signed result; do not floor negative savings |

Edge-case rules:

- If committed spend exceeds guessed monthly spend, fixed spend remains the committed amount and discretionary spend is zero. Fixed percentage may exceed 100%; cap the displayed fixed percentage at 100% and show the underlying relationship in the narrative: `Your commitments are higher than your total-spend estimate.`
- Savings rate may be negative and is displayed as negative.
- Round currency values to cents for API payloads and to whole dollars in headlines, matching the existing Profile UI.
- Round displayed percentages to the nearest whole percent. Keep the precise decimal in the API payload.
- The estimate has no transaction IDs, merchant breakdown, cadence, confidence score, or confidence label. The source is `user_estimate` and uncertainty is communicated by the `Estimated` label.
- Fees & Interest remains `insufficient_data` until ledger data exists. Do not infer fees from the interview.

## Source Precedence And Transition To Real Data

The Financial Profile response must include a top-level source:

```json
{
  "source": "user_estimate",
  "estimated": true
}
```

Allowed source values are `user_estimate` and `ledger`.

- Before the first successful statement import, return the saved estimate as the Profile's five populated metrics and retain the existing insufficient-data state for fees/interest.
- After the first successful import creates at least one usable ledger transaction, return the existing ledger-computed Profile for all metrics. Set `source` to `ledger` and `estimated` to `false`.
- Do not blend user estimates with ledger values.
- Do not delete the saved interview answers when ledger data becomes available. They are retained for audit/edit history and possible future comparison, but are not shown as active metrics after transition.
- If all imports are later deleted and no usable ledger remains, fall back to the saved estimate and set `estimated` back to `true`.
- Import completion is the transition trigger; merely selecting a file does not transition the Profile.

## Estimated Profile Experience

Add a dedicated authenticated `/profile` route that renders the existing `FinancialProfile` component or a shared page-level wrapper around it. Add `Profile` to the authenticated navigation. Keep the existing Profile module on summary/import views unless the implementer finds a strong reason to remove it; both surfaces must use the same API and source treatment.

When `estimated=true`:

- Place a prominent but calm `Estimated` badge in the Financial Profile header.
- Header description: `Based on your estimates. Import one statement to replace these with real numbers.`
- Include the exact CTA: `Import a statement to see your real numbers` linking to `/app`.
- Each populated tile carries an `Estimated` indicator or inherits it from the clearly visible Profile header; do not rely on color alone.
- Replace transaction drill-down affordances with an `How this was estimated` detail showing the relevant inputs and formula.
- Show an edit action, `Update my estimates`, linking to `/profile/vitals` or reopening the interview. It must update the same persisted record.
- Do not display fake confidence scores or fake supporting transactions.

When `estimated=false`, preserve the existing Financial Profile UI, confidence labels, transaction drill-downs, and ledger narratives described in `specs/Financial Profile.md`.

## API Contract

### Save or Replace Vitals

```http
PUT /api/financial-vitals
Authorization: Bearer <token>
Content-Type: application/json
```

Request:

```json
{
  "take_home_pay_monthly": 6000.00,
  "rent_or_mortgage_monthly": 1800.00,
  "car_payment_monthly": 450.00,
  "monthly_spend_estimate": 4200.00
}
```

Response: `200` with the normalized saved record and `source: "user_estimate"`.

Validation failures return `422` with field-level errors. The endpoint must be idempotent: repeated requests replace the authenticated user's current answers and do not create multiple records.

### Get Vitals

```http
GET /api/financial-vitals
Authorization: Bearer <token>
```

Return `200` with the saved record, or `404` when the user has not completed the interview. Never return another user's record.

### Financial Profile Extension

Extend `GET /api/financial-profile` with:

```json
{
  "source": "user_estimate",
  "estimated": true,
  "vitals_completed_at": "2026-09-01T12:00:00Z",
  "metrics": {}
}
```

Existing ledger responses must remain valid for current consumers. For an account with neither ledger data nor saved vitals, retain the current insufficient-data response and add `source: "none"`, `estimated: false`.

## Data Model And Migration

Add a one-to-one `financial_vitals` table owned by `user_id`:

- `id` integer primary key
- `user_id` integer, unique, non-null, indexed, foreign key to `app_user.id`
- `take_home_pay_monthly_cents` integer, non-null
- `rent_or_mortgage_monthly_cents` integer, non-null
- `car_payment_monthly_cents` integer, non-null
- `monthly_spend_estimate_cents` integer, non-null
- `created_at` datetime, non-null
- `updated_at` datetime, non-null
- `completed_at` datetime, non-null

Use a dialect-agnostic Alembic migration. Do not alter the existing `Transaction` schema. Register the model wherever the application imports SQLModel models for metadata/migrations.

Do not store calculated metrics. The profile engine calculates them from the current vitals row on request, just as ledger metrics are calculated from the current ledger.

## Backend Implementation Notes

- Add a `financial_vitals` model, router, service, request/response schemas as needed by existing project conventions, and API client functions/types in the frontend.
- Add an estimated-profile path in `services/profile_engine.py` that returns the same metric keys expected by `FinancialProfile.tsx`.
- Keep the existing ledger computation unchanged when a usable ledger exists.
- Define “usable ledger” using the same `load_ledger` filtering already used by the profile engine: non-duplicate, non-ambiguous transactions. An empty ledger must not transition the source.
- Use the authenticated user dependency on every vitals endpoint.
- Save validation must be atomic and must not create a row on invalid input.
- Instrument server-side events only if an existing analytics/event mechanism is present. Otherwise instrument the frontend funnel events with a small typed helper and document the event sink/TODO rather than adding a new analytics platform in this feature.

## Frontend Implementation Notes

- Keep the first-run eligibility check fast and non-blocking. A failed eligibility/profile request must not prevent the existing import page from rendering.
- Extract a shared `FinancialProfileView` state for ledger and estimated sources rather than duplicating the six-tile layout.
- Add responsive layout for the choice screen and interview on mobile. Amount inputs must not require horizontal scrolling.
- Use the existing auth/API patterns in `frontend/lib/api.ts` and types in `frontend/lib/types.ts`.
- Add loading, validation, retry, empty, and unauthorized states. A silent failure is not acceptable for saving vitals.
- Keep the upload CTA visible on the estimated Profile at desktop and mobile widths.

## Acceptance Criteria

1. A new authenticated user with no imports sees both `Import a statement` and `Answer a few questions` on `/app`.
2. Choosing import preserves the current uploader behavior and does not require completing the interview.
3. A user can complete the four-question interview with valid values, save once, and land on `/profile`.
4. Invalid, negative, zero-required, over-limit, and over-precision values are rejected with field-level feedback and no persisted partial record.
5. The estimated Profile computes all five specified metrics using the formulas in this document and leaves fees/interest insufficient until statements exist.
6. The Profile visibly says `Estimated`, explains that the values are guesses, and offers `Import a statement to see your real numbers`.
7. Estimated tiles do not expose fake transaction links, confidence labels, or ledger-derived narratives.
8. Editing answers replaces the existing vitals record and immediately recomputes the estimated Profile.
9. A successful usable statement import switches the Profile to ledger source without blending values, and the estimated banner disappears.
10. Deleting all imports switches the Profile back to the saved estimate.
11. User A cannot read or modify User B's vitals through any endpoint.
12. Repeating the save request does not create duplicate vitals rows.
13. Existing ledger Profile tests and existing import tests continue to pass.
14. Funnel events are emitted for choice view, path selection, interview start, validation error, completion, estimated Profile view, and import CTA click.

## Test Plan

Backend:

- Unit-test each estimate formula, including zero commitments, commitments greater than spend, negative savings, rounding, and maximum bounds.
- Test PUT validation and idempotency.
- Test GET/PUT authentication and user isolation.
- Test profile source selection for no data, vitals only, ledger only, ledger plus vitals, and deleted ledger with retained vitals.
- Test that estimated metrics use no transaction IDs and fees remain insufficient.
- Run the existing profile, analytics, auth, and import test suites.

Frontend:

- Test eligible and ineligible first-run routing.
- Test both parallel choices and navigation back to import.
- Test all four interview fields, zero shortcuts, validation errors, retry, and success navigation.
- Test estimated header/badge/CTA/formula details and edit flow.
- Test transition from estimated to ledger response and the no-data state.
- Test mobile layout at the existing supported breakpoints.

Manual smoke test:

1. Create a new account.
2. Start the interview, enter `$6,000`, `$1,800`, `$450`, and `$4,200`.
3. Confirm the Profile shows `$2,250` committed monthly spend, `$4,200` burn, `$6,000` income, approximately `46%` savings rate, and approximately `54%` fixed / `46%` discretionary.
4. Return to import, upload a valid statement, and confirm the Profile becomes ledger-derived.
5. Delete imports and confirm the saved estimate returns.

## Rollout And Rollback

- Ship behind a server- or client-configurable feature flag for new-user onboarding.
- Enable for internal accounts first, then a small percentage of new signups.
- Rollback is disabling the flag; existing saved vitals remain harmless and can be ignored by the old UI.
- The migration is additive. Do not drop the table or data as part of a UI rollback.

## Non-Goals

- No bank connection or credential collection.
- No statement parsing changes.
- No gross-income, tax, debt, assets, net-worth, runway, budget, or forecasting model.
- No automatic categorization of the guessed monthly spend.
- No blending or reconciliation between guesses and ledger data in this feature.
- No financial advice, recommendations, peer benchmarks, or behavioral judgments.
- No new analytics vendor or event warehouse unless an existing project mechanism requires it.

## Open Implementation Decisions

The implementer may choose the exact component split, route nesting, schema library, and event transport, provided the API behavior, formulas, source precedence, persistence, and acceptance criteria remain unchanged. If `/profile` conflicts with an existing route discovered during implementation, preserve the dedicated Profile destination and update links consistently rather than collapsing the feature back into upload-only onboarding.
