from fastapi.testclient import TestClient

from app.main import create_app


client = TestClient(create_app())


def test_given_app_when_get_healthz_then_ok():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_given_app_when_get_readyz_then_ready():
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}
