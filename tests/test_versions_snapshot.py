from fastapi.testclient import TestClient

from app.main import create_app


def test_given_profile_when_get_profile_then_etag_header_present(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    body = {
        "name": "E1",
        "device_type": "desktop",
        "window": {"width": 100, "height": 100},
        "user_agent": "UA",
        "country": "us",
    }
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    pid = r.json()["id"]
    g = client.get(f"/v1/device-profiles/{pid}", headers={"X-API-Key": raw})
    assert g.status_code == 200
    assert "etag" in {k.lower() for k in g.headers.keys()}


def test_given_known_version_when_get_snapshot_then_returns_snapshot(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    body = {
        "name": "SV1",
        "device_type": "desktop",
        "window": {"width": 100, "height": 100},
        "user_agent": "UA",
        "country": "us",
    }
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    pid = r.json()["id"]
    v = r.json()["version"]
    s = client.get(f"/v1/device-profiles/{pid}/versions/{v}", headers={"X-API-Key": raw})
    assert s.status_code == 200
    data = s.json()
    assert data["id"] == pid
    assert data["version"] == v


def test_given_matching_etag_when_get_profile_then_304(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    body = {
        "name": "E2",
        "device_type": "desktop",
        "window": {"width": 100, "height": 100},
        "user_agent": "UA",
        "country": "us",
    }
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    pid = r.json()["id"]
    g1 = client.get(f"/v1/device-profiles/{pid}", headers={"X-API-Key": raw})
    etag = g1.headers.get("ETag")
    g2 = client.get(f"/v1/device-profiles/{pid}", headers={"X-API-Key": raw, "If-None-Match": etag})
    assert g2.status_code == 304