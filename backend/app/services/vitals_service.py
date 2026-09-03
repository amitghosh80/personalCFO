"""Persistence for the Financial Vitals Interview (AMI-66): the user-estimate
inputs that back an estimated Financial Profile before any statement has been
imported. One row per user, always replaced in place."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select

from ..models.financial_vitals import FinancialVitals


def _dollars_to_cents(value: Decimal) -> int:
    return int((value * 100).to_integral_value())


def cents_to_dollars(cents: int) -> float:
    return cents / 100


def total_spend_cents(vitals: FinancialVitals) -> int:
    return vitals.food_monthly_cents + vitals.transportation_monthly_cents + vitals.other_spend_monthly_cents


def get_vitals(session: Session, user_id: int) -> Optional[FinancialVitals]:
    return session.exec(select(FinancialVitals).where(FinancialVitals.user_id == user_id)).first()


def save_vitals(
    session: Session,
    user_id: int,
    take_home_pay_monthly: Decimal,
    rent_or_mortgage_monthly: Decimal,
    car_payment_monthly: Decimal,
    food_monthly: Decimal,
    transportation_monthly: Decimal,
    other_monthly: Decimal,
) -> FinancialVitals:
    """Insert or replace the user's vitals row atomically. Callers must
    validate inputs before calling this — it performs no bounds checking."""
    now = datetime.utcnow()
    record = get_vitals(session, user_id)
    if record is None:
        record = FinancialVitals(user_id=user_id, created_at=now)
        session.add(record)

    record.take_home_pay_monthly_cents = _dollars_to_cents(take_home_pay_monthly)
    record.rent_or_mortgage_monthly_cents = _dollars_to_cents(rent_or_mortgage_monthly)
    record.car_payment_monthly_cents = _dollars_to_cents(car_payment_monthly)
    record.food_monthly_cents = _dollars_to_cents(food_monthly)
    record.transportation_monthly_cents = _dollars_to_cents(transportation_monthly)
    record.other_spend_monthly_cents = _dollars_to_cents(other_monthly)
    record.updated_at = now
    record.completed_at = now

    session.commit()
    session.refresh(record)
    return record
