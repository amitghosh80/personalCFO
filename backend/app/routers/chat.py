import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session

from ..database import get_session
from ..dependencies import get_current_user
from ..models.user import User
from ..rate_limit import limiter
from ..services.analytics import data_coverage, starter_questions
from ..services.chat_service import answer_question

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger("personalcfo.chat")


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessageIn] = []
    # Set once the user has dismissed the uncategorized-data warning (AMI-33).
    suppress_data_warning: bool = False


@router.post("/chat")
@limiter.limit("20/minute")
def chat(
    request: Request,
    req: ChatRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    logger.info(f"chat request user_id={current_user.id} message_length={len(req.question)}")
    history = [{"role": m.role, "content": m.content} for m in req.history]
    try:
        result = answer_question(
            session, current_user.id, req.question, history,
            suppress_data_warning=req.suppress_data_warning,
        )
    except RuntimeError as e:  # config problem (e.g. missing API key)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:  # upstream/model failure
        logger.exception(f"chat failed user_id={current_user.id}")
        raise HTTPException(status_code=502, detail="Chat failed — please try again")
    # Attach the data scope so the UI can show a coverage footer.
    result["coverage"] = data_coverage(session, current_user.id)
    return result


@router.get("/chat/starters")
def chat_starters(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Contextual suggested questions for the chat screen."""
    return {"questions": starter_questions(session, current_user.id)}
