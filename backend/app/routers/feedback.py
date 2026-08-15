from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlmodel import Session

from ..database import get_session
from ..dependencies import get_current_user
from ..models.feedback import Feedback
from ..models.user import User
from ..rate_limit import limiter

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

_CATEGORIES = {"bug", "feature", "general"}


class FeedbackRequest(BaseModel):
    category: str = "general"
    message: str
    page_url: str | None = None

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str) -> str:
        if v not in _CATEGORIES:
            raise ValueError(f"category must be one of {sorted(_CATEGORIES)}")
        return v

    @field_validator("message")
    @classmethod
    def _non_empty_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        if len(v) > 5000:
            raise ValueError("message must be 5000 characters or fewer")
        return v


@router.post("")
@limiter.limit("10/hour")
def submit_feedback(
    request: Request,
    body: FeedbackRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    feedback = Feedback(
        user_id=current_user.id,
        category=body.category,
        message=body.message,
        page_url=body.page_url,
    )
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    return {"id": feedback.id, "created_at": str(feedback.created_at)}
