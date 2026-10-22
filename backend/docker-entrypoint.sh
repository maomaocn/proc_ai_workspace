#!/bin/sh
set -eu

alembic upgrade head

if [ "${SEED_DEMO_DATA:-true}" = "true" ] && [ "${APP_ENV:-local}" = "production" ]; then
  printf '%s\n' 'SEED_DEMO_DATA must be disabled in production' >&2
  exit 1
fi

if [ "${SEED_DEMO_DATA:-true}" = "true" ]; then
  python -m app.db.seed
fi

exec uvicorn app.main:app \
  --host "${API_HOST:-0.0.0.0}" \
  --port "${API_PORT:-8000}" \
  --no-access-log \
  --log-level "$(printf '%s' "${LOG_LEVEL:-INFO}" | tr '[:upper:]' '[:lower:]')"
