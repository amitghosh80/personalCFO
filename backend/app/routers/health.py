from fastapi import APIRouter, Depends
from sqlmodel import Session
from sqlalchemy import text

from ..database import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
def health(session: Session = Depends(get_session)):
    session.exec(text("SELECT 1"))
    return {"status": "ok"}
