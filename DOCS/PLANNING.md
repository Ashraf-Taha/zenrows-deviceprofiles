# ZenRows Device Profiles — Project Plan & Milestones

> This plan turns the design into a clear iterations.

**What we’re building:**  
An API to create, read, update, list, and soft-delete **Device Profiles** used by scrapers. A profile includes device type, window size, user agent, country, and optional custom headers. Profiles can be cloned from curated templates. Every change bumps a version and we keep an audit snapshot.

**Outcomes for the MVP:**
- Clean, maintainable API with basic security and solid validation  
- PostgreSQL schema + migrations; soft delete; simple versioning  
- Pagination and filters for lists  
- Basic templates and clone flow  
- Logs/metrics/traces wired into **AWS CloudWatch** and **X-Ray**  
- Containerized local dev; optional AWS deploy (ECS Fargate + RDS)

**Chosen Tech (aligns with the design doc):**  
- **API:** FastAPI (Python 3.12), Pydantic for validation  
- **DB:** PostgreSQL 16 (JSONB for flexible headers)  
- **ORM/Migrations:** SQLAlchemy + Alembic  
- **Tests:** pytest + httpx  
- **Packaging/Run:** Docker + docker compose, Uvicorn  
- **Observability:** CloudWatch Logs + **EMF** metrics, CloudWatch Alarms/Dashboards, **AWS X-Ray**, ECS/ALB/RDS Container Insights  
- **Infra (stretch):** Terraform (ECR, ECS Fargate, ALB, RDS, Secrets Manager)

---

## 0) Ground Rules & Glossary
- **Device Profile:** `{device_type, window(width,height), user_agent, country, custom_headers[]}`  
- **Template:** A profile flagged as reusable; global templates are readable by everyone  
- **Owner:** The user tied to an API key; only sees their data  
- **API Key:** Sent via `X-API-Key` header; we store hashes, not raw values  
- **Soft Delete:** We mark `deleted_at` so references don’t break

**Non-Goals (MVP):** org RBAC, multi-region, full-text search, complex rate limiting

---

## 1) Milestones (bird’s eye)
1. M0 — Repo & local environment (DONE)
2. M1 — Database schema & migrations (DONE)
3. M2 — Auth module (API keys + owner scoping) <- expanded with concrete steps  (DONE)
4. M3 — Core CRUD for Device Profiles (DONE)
5. M4 — Templates & clone (DONE)
6. M5 — Validation, filters, pagination (DONE)
7. M6 — Versioning & audit snapshots (DONE)
8. M7 — Error model & security polish  
9. M8 — **Observability on CloudWatch** (+ X-Ray)  
10. M9 — Tests (unit + integration)  
11. M10 — Dockerization & local run  
12. M11 — Docs (README + API quickstart)  
13. M12 — (Stretch) AWS deploy  
14. M13 — Handoff (runbook, on-call notes)
---

## M0 — Repo & Local Environment
**Goal:** A clean skeleton so development is frictionless.

**Tasks**
- Add base folders: `/app` (code), `/migrations`, `/scripts`, `/tests`, `/infra`, `/ops`.
- Initialize Python project (3.12). Add deps: fastapi, uvicorn, pydantic, sqlalchemy, alembic, psycopg, httpx, pytest, boto3 (for future), aws-xray-sdk.
- Add a minimal FastAPI app with a root `GET /healthz`.

**Done when**
- `make dev` starts the API locally and `GET /healthz` returns 200.

---

## M1 — Database Schema & Migrations
**Goal:** Postgres schema that matches the design.

**Tasks**
- Create Alembic migration `001_init`:
  - `users`, `api_keys`, enums: `device_type('desktop','mobile')`, `visibility('private','global')`.
- Create migration `002_profiles`:
  - `device_profiles` with fields from the design, JSONB `custom_headers`, `deleted_at`, checks for window bounds and two-letter `country`.
  - indexes: owner, device_type, is_template; unique `(owner_id, name)` excluding soft-deleted; triggers to auto-touch `updated_at`.
- Create migration `003_versions`:
  - `device_profile_versions` with `(profile_id, version)` PK and full JSON snapshot.
- Optional: table `idempotency_keys` for POST safety.

**Done when**
- Migrations apply cleanly to a local DB via `make migrate-up`.  
- Tables and indexes exist as expected.

---

## M2 — **Auth module (API keys + owner scoping)**
**Goal:** Every request is authenticated via `X-API-Key`, and all data access is scoped to the key’s owner. No separate microservice—keep it in-process for the MVP.

**Tasks**
- **Data model & seeding**
  - Add `users(id, email, created_at)` and `api_keys(id, user_id, key_hash, name, created_at, revoked_at)`.
  - Seed script to create a test user and an API key; print the raw key **once**.
- **Hashing & lookup**
  - Store only **hashed** keys (Argon2id/bcrypt).  
  - Add a **sha256 prefix column** (e.g., first 8–12 hex chars) to narrow candidates before verifying the expensive hash.
  - Index the prefix column.
- **Middleware (`api_key_auth`)**
  - Read `X-API-Key`; if missing → 401.
  - Look up by prefix, verify against `key_hash`; if invalid or `revoked_at` set → 401.
  - On success, attach `request.state.user_id`.
- **Authorization (repo-level)**
  - All queries include `owner_id = :user_id` (soft-deleted excluded), except **read-only access** to global templates.
- **Response behavior**
  - 401 for missing/invalid key; reserve 403 for future role-based constraints (not in MVP).
- **Docs**
  - Document header usage, error codes, and rotation/revocation procedure.

**Done when**
- Requests without/invalid key are rejected with 401.  
- With a valid key, all repo calls are owner-scoped; global templates are readable by anyone.

---

## M3 — Core CRUD for Device Profiles
**Goal:** Create, read, update, list, and soft-delete profiles.

**Tasks**
- Define Pydantic DTOs: `CreateProfile`, `UpdateProfile`, `ProfileResponse`.
- Implement handlers:
  - `POST /v1/device-profiles` (supports `Idempotency-Key`)
  - `GET /v1/device-profiles/{id}`
  - `GET /v1/device-profiles`
  - `PATCH /v1/device-profiles/{id}` (partial; **optimistic concurrency**, require `If-Match: <version>`)
  - `DELETE /v1/device-profiles/{id}` (soft delete)
- Add repository functions and transactions.

**Done when**
- CRUD works end-to-end against Postgres with owner isolation and soft delete.

---

## M4 — Templates & Clone Flow
**Goal:** Seed a few global templates and allow cloning.

**Tasks**
- Seed script to insert global templates (e.g., Chrome/Windows, iPhone, Android).
- `POST /v1/device-profiles` accepts `{template_id, overrides}` and clones into the caller’s space.

**Done when**
- Listing with `?is_template=true` shows templates.  
- Creating from template produces a valid, owned profile.

---

## M5 — Validation, Filters, Pagination
**Goal:** Make the API robust and comfortable to use.

**Tasks**
- Validation rules: device_type enum; window width/height bounds; country regex and allow-list; header key denylist (`host`, `content-length`); size caps.
- Filters on list: `is_template`, `device_type`, `country`, `q` (name prefix).
- Cursor pagination with stable ordering (`created_at, id`); opaque base64 cursor.

**Done when**
- Bad inputs return 400 with clear field-level errors.  
- Listing with filters + pagination is predictable and stable.

---

## M6 — Versioning & Audit
**Goal:** Keep immutable snapshots and bump versions on change.

**Tasks**
- On create: write version `1` snapshot.
- On update: transactional bump `version = version+1`, write a snapshot with `changed_by`.
- Optional: `GET /v1/device-profiles/{id}/versions` lists metadata.

**Done when**
- Updates create audit rows and version increments atomically.

---

## M7 — Error Model & Security Polish
**Goal:** Production-sensible errors and no sensitive leakage.

**Tasks**
- Middleware to emit **Problem+JSON** with fields: `type,title,status,detail,request_id,errors[]`.
- Mask values in `custom_headers` in logs and traces; never log secrets.
- Lightweight per-key rate limit (token bucket; config-driven).

**Done when**
- Errors are consistent; sensitive data never appears in logs.

---

## M8 — Observability (CloudWatch + X-Ray)
**Goal:** Useful logs, metrics, and traces from day one.

**Tasks**
- **Logs:** structured JSON to stdout (request_id, user_id, route, method, status, duration_ms, error_code). Ship to **CloudWatch Logs** with retention.
- **Metrics:** emit **EMF** lines (namespace `ZenRows/DeviceProfiles`, dims `Service=device-profiles-api`, `Env`).  
  Core: `RequestCount`, `LatencyMs`, `Errors4xx`, `Errors5xx`, optional `DBQueryMs`.
- **Tracing:** add AWS **X-Ray** middleware; capture inbound + DB spans; sample ~10% in prod.
- **Alarms:** 5xx > 1% (5m), p95 latency > 300ms (5m), RDS CPU > 80% (10m), free storage < 20%, ECS running < desired, ALB p95 > 500ms.
- **Dashboards:** app (count/errors/latency), infra (ECS CPU/Mem, RDS CPU/Conns, ALB TargetResponseTime).

**Done when**
- You can see requests, latencies, and error spikes in CloudWatch; traces show DB spans.

---

## M9 — Tests (Unit & Integration)
**Goal:** Confidence to refactor.

**Tasks**
- Unit tests: validators, auth middleware, small utilities.
- Repo tests: run against a throwaway DB; use transactions rollback per test.
- HTTP tests: spin up app, hit endpoints with httpx; cover happy paths and edge cases.

**Done when**
- `pytest -q` passes locally; core paths are covered.

---

## M10 — Dockerization & Local Run
**Goal:** One command to run the whole thing.

**Tasks**
- Multi-stage Dockerfile (build → minimal runtime).
- `docker compose` for `api + postgres`. Health checks for `/readyz`.
- Makefile shortcuts: `make dev`, `make test`, `make migrate-up`.

**Done when**
- `docker compose up` starts DB + API; CRUD works locally.

---

## M11 — Docs (README + API Quickstart)
**Goal:** Anyone can run it in minutes.

**Tasks**
- **README** with: what this is, how to run, how to test, env vars, sample requests, design choices, future work.
- Quickstart cURL commands and a short Postman collection (optional).

**Done when**
- A new engineer can go from clone → running API in under 10 minutes.

---

## M12 — (Stretch) AWS Deploy
**Goal:** A lean, secure AWS setup.

**Tasks**
- Terraform modules for VPC, ECS Fargate service (2 AZs), ALB (HTTPS), RDS Postgres (encrypted), Secrets Manager, CloudWatch alarms.
- GitHub Actions workflow: build, push to ECR, deploy to ECS.
- App reads DB creds from Secrets Manager; security groups are tight (private subnets, ALB public listener).

**Done when**
- The service is reachable via ALB in a sandbox account; health checks pass; logs/metrics flow to CloudWatch.

---

## M13 — Handoff (Runbook & On-call Notes)
**Goal:** Smooth operations after delivery.

**Tasks**
- `RUNBOOK.md`: start/stop, config, log search snippets, common errors.
- On-call one-pager: what to check first for spikes or 5xx.
- `CHANGELOG.md` and tag `v0.1.0`.

**Done when**
- Another engineer can support the service without extra help.

---

## Appendix A — Configuration
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`  
- `PORT` (default 8080)  
- `LOG_LEVEL` (`info|debug`)  
- `RATE_LIMIT_RPS` (optional)  
- `DISABLE_RATE_LIMIT` (`true|false`)

---

## Appendix B — Quickstart Commands
```
# Start local DB + API (first time)
docker compose up --build

# Apply migrations
make migrate-up

# Health checks
curl -i http://localhost:8080/healthz
curl -i http://localhost:8080/readyz

# Create a profile (replace $KEY)
curl -s -X POST http://localhost:8080/v1/device-profiles \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"name":"Amazon Desktop","device_type":"desktop","window":{"width":1366,"height":768},"user_agent":"Mozilla/5.0","country":"gb"}' | jq .

# List profiles
curl -s "http://localhost:8080/v1/device-profiles?limit=20" \
  -H "X-API-Key: $KEY" | jq .
```

---

## Appendix C — Definition of Done
- Milestones M0–M11 completed; stretch M12 deployed if time allows  
- Tests green; CRUD & versioning verified end-to-end  
- CloudWatch shows logs/metrics; X-Ray traces are visible  
- README is accurate; sensitive values never logged
