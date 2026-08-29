from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from sqlmodel import Session

from ..database import get_session
from ..dependencies import get_current_user
from ..models.feedback import Feedback
from ..models.user import User
from ..rate_limit import limiter
from ..services.linear_client import create_bug_issue

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

_CATEGORIES = {"bug", "feature", "general"}
_MAX_ATTACHMENT_MB = 5
_MAX_ATTACHMENT_BYTES = _MAX_ATTACHMENT_MB * 1024 * 1024
_ALLOWED_ATTACHMENT_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"}


def _linear_title(message: str) -> str:
    first_line = message.strip().splitlines()[0]
    return f"[Feedback] {first_line[:80]}"


def _linear_description(feedback: Feedback, user_email: str) -> str:
    lines = [
        f"**Category:** {feedback.category}",
        f"**Page:** {feedback.page_url or 'unknown'}",
        f"**Submitted by:** {user_email} (user_id={feedback.user_id})",
        f"**Feedback ID:** {feedback.id}",
    ]
    if feedback.attachment_filename:
        lines.append(f"**Attachment:** {feedback.attachment_filename} (stored in the app, not attached here)")
    lines.append("")
    lines.append(feedback.message)
    return "\n".join(lines)


@router.post("")
@limiter.limit("10/hour")
async def submit_feedback(
    request: Request,
    background_tasks: BackgroundTasks,
    category: str = Form("general"),
    message: str = Form(...),
    page_url: str | None = Form(None),
    attachment: UploadFile | None = File(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if category not in _CATEGORIES:
        raise HTTPException(status_code=422, detail=f"category must be one of {sorted(_CATEGORIES)}")

    message = message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="message must not be empty")
    if len(message) > 5000:
        raise HTTPException(status_code=422, detail="message must be 5000 characters or fewer")

    attachment_bytes: bytes | None = None
    attachment_filename: str | None = None
    attachment_content_type: str | None = None
    if attachment is not None and attachment.filename:
        if attachment.content_type not in _ALLOWED_ATTACHMENT_TYPES:
            raise HTTPException(status_code=422, detail="Attachment must be an image or PDF")
        attachment_bytes = await attachment.read()
        if len(attachment_bytes) > _MAX_ATTACHMENT_BYTES:
            raise HTTPException(status_code=422, detail=f"Attachment must be {_MAX_ATTACHMENT_MB}MB or smaller")
        attachment_filename = attachment.filename
        attachment_content_type = attachment.content_type

    feedback = Feedback(
        user_id=current_user.id,
        category=category,
        message=message,
        page_url=page_url,
        attachment=attachment_bytes,
        attachment_filename=attachment_filename,
        attachment_content_type=attachment_content_type,
    )
    session.add(feedback)
    session.commit()
    session.refresh(feedback)

    background_tasks.add_task(
        create_bug_issue, _linear_title(feedback.message), _linear_description(feedback, current_user.email)
    )

    return {"id": feedback.id, "created_at": str(feedback.created_at)}
