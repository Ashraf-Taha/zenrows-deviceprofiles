# ZenRows Device Profiles – MVP Plan

This API lets you create, edit, list, and delete reusable device profiles for web scraping. Scrapers can pass a profile ID instead of rebuilding headers and user agents every time.

**Recommendation:** run a small containerized service on AWS (ECS Fargate) with PostgreSQL (RDS). Postgres gives us JSONB for flexible headers and easy auditing. Keep the design MVP-simple but production-sensible (least-privilege IAM, encryption, health checks, observability).

---

## 1) Functional Requirements
- Create a profile (from scratch or by cloning a template)
- Read a profile by ID
- List my profiles with filters (template/non-template, device type, country) and pagination
- Update a profile (partial updates)
- Delete a profile (soft delete so old references don’t break)
- Templates: curated set to clone
- Ownership: users only see their profiles, global templates are readable by everyone
- Validation: required fields, window size bounds, allowed countries, clean header keys
- Versioning/audit: every change bumps a version and stores a snapshot

---

## 2) Non-Functional Requirements
- **Security:** API key auth, least-privilege IAM, TLS in transit, KMS at rest, never log sensitive header values, optional field-level encryption for `custom_headers.value` (KMS envelope)
- **Reliability:** 99.9% target, safe migrations and rollback
- **Performance:** p50 < 50 ms for CRUD in-region, p99 < 300 ms under light load
- **Scalability:** scale out ECS tasks, RDS read replicas if needed, add Redis cache later if necessary
- **Observability:** **AWS CloudWatch** (Logs, Metrics via **EMF**, Alarms, Dashboards) and **AWS X-Ray** for tracing, enable **ECS/ALB/RDS Container Insights**
- **Cost:** small footprint (1–2 Fargate tasks, small RDS) with room to grow
- **Operability:** IaC (Terraform/CDK), blue/green or rolling deploys, runbooks, health endpoints `/healthz` (liveness) and `/readyz` (readiness)
- **Edge/Cross-cutting:** CORS (if needed), HSTS on ALB, AWS WAF on the public listener, per-key rate limiting (token bucket, default e.g., 60 rpm)

---

## 3) Core Models, Tables, and Schemas

### 3.1 Entities
- **User:** owner/creator
- **DeviceProfile:** the main resource referenced by scraping jobs
- **DeviceProfileVersion:** immutable change history (audit/rollback)  
  Note: “templates” are represented by `is_template=true` and `visibility='global'` on `device_profiles`.

### 3.2 DeviceProfile shape
```
{
  "id": "prof_01…",
  "owner_id": "usr_01…",
  "name": "Amazon Desktop",
  "device_type": "desktop|mobile",
  "window": { "width": 1366, "height": 768 },
  "user_agent": "Mozilla/5.0 …",
  "country": "gb",
  "custom_headers": [ { "key": "cookie", "value": "…" } ],
  "is_template": false,
  "visibility": "private|global",
  "version": 3,
  "created_at": "…",
  "updated_at": "…",
  "deleted_at": null
}
```

**Validation rules (subset):**
- `device_type` is {desktop, mobile}
- `width,height` in 1..10000
- `country` is lower-case two-letter (allow list)
- `custom_headers`: keys lower-cased, denylist headers like `host`/`content-length`, cap sizes
- **Name uniqueness per owner** (case-insensitive) for non-deleted profiles

### 3.3 PostgreSQL tables (sketch)
```
CREATE EXTENSION IF NOT EXISTS citext,

CREATE TYPE device_type AS ENUM ('desktop','mobile'),
CREATE TYPE visibility  AS ENUM ('private','global'),

CREATE TABLE users (
  id         TEXT PRIMARY KEY,
  email      TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
),

CREATE TABLE api_keys (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id),
  key_hash   BYTEA NOT NULL, -- argon2/bcrypt
  name       TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ
),

CREATE TABLE device_profiles (
  id             TEXT PRIMARY KEY,
  owner_id       TEXT NOT NULL REFERENCES users(id),
  name           CITEXT NOT NULL,
  device_type    device_type NOT NULL,
  width          INT NOT NULL,
  height         INT NOT NULL,
  user_agent     TEXT NOT NULL,
  country        TEXT NOT NULL,
  custom_headers JSONB,
  is_template    BOOLEAN NOT NULL DEFAULT FALSE,
  visibility     visibility NOT NULL DEFAULT 'private',
  version        INT NOT NULL DEFAULT 1,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at     TIMESTAMPTZ,
  CONSTRAINT chk_window  CHECK (width BETWEEN 1 AND 10000 AND height BETWEEN 1 AND 10000),
  CONSTRAINT chk_country CHECK (country ~ '^[a-z]{2}$')
),

CREATE TABLE device_profile_versions (
  profile_id TEXT NOT NULL REFERENCES device_profiles(id),
  version    INT  NOT NULL,
  snapshot   JSONB NOT NULL,
  changed_by TEXT NOT NULL REFERENCES users(id),
  changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (profile_id, version)
),

CREATE INDEX idx_profiles_owner ON device_profiles(owner_id) WHERE deleted_at IS NULL,
CREATE INDEX idx_profiles_type  ON device_profiles(device_type) WHERE deleted_at IS NULL,
CREATE INDEX idx_profiles_tmpl  ON device_profiles(is_template) WHERE deleted_at IS NULL,

CREATE UNIQUE INDEX uniq_owner_name_not_deleted
  ON device_profiles(owner_id, name)
  WHERE deleted_at IS NULL,

-- updated_at auto-touch trigger
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = now(), RETURN NEW, END, $$ LANGUAGE plpgsql,
CREATE TRIGGER touch_profiles BEFORE UPDATE ON device_profiles
  FOR EACH ROW EXECUTE FUNCTION set_updated_at(),

-- idempotency store for POST /v1/device-profiles
CREATE TABLE idempotency_keys (
  key        TEXT PRIMARY KEY,
  owner_id   TEXT NOT NULL REFERENCES users(id),
  response   JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
),
```

**Notes:** soft delete via `deleted_at`, validate header keys/sizes in the app, consider encrypting sensitive header values.

---

## 4) API Design (v1)

**Base path:** `/v1/device-profiles`  
**Auth:** `X-API-Key: <key>` (scopes to owner). Rate limiting per key.

**Pagination:** cursor-based `?limit=20&cursor=…` → `{ "data": [...], "next_cursor": "…" }`. Stable ordering `ORDER BY created_at, id`. Cursor encodes the last tuple (e.g., base64 of `created_at|id`).

**Errors:** Problem+JSON with fields  
`{ "type": "about:blank", "title": "Invalid Request", "status": 400, "detail": "...", "request_id": "…", "errors": [ { "field": "window.width", "message": ">= 1" } ] }`

**Endpoints:**
- **POST `/`** – Create profile (full body, or `{template_id, overrides}`), supports `Idempotency-Key`  
  _Idempotency semantics:_ same `Idempotency-Key` within TTL (e.g., 24h) returns the original response.
- **GET `/`** – List my profiles (filters: `is_template`, `device_type`, `country`, `q`=name-prefix)
- **GET `/{id}`** – Fetch one (owner or global template)
- **PATCH `/{id}`** – Partial update, **optimistic concurrency required**  
  Client sends `If-Match: <current-version>` (or includes `version` in body).  
  Server updates with `WHERE id=? AND owner_id=? AND version=?`, bumps `version = version+1`, writes snapshot, on mismatch return **412 Precondition Failed**.
- **DELETE `/{id}`** – Soft delete
- **POST `/validate`** – Validate only (optional)
- **POST `/templates:seed`** – Admin seed (optional)

---

## 5) Architecture Design

**Recommended:** ECS Fargate + RDS (PostgreSQL).

**Components**
- API service (FastAPI) on Fargate behind an ALB (2 AZs), ALB health checks `/readyz`
- RDS Postgres in private subnets, KMS-encrypted, Multi-AZ
- AWS Secrets Manager for DB creds and keys
- **CloudWatch** Logs (structured JSON), **CloudWatch Metrics** via **Embedded Metric Format (EMF)**, **CloudWatch Alarms & Dashboards**, **AWS X-Ray** tracing
- Enable **ECS/ALB/RDS Container Insights** for infra metrics and automatic dashboards
- WAF on the ALB, least-privilege IAM, private VPC with NAT only when required, HSTS enabled, CORS as required

**Security notes**
- API keys are stored **hashed** (bcrypt/Argon2), support rotation and revocation.
- Never log `custom_headers.value`, mask/redact in error paths and traces.

**Why this:** familiar workflow, secure defaults, easy migrations. Can scale by adding tasks, Postgres read replicas, and caching (Redis). If you want zero server management, use API Gateway + Lambda + DynamoDB, at the cost of more data modeling.

---

## 6) Observability (AWS CloudWatch) — Implementation Notes

### Logging (CloudWatch Logs)
- Output **structured JSON** to stdout with fields: `timestamp`, `level`, `request_id`, `user_id`, `route`, `method`, `status`, `duration_ms`, `error_code` (if any).
- Ship logs via ECS `awslogs` driver or FireLens to **CloudWatch Logs**, set retention (e.g., 30d) by environment.
- **Never** log `custom_headers.value`. Include X-Ray **trace ID** in each log line for correlation.

### Metrics (CloudWatch Metrics via EMF)
- Emit application metrics in **Embedded Metric Format (EMF)** with namespace `ZenRows/DeviceProfiles`
  and dimensions `Service=device-profiles-api`, `Env`.
- Core metrics:
  - `RequestCount` (Count)
  - `LatencyMs` (Milliseconds) — record per request, chart p50/p95/p99
  - `Errors4xx` (Count), `Errors5xx` (Count)
  - `DBQueryMs` (Milliseconds) — optional
- **Example EMF payload (single log line):**
```
{
  "_aws": {
    "Timestamp": 0,
    "CloudWatchMetrics": [{
      "Namespace": "ZenRows/DeviceProfiles",
      "Dimensions": [["Service","Env"]],
      "Metrics": [
        {"Name": "RequestCount", "Unit": "Count"},
        {"Name": "LatencyMs",   "Unit": "Milliseconds"},
        {"Name": "Errors4xx",   "Unit": "Count"},
        {"Name": "Errors5xx",   "Unit": "Count"}
      ]
    }]
  },
  "Service": "device-profiles-api",
  "Env": "prod",
  "RequestCount": 1,
  "LatencyMs": 42
}
```

### Tracing (AWS X-Ray)
- Use the X-Ray SDK middleware (Gin/FastAPI) to capture incoming requests and downstream Postgres calls.
- Sampling: ~5–10% in prod, 100% in dev. Propagate trace context to logs.

### Alarms & Dashboards (CloudWatch)
- **Alarms (suggested):**
  - 5xx rate > **1%** for 5 minutes
  - p95 `LatencyMs` > **300ms** for 5 minutes
  - RDS CPU > **80%** for 10 minutes, free storage < **20%**
  - ECS service **RunningTaskCount < DesiredCount**
  - ALB **TargetResponseTime p95 > 500ms**
- **Dashboards:**
  - App metrics (RequestCount, Errors4xx/5xx, LatencyMs p95)
  - Infra (ECS CPU/Mem, ALB TargetResponseTime, RDS CPU/Connections)

**Notes:** This design **removes the need for a `/metrics` endpoint** and Prometheus, all metrics flow to CloudWatch via EMF.

---
