---
name: reset-user-onboarding
description: Use this skill when the user asks to "reset a user to new", "refresh <email> as a brand new user", "make <user> go through onboarding again", "reset <email>'s onboarding", or wants an existing account to hit the first-run choice screen (Import a statement / Answer a few questions / See a live example) again as if they'd just signed up. Takes an email or numeric user id and runs the reset script against the local dev database.
compatibility: Local dev environment only — operates directly on backend/personalcfo.db via the backend's Python venv. Requires the backend venv to be set up (see CLAUDE.md).
---

# Reset User Onboarding

Wipes exactly the data that makes `/app` skip the first-run choice screen (AMI-66),
so the target account experiences the three onboarding options again — "Import a
statement", "Answer a few questions", "See a live example" — as if newly signed up.

The underlying script is `backend/scripts/reset_user_onboarding.py`. This skill is
just the safe operating procedure around it.

## Step 1 — Confirm the target and get explicit go-ahead

This is destructive and irreversible (it deletes real transactions/imports/insights
if the target user has any). Before running with `--yes`:

- Identify the user by email or numeric id from what the user asked for. If it's
  ambiguous which account they mean, ask.
- If you have any reason to think this might be a real user's account with real
  imported data (not a throwaway/test account), say what will be deleted and get
  explicit confirmation before running with `--yes` — a dry run first is the way to
  surface this, not a guess.

## Step 2 — Dry run first, always

From `backend/`, with the venv active (`.venv\Scripts\activate` on Windows) so
`ENCRYPTION_KEY` loads per CLAUDE.md:

```powershell
cd backend
.venv\Scripts\activate
$env:PYTHONPATH = "."
python scripts/reset_user_onboarding.py <email-or-user-id>
```

(On bash: `PYTHONPATH=. python scripts/reset_user_onboarding.py <email-or-user-id>`)

Without `--yes` this only prints what it *would* delete:

```
User: someone@example.com (id=12)
  transactions to delete: 22
  import jobs to delete:  2
  insights to delete:     5
  financial vitals row:   yes
  vitals_prompt_dismissed_at: 2026-08-01T00:00:00
```

Read this output back to the user (or reason about it yourself if this was an
explicit, already-scoped request) before proceeding — a nonzero transaction count on
an account you expected to be empty is a sign you have the wrong user.

## Step 3 — Apply it

```powershell
python scripts/reset_user_onboarding.py <email-or-user-id> --yes
```

This deletes, for that user only:
- All `Transaction` rows
- All `ImportJob` rows
- All `Insight` rows
- The `FinancialVitals` row (the completed vitals-interview record), if any
- Clears `vitals_prompt_dismissed_at` back to `None`

It deliberately leaves alone: `MerchantRule` (learned categorization preferences),
`ChatUsage`, and `Feedback` — same scope the in-app "Delete previous imports" button
uses (`DELETE /api/data`), plus the one extra piece that endpoint intentionally
skips: the Financial Vitals record. (`DELETE /api/data` alone is not enough to
re-trigger the choice screen for a user who completed the vitals interview, because
`get_financial_profile` resolves `source: "user_estimate"` from the `FinancialVitals`
row regardless of transaction count — see `backend/app/services/profile_engine.py`.)

## Step 4 — Verify without guessing at the user's password

You almost never have the target user's real login password, so don't try to log in
as them through the UI to check. Verify at the service layer instead, from the same
venv:

```python
from sqlmodel import Session
from app.database import get_engine
from app.services.profile_engine import get_financial_profile
from app.models import User

with Session(get_engine()) as s:
    user = s.get(User, <id>)  # or look up by email
    print(user.vitals_prompt_dismissed_at)      # should be None
    print(get_financial_profile(s, user.id)["source"])  # should be "none"
```

`source == "none"` and `vitals_prompt_dismissed_at is None` together mean the next
`/app` load will show the three-option choice screen (mirrors the exact check in
`frontend/app/(app)/app/page.tsx`'s `decide()`).

## Step 5 — Report back

State plainly what was deleted (counts from Step 2's dry run) and confirm the
verification from Step 4. If the dry run showed zero rows across the board except
possibly the vitals row, say so — it means this was already a near-empty account and
the reset was mostly just clearing the vitals record/dismissal flag.

## Non-goals

- **Not a self-service user feature.** This is a dev/ops script for local testing,
  not something exposed via the app's API or UI. Don't wire it into a router.
- **Doesn't touch auth.** Email, password hash, and Google sign-in linkage are left
  alone — only onboarding-relevant data is cleared.
- **Doesn't reset merchant rules, chat usage, or feedback** — see Step 3. If a future
  ask needs a truly total wipe of everything tied to a user, that's a different,
  broader operation — say so rather than silently expanding scope.
