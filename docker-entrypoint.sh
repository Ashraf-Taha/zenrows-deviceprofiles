#!/usr/bin/env bash
set -euo pipefail

# Defaults for DB connectivity
: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_NAME:=zenrows}"
: "${DB_USER:=postgres}"
: "${DB_PASSWORD:=postgres}"

export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD

echo "[entrypoint] Waiting for database ${DB_HOST}:${DB_PORT}..."
for i in {1..60}; do
  if python - <<'PY'
import os,sys
import psycopg
host=os.environ.get('DB_HOST','db'); port=int(os.environ.get('DB_PORT','5432'))
user=os.environ.get('DB_USER','postgres'); pwd=os.environ.get('DB_PASSWORD','postgres')
db=os.environ.get('DB_NAME','zenrows')
try:
  with psycopg.connect(host=host, port=port, user=user, password=pwd, dbname=db) as conn:
    pass
  sys.exit(0)
except Exception as e:
  sys.exit(1)
PY
  then
    break
  fi
  sleep 1
done

echo "[entrypoint] Running migrations..."
alembic upgrade head

if [ "${SEED_TEMPLATES:-true}" = "true" ]; then
  echo "[entrypoint] Seeding templates..."
  python scripts/seed_templates.py || true
fi

if [ "${SEED_API_KEY:-true}" = "true" ]; then
  echo "[entrypoint] Seeding API key (printed below, save it now):"
  python scripts/seed_api_key.py || true
fi

echo "[entrypoint] Starting API..."
exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8080}"
