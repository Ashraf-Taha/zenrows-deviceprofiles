from fastapi.testclient import TestClient

from app.main import create_app


def test_list_profiles_invalid_cursor_400(seed_env):
    raw, _ = seed_env
    client = TestClient(create_app())
    r = client.get("/v1/device-profiles?cursor=notb64", headers={"X-API-Key": raw})
    assert r.status_code == 400


def test_get_version_not_found_404(seed_env):
    raw, _ = seed_env
    client = TestClient(create_app())
    r = client.get("/v1/device-profiles/prof_missing/versions/1", headers={"X-API-Key": raw})
    assert r.status_code == 404


def test_versions_page_not_found_404(seed_env):
    raw, _ = seed_env
    client = TestClient(create_app())
    r = client.get("/v1/device-profiles/prof_missing/versions:page", headers={"X-API-Key": raw})
    assert r.status_code == 404
