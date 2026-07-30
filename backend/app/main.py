from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .config import get_settings as _get_settings
from .error_reporting import init_error_reporting
from .logging_config import configure_logging
from .rate_limit import limiter
from .routers import upload, transactions
from .routers import insights
from .routers import chat
from .routers import categories
from .routers import auth
from .routers import health

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
