import base64
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import create_app
from app.db.session import get_session
from app.profiles.dto import CreateProfile, Window
from app.db.models import DeviceType
from app.profiles.repository import DeviceProfileRepository, ListFilters
# seed_env provided via tests/conftest.py


def _b64(ts: datetime, pid: str) -> str:
    raw = f"{ts.isoformat()}|{pid}".encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def test_given_invalid_params_when_list_then_400(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    r = client.get("/v1/device-profiles?limit=0", headers={"X-API-Key": raw})
    assert r.status_code == 400
    r2 = client.get("/v1/device-profiles?device_type=tablet", headers={"X-API-Key": raw})
    assert r2.status_code == 400
    r3 = client.get("/v1/device-profiles?country=xx", headers={"X-API-Key": raw})
    assert r3.status_code == 400
    r4 = client.get("/v1/device-profiles?cursor=bad", headers={"X-API-Key": raw})
    assert r4.status_code == 400


def test_given_many_items_when_list_then_cursor_pages(seed_env):
    raw, uid = seed_env
    app = create_app()
    client = TestClient(app)
    with get_session() as s:
        repo = DeviceProfileRepository(s)
        created = []
        for i in range(5):
            p = repo.create(
                uid,
                CreateProfile(
                    name=f"P{i}",
                    device_type=DeviceType.desktop,
                    window=Window(width=100 + i, height=100 + i),
                    user_agent="ua",
                    country="us",
                ),
            )
            s.flush()
            created.append(p)
        s.commit()
    r1 = client.get("/v1/device-profiles?limit=2", headers={"X-API-Key": raw})
    assert r1.status_code == 200
    j1 = r1.json()
    assert len(j1["data"]) <= 2
    cur = j1.get("next_cursor")
    if cur:
        r2 = client.get(f"/v1/device-profiles?limit=2&cursor={cur}", headers={"X-API-Key": raw})
        assert r2.status_code == 200
        j2 = r2.json()
        assert isinstance(j2.get("data", []), list)


def test_repository_cursor_pagination_orders_and_advances(seed_env):
    raw, uid = seed_env
    with get_session() as s:
        repo = DeviceProfileRepository(s)
    repo.create(uid, CreateProfile(name="A", device_type=DeviceType.desktop, window=Window(width=1, height=1), user_agent="ua", country="us"))
    s.flush()
    repo.create(uid, CreateProfile(name="B", device_type=DeviceType.desktop, window=Window(width=2, height=2), user_agent="ua", country="us"))
    s.flush()
    rows, nxt = repo.list_scoped_page(uid, ListFilters(limit=1))
    assert len(rows) == 1
    assert nxt is not None
    rows2, nxt2 = repo.list_scoped_page(uid, ListFilters(limit=1, cursor=nxt))
    assert len(rows2) == 1
    assert not nxt2 or nxt2[1] != nxt[1]
