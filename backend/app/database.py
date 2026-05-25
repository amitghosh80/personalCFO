from sqlmodel import SQLModel, create_engine, Session
from .config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_settings().database_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    return _engine


def create_db_and_tables():
    SQLModel.metadata.create_all(get_engine())


def get_session():
    with Session(get_engine()) as session:
        yield session
