from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class FinancialVitals(SQLModel, table=True):
    __tablename__ = "financial_vitals"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="app_user.id", unique=True, index=True)
    take_home_pay_monthly_cents: int
    rent_or_mortgage_monthly_cents: int
    car_payment_monthly_cents: int
    # Spending breakdown: replaces a single lump "total monthly spend" figure
    # so the estimated Fixed vs. Discretionary tile has some texture.
    food_monthly_cents: int
    transportation_monthly_cents: int
    other_spend_monthly_cents: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime = Field(default_factory=datetime.utcnow)
