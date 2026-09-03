from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator, model_validator
from sqlmodel import Session

from ..database import get_session
from ..dependencies import get_current_user
from ..models.financial_vitals import FinancialVitals
from ..models.user import User
from ..services.vitals_service import cents_to_dollars, get_vitals, save_vitals, total_spend_cents

router = APIRouter(prefix="/api", tags=["financial-vitals"])

_MAX_MONTHLY_AMOUNT = Decimal("1000000")
_MUST_BE_POSITIVE = {"take_home_pay_monthly"}
_AMOUNT_FIELDS = (
    "take_home_pay_monthly",
    "rent_or_mortgage_monthly",
    "car_payment_monthly",
    "food_monthly",
    "transportation_monthly",
    "other_monthly",
)


class VitalsRequest(BaseModel):
    take_home_pay_monthly: Decimal
    rent_or_mortgage_monthly: Decimal
    car_payment_monthly: Decimal
    food_monthly: Decimal
    transportation_monthly: Decimal
    other_monthly: Decimal

    @field_validator(*_AMOUNT_FIELDS)
    @classmethod
    def _validate_amount(cls, v: Decimal, info) -> Decimal:
        if v < 0:
            raise ValueError(f"{info.field_name} must not be negative")
        if v > _MAX_MONTHLY_AMOUNT:
            raise ValueError(f"{info.field_name} must be at most $1,000,000")
        if v.as_tuple().exponent < -2:
            raise ValueError(f"{info.field_name} must have at most two decimal places")
        if info.field_name in _MUST_BE_POSITIVE and v <= 0:
            raise ValueError(f"{info.field_name} must be greater than zero")
        return v

    @model_validator(mode="after")
    def _validate_combined_spend(self):
        if self.food_monthly + self.transportation_monthly + self.other_monthly <= 0:
            raise ValueError("Combined monthly spend (food + transportation + other) must be greater than zero")
        return self


def _vitals_out(vitals: FinancialVitals) -> dict:
    return {
        "take_home_pay_monthly": cents_to_dollars(vitals.take_home_pay_monthly_cents),
        "rent_or_mortgage_monthly": cents_to_dollars(vitals.rent_or_mortgage_monthly_cents),
        "car_payment_monthly": cents_to_dollars(vitals.car_payment_monthly_cents),
        "food_monthly": cents_to_dollars(vitals.food_monthly_cents),
        "transportation_monthly": cents_to_dollars(vitals.transportation_monthly_cents),
        "other_monthly": cents_to_dollars(vitals.other_spend_monthly_cents),
        "monthly_spend_estimate": cents_to_dollars(total_spend_cents(vitals)),
        "completed_at": vitals.completed_at.isoformat() + "Z",
        "source": "user_estimate",
    }


@router.put("/financial-vitals")
def put_financial_vitals(
    body: VitalsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Replaces the authenticated user's vitals record. Idempotent: repeated
    calls update the same row rather than creating new ones."""
    vitals = save_vitals(
        session,
        current_user.id,
        body.take_home_pay_monthly,
        body.rent_or_mortgage_monthly,
        body.car_payment_monthly,
        body.food_monthly,
        body.transportation_monthly,
        body.other_monthly,
    )
    return _vitals_out(vitals)


@router.get("/financial-vitals")
def read_financial_vitals(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    vitals = get_vitals(session, current_user.id)
    if vitals is None:
        raise HTTPException(status_code=404, detail="No financial vitals saved for this user")
    return _vitals_out(vitals)
