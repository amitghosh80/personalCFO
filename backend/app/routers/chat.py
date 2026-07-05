from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from ..database import get_session
from ..services.analytics import data_coverage, starter_questions
from ..services.chat_service import answer_question

router = APIRouter(prefix="/api", tags=["chat"])


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessageIn] = []
    # Set once the user has dismissed the uncategorized-data warning (AMI-33).
    suppress_data_warning: bool = False


@router.post("/chat")
def chat(req: ChatRequest, session: Session = Depends(get_session)):
    history = [{"role": m.role, "content": m.content} for m in req.history]
    try:
        result = answer_question(
            session, req.question, history,
            suppress_data_warning=req.suppress_data_warning,
        )
    except RuntimeError as e:  # config problem (e.g. missing API key)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:  # upstream/model failure
        raise HTTPException(status_code=502, detail=f"Chat failed: {e}")
    # Attach the data scope so the UI can show a coverage footer.
    result["coverage"] = data_coverage(session)
    return result


@router.get("/chat/starters")
def chat_starters(session: Session = Depends(get_session)):
    """Contextual suggested questions for the chat screen."""
    return {"questions": starter_questions(session)}
