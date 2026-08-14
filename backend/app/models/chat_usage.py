from datetime import date as date_, datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class ChatUsage(SQLModel, table=True):
    """Per-user, per-day counter of /api/chat requests, used to enforce a
    daily cap so a single user can't run up unbounded Anthropic API cost."""

    __tablename__ = "chat_usage"
    __table_args__ = (UniqueConstraint("user_id", "usage_date"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="app_user.id", index=True)
    usage_date: date_ = Field(index=True)
    message_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
