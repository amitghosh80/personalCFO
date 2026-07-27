from sqlmodel import Field, SQLModel
from datetime import datetime
from typing import Optional
from enum import Enum


class ImportStatus(str, Enum):
    processing = "processing"
    pending_income_review = "pending_income_review"
    completed = "completed"


class ImportJob(SQLModel, table=True):
    id: str = Field(primary_key=True)  # UUID
    user_id: Optional[int] = Field(default=None, foreign_key="app_user.id", index=True)
    status: ImportStatus = Field(default=ImportStatus.processing)
    file_count: int
    total_transactions: int = Field(default=0)
    file_results_json: Optional[str] = Field(default=None)  # JSON array of per-file summaries
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
