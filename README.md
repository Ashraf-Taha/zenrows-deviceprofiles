# ZenRows Device Profiles API

A FastAPI service to create, read, update, list, and soft-delete reusable device profiles for web scraping. Includes owner scoping via API keys, versioning with audit snapshots, templates/clone, filters/pagination, and a comprehensive test suite.

Links to docs:
- System design: `DOCS/HIGH_LEVEL_DESIGN.md`
- Project plan & milestones: `DOCS/PLANNING.md`

Health endpoints:
- GET http://127.0.0.1:8080/healthz → { "status": "ok" }
- GET http://127.0.0.1:8080/readyz → { "status": "ready" }

## Table of contents

- What you get
- Prerequisites
- Quickstart (Windows PowerShell)
- Quickstart (macOS/Linux)
- Run with Docker Compose
- API docs & testing in Swagger UI
- Authentication & seeding an API key
- Database & migrations
- Running tests
- Make targets
- Project structure
- Configuration
- Troubleshooting

## What you get

- FastAPI app with middleware-enforced API key auth (header: `X-API-Key`)
- Device Profiles CRUD with soft delete, templates + clone flow, validation, pagination/filters
- Versioning and immutable audit snapshots
- Idempotency for POST via `Idempotency-Key`
- SQLAlchemy + Alembic migrations (PostgreSQL 16)
- Rich tests with pytest
- Dockerfile + docker compose for local stack

## Prerequisites

- Python 3.11+
- PostgreSQL 16 (local or via Docker)
- Windows PowerShell 5.1+ (for Windows quickstart) or a Unix-like shell

## Quickstart (Windows PowerShell)

```powershell
# 1) Create virtual env and install deps
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]

# 2) Ensure Postgres is reachable (env below). If you don’t have Postgres, see Docker section.
$env:DB_HOST = "localhost"
$env:DB_PORT = "5432"
$env:DB_NAME = "zenrows"
$env:DB_USER = "postgres"
$env:DB_PASSWORD = "postgres"

# 3) Run migrations
.\.venv\Scripts\alembic.exe upgrade head

# 4) Seed an API key (prints it once — save it!)
python .\scripts\seed_api_key.py

# 5) Start the API (port defaults to 8080)
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8080 --reload
```

Visit Swagger UI at http://127.0.0.1:8080/docs

## Quickstart (macOS/Linux)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=zenrows
export DB_USER=postgres
export DB_PASSWORD=postgres

alembic upgrade head
python scripts/seed_api_key.py   # save the printed key

uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8080 --reload
```

## Run with Docker Compose

This brings up Postgres and the API. The API is exposed at http://localhost:8088.

```bash
docker compose up --build
```

Notes:
- Migrations run automatically at startup.
- Templates and an API key are seeded by default; the raw API key is printed to the container logs once. Keep the terminal open to copy it, or run `docker compose logs -f api` to retrieve it.
- Health checks: http://localhost:8088/healthz and /readyz

## API docs & testing in Swagger UI

Swagger UI is available at:
- Local run: http://127.0.0.1:8080/docs
- Docker compose: http://localhost:8088/docs

Steps to test in Swagger:
1) Obtain an API key (see “Authentication & seeding” below).
2) Open Swagger UI and click the “Authorize” lock button.
3) In the “ApiKeyAuth” section, paste your API key as the value. This sets the `X-API-Key` header for your requests. Authorization persists across page reloads.
4) Try endpoints under the `device-profiles` tag:
	 - POST /v1/device-profiles — create a profile (or clone via `template_id`)
	 - GET /v1/device-profiles — list profiles with filters and pagination
	 - GET /v1/device-profiles/{id} — fetch one; the response includes `ETag: <version>`
	 - PATCH /v1/device-profiles/{id} — send partial fields and include the current `version` in the JSON body for optimistic concurrency
	 - DELETE /v1/device-profiles/{id} — soft delete

Tips:
- POST supports idempotency via an `Idempotency-Key` header. Swagger UI doesn’t let you add arbitrary headers for a single call by default; use curl for idempotency testing (see “API cheat sheet”).
- For conditional GETs, copy the `ETag` header from GET and send `If-None-Match: <same-value>` on subsequent GETs to receive `304 Not Modified`.

## Authentication & seeding an API key

- Auth is enforced by middleware on all non-health/documentation routes.
- Header: `X-API-Key: <your-key>`
- Seed a test key locally:
	- Run `python scripts/seed_api_key.py` after migrations; it prints the raw key once. Save it; only the hash is stored.
	- With Docker compose, the key is printed at container startup by the entrypoint.

## Database & migrations

- SQLAlchemy engine reads env vars: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (or `DATABASE_URL`).
- Apply migrations: `alembic upgrade head` (or `make migrate-up`).
- Generate new migration (autogenerate): `alembic revision --autogenerate -m "your message"` (or `make makemigrations m=\"your message\"`).

## Running tests

```powershell
# Windows PowerShell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"  # avoids slow/fragile global plugins
if (Test-Path .\.venv\Scripts\python.exe) { .\.venv\Scripts\python.exe -m pytest -q } else { pytest -q }
```

```bash
# macOS/Linux
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```

You can also use the provided VS Code task “Tests: Pytest (venv)”.

## Make targets

```bash
make install      # create venv and install deps
make dev          # run API with uvicorn (reload)
make test         # pytest -q
make migrate-up   # alembic upgrade head
make lint         # ruff
make typecheck    # mypy
```

## Project structure

- `app/` — FastAPI app and modules (auth, db, profiles, orchestrator, core)
- `migrations/` — Alembic migration scripts
- `scripts/` — Dev helpers (PowerShell + seeders)
- `tests/` — Pytest suite (units + integration)
- `DOCS/` — Design and planning docs
- `infra/`, `ops/` — placeholders for future milestones

## Configuration

Key environment variables (see also `DOCS/PLANNING.md` Appendix A):
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` or `DATABASE_URL`
- `PORT` (default 8080)
- `LOG_LEVEL` (info|debug)
- `SEED_TEMPLATES` (true|false), `SEED_API_KEY` (true|false) — used by Docker entrypoint

## API cheat sheet (curl)

PowerShell quoting is different; examples below include both PowerShell and bash.

Create a profile (PowerShell):
```powershell
$KEY = "<paste-your-api-key>"
curl -s -X POST http://127.0.0.1:8080/v1/device-profiles `
	-H "X-API-Key: $KEY" -H "Content-Type: application/json" `
	--data '{"name":"Amazon Desktop","device_type":"desktop","window":{"width":1366,"height":768},"user_agent":"Mozilla/5.0","country":"gb"}'
```

Create a profile (bash):
```bash
KEY=<paste-your-api-key>
curl -s -X POST http://127.0.0.1:8080/v1/device-profiles \
	-H "X-API-Key: $KEY" -H "Content-Type: application/json" \
	-d '{"name":"Amazon Desktop","device_type":"desktop","window":{"width":1366,"height":768},"user_agent":"Mozilla/5.0","country":"gb"}'
```

Idempotent create (bash, note Idempotency-Key):
```bash
KEY=<paste-your-api-key>
curl -s -X POST http://127.0.0.1:8080/v1/device-profiles \
	-H "X-API-Key: $KEY" -H "Idempotency-Key: abc123" -H "Content-Type: application/json" \
	-d '{"name":"Idem Test","device_type":"desktop","window":{"width":800,"height":600},"user_agent":"Mozilla/5.0","country":"us"}'
```

Conditional GET using ETag (bash):
```bash
KEY=<key>
ETAG=$(curl -si -H "X-API-Key: $KEY" http://127.0.0.1:8080/v1/device-profiles | grep -i ETag | awk '{print $2}' | tr -d '\r')
curl -i -H "X-API-Key: $KEY" -H "If-None-Match: $ETAG" http://127.0.0.1:8080/v1/device-profiles/<id>
```

Patch with optimistic concurrency (include current version in body):
```bash
KEY=<key>
curl -s -X PATCH http://127.0.0.1:8080/v1/device-profiles/<id> \
	-H "X-API-Key: $KEY" -H "Content-Type: application/json" \
	-d '{"name":"New Name","version":3}'
```

## Troubleshooting

- Swagger shows 401 even after Authorize: ensure you pasted the raw API key (not a hash) and the server process restarted after seeding.
- Database connection errors: verify `DB_*` env vars and that Postgres is listening. With Docker compose, the app waits for DB readiness automatically.
- PowerShell execution policy blocks activation: run `Set-ExecutionPolicy -Scope Process RemoteSigned` in your shell, then activate the venv again.
- “pytest hangs or is slow”: set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` as shown above to avoid loading global plugins.

---

See the full architecture and rationale in `DOCS/HIGH_LEVEL_DESIGN.md` and the delivery plan in `DOCS/PLANNING.md`.