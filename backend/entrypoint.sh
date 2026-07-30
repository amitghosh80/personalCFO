#!/bin/sh
set -e
alembic upgrade head
exec gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 60
