from fastapi.testclient import TestClient

from app.main import create_app


def test_given_same_idempotency_key_when_post_then_same_response(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)

    body = {
        "name": "DupP",
        "device_type": "desktop",
        "window": {"width": 100, "height": 100},
        "user_agent": "UA",
        "country": "us",
    }

    headers = {"X-API-Key": raw, "Idempotency-Key": "idem-123"}
    r1 = client.post("/v1/device-profiles/", json=body, headers=headers)
    r2 = client.post("/v1/device-profiles/", json=body, headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    d1 = r1.json()
    d2 = r2.json()
    assert d1["id"] == d2["id"]
