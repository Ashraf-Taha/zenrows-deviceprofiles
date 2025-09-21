# Swagger Testing Playbook

This guide helps you validate the API via Swagger UI with real requests against the running containers.

Prereqs: Docker Desktop installed and running.

## 1) Start the stack

- From the repo root, run Docker Compose to start Postgres and the API. The API container runs migrations and seeds templates and an API key on boot.

  Notes:
  - The API will listen on http://localhost:8080
  - The seed script prints a new API key once on container start. Check the container logs to copy it.

## 2) Get the API key from logs

- Open the logs for the API container and copy the key:
  - Look for a line similar to: "Seeding API key (printed below, save it now):" followed by a long token.

## 3) Open Swagger UI

- Go to: http://localhost:8080/docs
- Click "Authorize" and paste the key into the value field; header name must be X-API-Key.
- Ensure "Persist Authorization" is on so the header sticks across calls.

## 4) Health endpoints

- GET /healthz → 200 {"status":"ok"}
- GET /readyz → 200 {"status":"ready"}

## 5) Device Profiles endpoints

All endpoints require X-API-Key set via Authorize, except health.

- POST /v1/device-profiles
  - Example body (new from scratch):
    {
      "name": "Amazon Desktop",
      "device_type": "desktop",
      "window": {"width": 1366, "height": 768},
      "user_agent": "Mozilla/5.0",
      "country": "gb",
      "custom_headers": [{"key":"accept-language","value":"en-GB"}]
    }
  - Or clone from template:
    {
      "template_id": "tmpl_chrome_win",
      "overrides": {"name": "My Chrome Windows"}
    }
  - Optional header: Idempotency-Key: any-unique-string

- GET /v1/device-profiles?limit=20
  - Supports filters: is_template, device_type, country, q (name prefix)

- GET /v1/device-profiles/{id}
  - Returns profile JSON with ETag set to current version.

- PATCH /v1/device-profiles/{id}
  - Include a minimal body plus the expected version for optimistic concurrency, e.g.:
    {
      "name": "Amazon Desktop v2",
      "version": 1
    }
  - On version mismatch, expect 412 Precondition Failed.

- DELETE /v1/device-profiles/{id}
  - Soft deletes the profile.

- GET /v1/device-profiles/{id}/versions
  - Lists version metadata.

- GET /v1/device-profiles/{id}/versions:page?limit=20
  - Lists version metadata with simple pagination via numeric cursor.

- GET /v1/device-profiles/{id}/versions/{version}
  - Returns the historical snapshot.

## 6) Common errors
- 401 missing_api_key or invalid_api_key when not authorized.
- 409 conflict for unique name per owner.
- 412 version_mismatch on stale update.
- 400 invalid_parameters on bad filters or cursor.
- 422 validation_error for DTO schema issues.

## 7) Cleanup/Re-run
- To restart cleanly, stop and remove containers; Postgres data is ephemeral unless you add a volume.
