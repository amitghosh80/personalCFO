from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Feedback(SQLModel, table=True):
    __tablename__ = "feedback"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="app_user.id", index=True)
    category: str = Field(default="general")
    message: str
    page_url: Optional[str] = Field(default=None)
    attachment: Optional[bytes] = Field(default=None)
    attachment_filename: Optional[str] = Field(default=None)
    attachment_content_type: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
