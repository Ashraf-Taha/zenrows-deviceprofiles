from fastapi.testclient import TestClient

from app.main import create_app


def test_list_versions_invalid_params(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    # invalid version route param types and invalid page params
    r1 = client.get("/v1/device-profiles/prof_x/versions:page?limit=0", headers={"X-API-Key": raw})
    assert r1.status_code == 400
    r2 = client.get("/v1/device-profiles/prof_x/versions:page?limit=101", headers={"X-API-Key": raw})
    assert r2.status_code == 400


def test_get_profile_version_invalid_version_returns_400(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    body = {
        "name": "PV1",
        "device_type": "desktop",
        "window": {"width": 100, "height": 100},
        "user_agent": "UA",
        "country": "us",
    }
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    pid = r.json()["id"]
    r2 = client.get(f"/v1/device-profiles/{pid}/versions/0", headers={"X-API-Key": raw})
    assert r2.status_code == 400
