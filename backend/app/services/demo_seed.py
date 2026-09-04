"""Seeds a fictional demo persona ("Jordan, 34") with a realistic multi-month
ledger across one checking account and two credit cards, so an anonymous
visitor can click through the Insight Feed, Financial Profile, and chat
without signing up (see routers/sandbox.py). Entirely synthetic — never
derived from real statements, which are gitignored personal data and must
never be used for a public demo."""
from datetime import date

from sqlmodel import Session, select

from ..models.transaction import Transaction, TransactionType
from ..models.user import User
from ..services.encryption import encrypt

DEMO_USER_EMAIL = "demo@personalcfo.internal"

_IMPORT_JOB_ID = "demo-jordan"
_SOURCE_HASH = "demo-jordan-seed"

_CHECKING = {"institution": "First National Checking", "account_last4": "4821"}
_EVERYDAY_CARD = {"institution": "Chase Visa", "account_last4": "1122"}
_TRAVEL_CARD = {"institution": "Amex Travel Rewards", "account_last4": "3399"}


def _shift_months(d: date, delta: int) -> date:
    month_index = d.month - 1 + delta
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _day(month_start: date, n: int) -> date:
    return month_start.replace(day=min(n, 28))


def _txn(user_id: int, day: date, amount: float, txn_type: TransactionType, description: str, account: dict, **kwargs) -> Transaction:
    return Transaction(
        user_id=user_id,
        import_job_id=_IMPORT_JOB_ID,
        date=day,
        description=encrypt(description),
        amount=round(amount, 2),
        transaction_type=txn_type,
        source_file_hash=_SOURCE_HASH,
        institution=account["institution"],
        account_last4=account["account_last4"],
        **kwargs,
    )


def _build_transactions(user_id: int) -> list[Transaction]:
    today = date.today()
    this_month_start = date(today.year, today.month, 1)
    txns: list[Transaction] = []

    for i in range(5, -1, -1):  # 5 months ago .. current (partial) month
        month_start = _shift_months(this_month_start, -i)

        # ── Checking: biweekly payroll, rent, utilities, card payments ──
        txns.append(_txn(user_id, _day(month_start, 1), 2612.50, TransactionType.credit,
                          "ACME CORP PAYROLL", _CHECKING,
                          is_income_candidate=True, income_confirmed=True, income_category="salary"))
        txns.append(_txn(user_id, _day(month_start, 15), 2612.50, TransactionType.credit,
                          "ACME CORP PAYROLL", _CHECKING,
                          is_income_candidate=True, income_confirmed=True, income_category="salary"))

        txns.append(_txn(user_id, _day(month_start, 1), 1650.00, TransactionType.debit,
                          "MAPLE RIDGE APARTMENTS", _CHECKING,
                          expense_category="housing", expense_subcategory="rent"))
        txns.append(_txn(user_id, _day(month_start, 10), 88.40, TransactionType.debit,
                          "CITY POWER & LIGHT", _CHECKING,
                          expense_category="utilities", expense_subcategory="electric_gas"))
        txns.append(_txn(user_id, _day(month_start, 12), 74.99, TransactionType.debit,
                          "COMCAST XFINITY", _CHECKING,
                          expense_category="utilities", expense_subcategory="internet_cable"))
        txns.append(_txn(user_id, _day(month_start, 20), 350.00, TransactionType.debit,
                          "PAYMENT TO CHASE VISA CARD", _CHECKING,
                          expense_category="credit_card_payment", expense_subcategory="credit_card_payment"))
        txns.append(_txn(user_id, _day(month_start, 22), 220.00, TransactionType.debit,
                          "PAYMENT TO AMEX TRAVEL CARD", _CHECKING,
                          expense_category="credit_card_payment", expense_subcategory="credit_card_payment"))

        if i == 3:
            txns.append(_txn(user_id, _day(month_start, 18), 35.00, TransactionType.debit,
                              "OVERDRAFT FEE", _CHECKING,
                              expense_category="financial", expense_subcategory="bank_fees"))

        # ── Everyday card: groceries, dining, gas, subscriptions ──
        for d_, merchant, amt, cat, sub in [
            (3, "TRADER JOES", 84.20, "food_and_drink", "groceries"),
            (9, "SAFEWAY", 96.10, "food_and_drink", "groceries"),
            (17, "TRADER JOES", 71.55, "food_and_drink", "groceries"),
            (24, "SAFEWAY", 88.30, "food_and_drink", "groceries"),
            (5, "CHIPOTLE", 13.75, "food_and_drink", "restaurant"),
            (8, "STARBUCKS", 6.45, "food_and_drink", "coffee"),
            (14, "LOCAL BISTRO", 42.00, "food_and_drink", "restaurant"),
            (21, "STARBUCKS", 5.95, "food_and_drink", "coffee"),
            (6, "SHELL", 52.10, "transportation", "gas"),
            (19, "CHEVRON", 48.75, "transportation", "gas"),
        ]:
            txns.append(_txn(user_id, _day(month_start, d_), amt, TransactionType.debit,
                              merchant, _EVERYDAY_CARD, expense_category=cat, expense_subcategory=sub))

        txns.append(_txn(user_id, _day(month_start, 1), 17.99, TransactionType.debit,
                          "NETFLIX.COM", _EVERYDAY_CARD,
                          expense_category="subscriptions", expense_subcategory="streaming"))
        txns.append(_txn(user_id, _day(month_start, 2), 11.99, TransactionType.debit,
                          "SPOTIFY", _EVERYDAY_CARD,
                          expense_category="subscriptions", expense_subcategory="streaming"))
        if i <= 2:  # Hulu started 2 months ago — subscription creep
            txns.append(_txn(user_id, _day(month_start, 3), 7.99, TransactionType.debit,
                              "HULU", _EVERYDAY_CARD,
                              expense_category="subscriptions", expense_subcategory="streaming"))

        if i == 1:
            txns.append(_txn(user_id, _day(month_start, 16), 649.00, TransactionType.debit,
                              "BEST BUY", _EVERYDAY_CARD,
                              expense_category="shopping", expense_subcategory="electronics"))
            txns.append(_txn(user_id, _day(month_start, 28), 21.50, TransactionType.debit,
                              "INTEREST CHARGE ON PURCHASES", _EVERYDAY_CARD,
                              expense_category="financial", expense_subcategory="interest_charge"))
        if i == 5:
            txns.append(_txn(user_id, _day(month_start, 5), 95.00, TransactionType.debit,
                              "ANNUAL FEE", _EVERYDAY_CARD,
                              expense_category="financial", expense_subcategory="other"))

        # ── Travel card: Amazon, one trip, movies ──
        for d_, merchant, amt, cat, sub in [
            (4, "AMAZON.COM", 34.20, "shopping", "online_marketplace"),
            (11, "AMAZON.COM", 58.10, "shopping", "online_marketplace"),
            (25, "AMAZON.COM", 22.40, "shopping", "online_marketplace"),
            (13, "MOVIE THEATER", 32.00, "entertainment", "movies_tv"),
        ]:
            txns.append(_txn(user_id, _day(month_start, d_), amt, TransactionType.debit,
                              merchant, _TRAVEL_CARD, expense_category=cat, expense_subcategory=sub))

        if i == 4:
            txns.append(_txn(user_id, _day(month_start, 9), 418.00, TransactionType.debit,
                              "DELTA AIR LINES", _TRAVEL_CARD,
                              expense_category="travel", expense_subcategory="flights"))
            txns.append(_txn(user_id, _day(month_start, 10), 376.00, TransactionType.debit,
                              "AIRBNB", _TRAVEL_CARD,
                              expense_category="travel", expense_subcategory="lodging"))
            txns.append(_txn(user_id, _day(month_start, 11), 11.80, TransactionType.debit,
                              "FOREIGN TRANSACTION FEE", _TRAVEL_CARD,
                              expense_category="financial", expense_subcategory="other"))

    # A transaction can't be dated in the future relative to the seed run.
    return [t for t in txns if t.date <= today]


def ensure_demo_data(session: Session) -> None:
    """Idempotent: creates the demo user and seeds Jordan's ledger once. Safe
    to call on every app startup — a no-op once the demo user has data."""
    user = session.exec(select(User).where(User.email == DEMO_USER_EMAIL)).first()
    if user is None:
        user = User(email=DEMO_USER_EMAIL)
        session.add(user)
        session.commit()
        session.refresh(user)

    existing = session.exec(
        select(Transaction).where(Transaction.user_id == user.id).limit(1)
    ).first()
    if existing is not None:
        return

    for txn in _build_transactions(user.id):
        session.add(txn)
    session.commit()
