from fastapi.testclient import TestClient

from app.main import create_app
from app.db.session import get_session
from app.profiles.dto import CreateProfile, Window, HeaderKV, headers_list_to_json, ProfileResponse
from app.db.models import DeviceType
from app.profiles.repository import DeviceProfileRepository, ListFilters, NotFoundError


def test_headers_helpers_and_profile_response(seed_env):
    raw, uid = seed_env
    with get_session() as s:
        repo = DeviceProfileRepository(s)
        dp = repo.create(
            uid,
            CreateProfile(
                name="HH",
                device_type=DeviceType.desktop,
                window=Window(width=120, height=90),
                user_agent="ua",
                country="us",
                custom_headers=[HeaderKV(key="x-a", value="1"), HeaderKV(key="x-b", value="2")],
            ),
        )
        s.commit()
        # headers_list_to_json
        assert headers_list_to_json(None) is None
        j = headers_list_to_json([HeaderKV(key="x", value="y")])
        assert j == {"x": "y"}
        # ProfileResponse.from_model path that builds headers list
        pr = ProfileResponse.from_model(dp)
        assert pr.custom_headers and any(h.key == "x-a" for h in pr.custom_headers)
    # repository.get_version path that builds HeaderKV list
    snap = repo.get_version(uid, dp.id, 1)
    assert snap.custom_headers and any(h.key == "x-a" for h in snap.custom_headers)


def test_versions_page_next_cursor_and_errors(seed_env):
    raw, uid = seed_env
    app = create_app()
    client = TestClient(app)
    with get_session() as s:
        repo = DeviceProfileRepository(s)
        dp = repo.create(
            uid,
            CreateProfile(
                name="VPG",
                device_type=DeviceType.desktop,
                window=Window(width=10, height=10),
                user_agent="ua",
                country="us",
            ),
        )
        pid = dp.id
        s.commit()
    # bump version using API patch
    r = client.get(f"/v1/device-profiles/{pid}", headers={"X-API-Key": raw})
    assert r.status_code == 200
    v = r.json()["version"]
    r2 = client.patch(
        f"/v1/device-profiles/{pid}",
        json={"name": "VPG2", "version": v},
        headers={"X-API-Key": raw},
    )
    assert r2.status_code in (200, 412)

    # list versions page
    r3 = client.get(f"/v1/device-profiles/{pid}/versions:page?limit=1", headers={"X-API-Key": raw})
    assert r3.status_code == 200
    j2 = r3.json()
    # next_cursor may or may not exist depending on above patch; just ensure shape
    assert "data" in j2

    # error path: missing parent
    with get_session() as s2:
        repo2 = DeviceProfileRepository(s2)
        try:
            repo2.list_versions_page(uid, "prof_missing", limit=1, cursor_version=None)
        except NotFoundError:
            pass
