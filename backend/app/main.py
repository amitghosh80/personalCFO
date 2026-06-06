from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import create_db_and_tables, get_engine
from .models import Insight  # noqa: F401 — ensures table is registered before create_all
from .routers import upload, transactions
from .routers import insights


def _migrate():
    """Add columns that didn't exist in older schema versions."""
    import sqlite3 as _sqlite3
    from .config import get_settings
    db_url = get_settings().database_url  # e.g. "sqlite:///./personalcfo.db"
    db_path = db_url.replace("sqlite:///", "") or "personalcfo.db"
    try:
        raw = _sqlite3.connect(db_path)
        raw.execute("ALTER TABLE \"transaction\" ADD COLUMN expense_category TEXT")
        raw.commit()
        raw.close()
    except _sqlite3.OperationalError:
        pass  # column already exists — safe to ignore


def _backfill_expense_categories():
    """Classify expense_category for any debit transactions missing it."""
    from sqlmodel import Session, select
    from .models.transaction import Transaction, TransactionType
    from .services.encryption import decrypt
    from .services.expense_categorizer import categorize_expense

    with Session(get_engine()) as session:
        txns = session.exec(
            select(Transaction)
            .where(Transaction.transaction_type == TransactionType.debit)
            .where(Transaction.expense_category == None)  # noqa: E711
        ).all()
        for t in txns:
            try:
                primary, sub, source = categorize_expense(decrypt(t.description))
                t.expense_category = primary
                t.expense_subcategory = sub
                t.category_source = source
                session.add(t)
            except Exception:
                pass
        if txns:
            session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    _migrate()
    _backfill_expense_categories()
    yield


app = FastAPI(title="PersonalCFO API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(transactions.router)
app.include_router(insights.router)
