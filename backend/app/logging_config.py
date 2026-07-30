"""Structured stdout logging for the app.

Never log: transaction `description` (decrypted or raw encrypted bytes),
`amount`, raw email addresses, JWT tokens/passwords, uploaded file contents
or filenames, or raw chat message/response text. Log only ids, counts, and
status — this mirrors the security principle in CLAUDE.md ("financial data
excluded from all logs").
"""
import logging
import sys

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
    ))
    root = logging.getLogger("personalcfo")
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root.propagate = False
    _CONFIGURED = True
