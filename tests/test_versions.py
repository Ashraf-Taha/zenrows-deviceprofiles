import os
from fastapi.testclient import TestClient

from app.main import create_app


def test_given_profile_with_updates_when_get_versions_then_returns_in_order(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)

    body = {
        "name": "V1",
        "device_type": "desktop",
        "window": {"width": 100, "height": 100},
        "user_agent": "UA",
        "country": "us",
    }
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    assert r.status_code == 200
    pid = r.json()["id"]
    v = r.json()["version"]

    r2 = client.patch(f"/v1/device-profiles/{pid}", json={"name": "V2", "version": v}, headers={"X-API-Key": raw})
    assert r2.status_code == 200

    r3 = client.get(f"/v1/device-profiles/{pid}/versions", headers={"X-API-Key": raw})
    assert r3.status_code == 200
    arr = r3.json()
    assert isinstance(arr, list)
    assert len(arr) >= 2
    assert arr[0]["version"] == 1
    assert arr[-1]["version"] == 2


def test_given_unknown_profile_when_get_versions_then_404(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    r = client.get("/v1/device-profiles/prof_missing/versions", headers={"X-API-Key": raw})
    assert r.status_code == 404


def test_given_profile_with_many_versions_when_page_then_paginates(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    body = {
        "name": "PAG1",
        "device_type": "desktop",
        "window": {"width": 10, "height": 10},
        "user_agent": "UA",
        "country": "us",
    }
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    pid = r.json()["id"]
    v = r.json()["version"]
    for i in range(5):
        client.patch(
            f"/v1/device-profiles/{pid}",
            json={"name": f"PAG{i}", "version": v},
            headers={"X-API-Key": raw},
        )
        v += 1
    p1 = client.get(f"/v1/device-profiles/{pid}/versions:page?limit=3", headers={"X-API-Key": raw})
    assert p1.status_code == 200
    data1 = p1.json()
    assert len(data1["data"]) == 3
    cur = data1["next_cursor"]
    p2 = client.get(f"/v1/device-profiles/{pid}/versions:page?limit=3&cursor={cur}", headers={"X-API-Key": raw})
    assert p2.status_code == 200
    data2 = p2.json()
    assert len(data2["data"]) >= 1