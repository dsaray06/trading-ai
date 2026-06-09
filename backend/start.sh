#!/usr/bin/env sh
# Production entrypoint: run DB migrations, then serve on the platform's $PORT
# (Render injects PORT; default to 8000 locally).
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
