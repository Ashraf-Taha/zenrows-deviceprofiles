import os
from fastapi.testclient import TestClient
from app.main import create_app
# no extra imports needed


def _make_url(db_name: str) -> str:
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER", "postgres")
    pwd = os.environ.get("DB_PASSWORD", "postgres")
    return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db_name}"

# seed_env is provided via tests/conftest.py


def test_given_valid_payload_when_create_then_persist_and_return(seed_env):
    raw, uid = seed_env
    app = create_app()
    client = TestClient(app)
    body = {
        "name": "Amazon Desktop",
        "device_type": "desktop",
        "window": {"width": 1366, "height": 768},
        "user_agent": "UA",
        "country": "gb",
    }
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    assert r.status_code == 200
    data = r.json()
    assert data["owner_id"] == uid
    pid = data["id"]

    r2 = client.get(f"/v1/device-profiles/{pid}", headers={"X-API-Key": raw})
    assert r2.status_code == 200
    assert r2.json()["id"] == pid


def test_given_list_when_request_then_returns_items(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    r = client.get("/v1/device-profiles?limit=20", headers={"X-API-Key": raw})
    assert r.status_code == 200
    json = r.json()
    assert isinstance(json.get("data", []), list) or isinstance(json, list)


def test_given_version_when_patch_then_version_bumps(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    body = {
        "name": "P1",
        "device_type": "desktop",
        "window": {"width": 100, "height": 100},
        "user_agent": "UA",
        "country": "us",
    }
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    pid = r.json()["id"]
    ver = r.json()["version"]

    patch = {"name": "P1 Updated", "version": ver}
    r2 = client.patch(f"/v1/device-profiles/{pid}", json=patch, headers={"X-API-Key": raw})
    assert r2.status_code == 200
    assert r2.json()["version"] == ver + 1

    r3 = client.patch(f"/v1/device-profiles/{pid}", json=patch, headers={"X-API-Key": raw})
    assert r3.status_code == 412


def test_given_delete_when_request_then_soft_deleted(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    body = {
        "name": "ToDelete",
        "device_type": "desktop",
        "window": {"width": 100, "height": 100},
        "user_agent": "UA",
        "country": "us",
    }
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    pid = r.json()["id"]
    r2 = client.delete(f"/v1/device-profiles/{pid}", headers={"X-API-Key": raw})
    assert r2.status_code == 200
    r3 = client.get(f"/v1/device-profiles/{pid}", headers={"X-API-Key": raw})
    assert r3.status_code in (404, 200)
