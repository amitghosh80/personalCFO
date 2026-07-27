from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings as _get_settings
from .database import create_db_and_tables, get_engine
from .models import Insight, User  # noqa: F401 — ensures tables are registered before create_all
from .routers import upload, transactions
from .routers import insights
from .routers import chat
from .routers import categories
from .routers import auth


def _migrate():
    """Add columns that didn't exist in older schema versions."""
    import sqlite3 as _sqlite3
    from .config import get_settings
    db_url = get_settings().database_url  # e.g. "sqlite:///./personalcfo.db"
    db_path = db_url.replace("sqlite:///", "") or "personalcfo.db"
    new_columns = [
        ("expense_category", "TEXT"),
        ("is_transfer", "BOOLEAN DEFAULT 0"),
        ("transfer_status", "TEXT"),
        ("transfer_pair_id", "INTEGER"),
        ("category_confidence", "REAL"),
        ("confidence_label", "TEXT"),
    ]
    # user_id lands on every per-user table once multi-tenancy ships (nullable so
    # existing local rows stay valid until the first signup claims them).
    user_scoped_tables = ["transaction", "importjob", "merchantrule", "insight"]

    raw = _sqlite3.connect(db_path)
    for col, decl in new_columns:
        try:
            raw.execute(f'ALTER TABLE "transaction" ADD COLUMN {col} {decl}')
        except _sqlite3.OperationalError:
            pass  # column already exists — safe to ignore
    for table in user_scoped_tables:
        try:
            raw.execute(f'ALTER TABLE "{table}" ADD COLUMN user_id INTEGER')
        except _sqlite3.OperationalError:
            pass  # column already exists, or table doesn't exist yet — safe to ignore
    raw.commit()
    raw.close()


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

_default_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]
_extra_origins = [o.strip() for o in _get_settings().allowed_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(transactions.router)
app.include_router(insights.router)
app.include_router(chat.router)
app.include_router(categories.router)
