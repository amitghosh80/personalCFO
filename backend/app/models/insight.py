from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class InsightType:
    spending_increase = "spending_increase"
    spending_decrease = "spending_decrease"
    income_change = "income_change"
    recurring_charge = "recurring_charge"
    duplicate_charge = "duplicate_charge"
    large_expense = "large_expense"
    merchant_spike = "merchant_spike"
    cashflow_risk = "cashflow_risk"
    transfer_detected = "transfer_detected"
    subscription_creep = "subscription_creep"
    top_spending_category = "top_spending_category"
    category_spike = "category_spike"


class Severity:
    low = "low"
    medium = "medium"
    high = "high"


class Insight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="app_user.id", index=True)
    import_job_id: str = Field(index=True)
    insight_type: str
    title: str
    explanation: str
    severity: str
    confidence: float
    confidence_label: str
    time_period_start: Optional[date] = Field(default=None)
    time_period_end: Optional[date] = Field(default=None)
    supporting_transaction_ids: str = Field(default="[]")  # JSON
    suggested_next_step: str
    is_dismissed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    meta_json: str = Field(default="{}")  # JSON (named to avoid SQLAlchemy reserved 'metadata')
