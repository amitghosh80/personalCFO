import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlmodel import Session
from .config import get_settings as _get_settings
from .database import get_engine
from .error_reporting import init_error_reporting
from .logging_config import configure_logging
from .rate_limit import limiter
from .services.demo_seed import ensure_demo_data
from .routers import upload, transactions
from .routers import insights
from .routers import chat
from .routers import categories
from .routers import auth
from .routers import health
from .routers import feedback
from .routers import financial_profile
from .routers import financial_vitals
from .routers import sandbox

configure_logging()
init_error_reporting(_get_settings())

app = FastAPI(title="PersonalCFO API", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(transactions.router)
app.include_router(insights.router)
app.include_router(chat.router)
app.include_router(categories.router)
app.include_router(feedback.router)
app.include_router(financial_profile.router)
app.include_router(financial_vitals.router)
app.include_router(sandbox.router)


@app.on_event("startup")
def _seed_sandbox_demo_data() -> None:
    """Best-effort: the sandbox demo is a supporting feature, never a reason
    for the whole app to fail to start."""
    try:
        with Session(get_engine()) as session:
            ensure_demo_data(session)
    except Exception:
        logging.getLogger("personalcfo.sandbox").exception("Failed to seed sandbox demo data")
