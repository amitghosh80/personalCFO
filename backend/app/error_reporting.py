"""Sentry wiring with PII scrubbing for a finance app.

Financial data (transaction descriptions/amounts, emails, chat text) must
never reach Sentry. `send_default_pii`/`max_request_body_size` are the real
controls (they stop the SDK from ever attaching request bodies or user
identity); `_scrub_event` is a defense-in-depth backstop, not the primary
control — the real guarantee is that app code never puts financial data
into an exception message in the first place.
"""
import sentry_sdk

from .config import Settings


def _scrub_event(event: dict, hint: dict) -> dict:
    event.pop("user", None)
    request = event.get("request")
    if request:
        request.pop("data", None)
        request.pop("query_string", None)
        request.pop("cookies", None)
    return event


def init_error_reporting(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        send_default_pii=False,
        max_request_body_size="never",
        traces_sample_rate=0.0,
        before_send=_scrub_event,
    )
