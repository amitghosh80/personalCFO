"""Reset a user to the first-run onboarding state (AMI-66 choice screen).

Deletes everything that would make /app skip straight to the uploader —
transactions, import jobs, insights, and any completed Financial Vitals
interview — and re-arms the vitals-prompt-dismissed flag. Merchant
categorization rules, chat usage, and feedback are left alone, matching the
scope of the in-app "Delete previous imports" action (DELETE /api/data) plus
the one extra piece it intentionally leaves out: the Financial Vitals record.

Usage (from backend/, with the venv active so ENCRYPTION_KEY loads):
    python scripts/reset_user_onboarding.py user@example.com --yes
    python scripts/reset_user_onboarding.py 12 --yes          # by user id

Omit --yes to preview what would be deleted without touching the database.
"""

import argparse
import sys

from sqlmodel import Session, select

from app.database import get_engine
from app.models import FinancialVitals, ImportJob, Insight, Transaction, User


def resolve_user(session: Session, identifier: str) -> User:
    if identifier.isdigit():
        user = session.get(User, int(identifier))
    else:
        user = session.exec(select(User).where(User.email == identifier)).first()
    if user is None:
        raise SystemExit(f"No user found for '{identifier}'")
    return user


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("user", help="Email address or numeric user id")
    parser.add_argument("--yes", action="store_true", help="Actually perform the deletion (default is dry-run)")
    args = parser.parse_args()

    with Session(get_engine()) as session:
        user = resolve_user(session, args.user)

        txns = session.exec(select(Transaction).where(Transaction.user_id == user.id)).all()
        jobs = session.exec(select(ImportJob).where(ImportJob.user_id == user.id)).all()
        insights = session.exec(select(Insight).where(Insight.user_id == user.id)).all()
        vitals = session.exec(select(FinancialVitals).where(FinancialVitals.user_id == user.id)).first()

        print(f"User: {user.email} (id={user.id})")
        print(f"  transactions to delete: {len(txns)}")
        print(f"  import jobs to delete:  {len(jobs)}")
        print(f"  insights to delete:     {len(insights)}")
        print(f"  financial vitals row:   {'yes' if vitals else 'no'}")
        print(f"  vitals_prompt_dismissed_at: {user.vitals_prompt_dismissed_at}")

        if not args.yes:
            print("\nDry run -- no changes made. Re-run with --yes to apply.")
            return

        for row in (*txns, *jobs, *insights):
            session.delete(row)
        if vitals is not None:
            session.delete(vitals)
        if user.vitals_prompt_dismissed_at is not None:
            user.vitals_prompt_dismissed_at = None
            session.add(user)

        session.commit()
        print("\nDone. User will see the first-run choice screen on next /app visit.")


if __name__ == "__main__":
    sys.exit(main())
