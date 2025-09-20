import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import create_app
from app.core.idempotency import IdempotencyStore
from app.db.session import get_session
from app.db.models import IdempotencyKey
from app.profiles.dto import HeaderKV, CreateProfile, UpdateProfile, ProfileResponse, Window, headers_list_to_json
from app.db.models import DeviceProfile, DeviceType, Visibility
from app.profiles.repository import DeviceProfileRepository, NotFoundError, ConflictError
from app.profiles.pipeline import GetValidator, GetRequest, DeleteValidator, DeleteRequest, PatchValidator, PatchRequest
from fastapi import Request
from sqlalchemy.orm import Session
from tests.test_profiles import seed_env


def test_given_duplicate_name_when_create_then_conflict(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    body = {
        "name": "DupName",
        "device_type": "desktop",
        "window": {"width": 100, "height": 100},
        "user_agent": "UA",
        "country": "us",
    }
    r1 = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    assert r1.status_code == 200
    r2 = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    assert r2.status_code == 409


def test_given_unknown_id_when_get_then_404(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    r = client.get("/v1/device-profiles/prof_unknown", headers={"X-API-Key": raw})
    assert r.status_code == 404


def test_given_unknown_id_when_delete_then_404(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    r = client.delete("/v1/device-profiles/prof_unknown", headers={"X-API-Key": raw})
    assert r.status_code == 404


def test_given_ttl_zero_when_get_idempotency_then_miss(seed_env):
    raw, uid = seed_env
    with get_session() as s:
        store = IdempotencyStore(s)
        store.save(uid, "k1", {"ok": True})
        s.commit()
        s.expunge_all()
        miss = IdempotencyStore(s, ttl_seconds=0).get(uid, "k1")
        assert miss is None
    none = IdempotencyStore(s).get(uid, "does-not-exist")
    assert none is None


def test_dto_header_key_validation_errors():
    with pytest.raises(ValueError):
        HeaderKV(key="Host", value="x")
    with pytest.raises(ValueError):
        HeaderKV(key="  ", value="x")


def test_dto_country_validation_errors():
    with pytest.raises(ValueError):
        CreateProfile(
            name="n",
            device_type=DeviceType.desktop,
            window=Window(width=10, height=10),
            user_agent="ua",
            country="xx",
        )


def test_headers_list_to_json_handles_none():
    assert headers_list_to_json(None) is None


def test_create_profile_country_normalizes_case():
    cp = CreateProfile(
        name="n",
        device_type=DeviceType.desktop,
        window=Window(width=10, height=10),
        user_agent="ua",
        country="US",
    )
    assert cp.country == "us"


def test_update_profile_requires_changes():
    with pytest.raises(ValueError):
        UpdateProfile(version=1)


def test_profile_response_from_model_maps_headers(seed_env):
    raw, uid = seed_env
    with get_session() as s:
        repo = DeviceProfileRepository(s)
        p = repo.create(
            uid,
            CreateProfile(
                name="M",
                device_type=DeviceType.desktop,
                window=Window(width=10, height=11),
                user_agent="ua",
                country="us",
                custom_headers=[HeaderKV(key="x-a", value="b")],
                is_template=True,
                visibility=Visibility.private,
            ),
        )
        s.commit()
        resp = ProfileResponse.from_model(p)
        assert any(h.key == "x-a" and h.value == "b" for h in (resp.custom_headers or []))


def test_repository_get_not_found(seed_env):
    raw, uid = seed_env
    with get_session() as s:
        repo = DeviceProfileRepository(s)
        with pytest.raises(NotFoundError):
            repo.get_scoped(uid, "prof_missing")


def test_repository_create_conflict_raised(seed_env):
    raw, uid = seed_env
    with get_session() as s:
        repo = DeviceProfileRepository(s)
        repo.create(
            uid,
            CreateProfile(
                name="C1",
                device_type=DeviceType.desktop,
                window=Window(width=10, height=10),
                user_agent="ua",
                country="us",
            ),
        )
        s.flush()
        with pytest.raises(ConflictError):
            repo.create(
                uid,
                CreateProfile(
                    name="C1",
                    device_type=DeviceType.desktop,
                    window=Window(width=10, height=10),
                    user_agent="ua",
                    country="us",
                ),
            )


def test_repository_update_all_fields_and_list_filters(seed_env):
    raw, uid = seed_env
    with get_session() as s:
        repo = DeviceProfileRepository(s)
        p = repo.create(
            uid,
            CreateProfile(
                name="LF1",
                device_type=DeviceType.desktop,
                window=Window(width=10, height=10),
                user_agent="ua",
                country="us",
            ),
        )
        s.flush()
        repo.create(
            uid,
            CreateProfile(
                name="LF2",
                device_type=DeviceType.mobile,
                window=Window(width=11, height=12),
                user_agent="ua2",
                country="gb",
                is_template=True,
            ),
        )
        s.flush()
        upd = UpdateProfile(
            name="LF1-upd",
            device_type=DeviceType.mobile,
            window=Window(width=13, height=14),
            user_agent="ua3",
            country="de",
            custom_headers=[HeaderKV(key="x-k", value="v")],
            is_template=True,
            visibility=Visibility.private,
            version=p.version,
        )
        old_ver = p.version
        row = repo.update_optimistic(uid, p.id, upd)
        s.flush()
        assert row.version == old_ver + 1
        assert row.device_type == DeviceType.mobile
        assert row.width == 13 and row.height == 14
        assert row.user_agent == "ua3"
        assert row.country == "de"
        assert (row.custom_headers or {}).get("x-k") == "v"
        assert row.is_template is True

        from app.profiles.repository import ListFilters
        rows = repo.list_scoped(uid, ListFilters(is_template=True, device_type="mobile", country="gb", q="LF", limit=50))
        assert isinstance(rows, list)


def test_patch_conflict_branch_returns_409(monkeypatch, seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    body = {
        "name": "P2",
        "device_type": "desktop",
        "window": {"width": 100, "height": 100},
        "user_agent": "UA",
        "country": "us",
    }
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    pid = r.json()["id"]
    ver = r.json()["version"]

    from app.profiles.repository import DeviceProfileRepository, ConflictError as RepoConflict

    def boom(self, owner_id, profile_id, data):
        raise RepoConflict("conflict")

    monkeypatch.setattr(DeviceProfileRepository, "update_optimistic", boom)
    r2 = client.patch(f"/v1/device-profiles/{pid}", json={"name": "X", "version": ver}, headers={"X-API-Key": raw})
    assert r2.status_code == 409


def test_idempotency_get_handles_naive_datetime(monkeypatch):
    from datetime import datetime
    with get_session() as s:
        store = IdempotencyStore(s, ttl_seconds=None)

        class Row:
            response = {"ok": True}
            created_at = datetime(2020, 1, 1)

        class FakeScalar:
            def first(self):
                return Row()

        class FakeResult:
            def scalars(self):
                return FakeScalar()

        monkeypatch.setattr(s, "execute", lambda q: FakeResult())
        val = store.get("o", "k")
        assert val == {"ok": True}


def test_soft_delete_wrong_owner_raises_not_found(seed_env):
    raw, uid = seed_env
    # create a second user and try to delete other's profile
    with get_session() as s:
        repo = DeviceProfileRepository(s)
        p = repo.create(
            uid,
            CreateProfile(
                name="OWN1",
                device_type=DeviceType.desktop,
                window=Window(width=10, height=10),
                user_agent="ua",
                country="us",
            ),
        )
        s.flush()
        other = f"usr_{uuid.uuid4().hex[:8]}"
        # insert other user
        eng = create_engine(os.environ["DATABASE_URL"], isolation_level="AUTOCOMMIT")
        with eng.connect() as conn:
            conn.execute(text("INSERT INTO users(id,email) VALUES (:i,:e)"), {"i": other, "e": f"{other}@x.z"})
        with pytest.raises(NotFoundError):
            repo.soft_delete(other, p.id)


def test_validators_raise_for_missing_ids_and_version():
    with pytest.raises(ValueError):
        GetValidator().validate(GetRequest(user_id="u", profile_id=""))
    with pytest.raises(ValueError):
        DeleteValidator().validate(DeleteRequest(owner_id="u", profile_id=""))
    with pytest.raises(ValueError):
        PatchValidator().validate(PatchRequest(owner_id="u", profile_id="p", payload=UpdateProfile()))
    with pytest.raises(ValueError):
        PatchValidator().validate(PatchRequest(owner_id="u", profile_id="p", payload=UpdateProfile(name="x")))


def test_user_id_helper_unauthorized():
    from app.api.routes.device_profiles import _user_id

    class Dummy:
        state = type("S", (), {})()

    req = Dummy()
    with pytest.raises(Exception):
        _user_id(req)


def test_update_optimistic_execution_failure_raises_precondition(monkeypatch, seed_env):
    raw, uid = seed_env
    with get_session() as s:
        repo = DeviceProfileRepository(s)
        p = repo.create(
            uid,
            CreateProfile(
                name="E1",
                device_type=DeviceType.desktop,
                window=Window(width=10, height=10),
                user_agent="ua",
                country="us",
            ),
        )
        s.flush()

        orig_execute = s.execute

        def boom(stmt):
            from sqlalchemy.sql.dml import Update as SAUpdate
            if isinstance(stmt, SAUpdate):
                raise RuntimeError("db error")
            return orig_execute(stmt)

        monkeypatch.setattr(s, "execute", boom)
        from app.profiles.repository import PreconditionFailed
        with pytest.raises(PreconditionFailed):
            # hit the broad except in repository.update_optimistic -> PreconditionFailed
            repo.update_optimistic(uid, p.id, UpdateProfile(name="x", version=p.version))


def test_repository_soft_delete_success(seed_env):
    raw, uid = seed_env
    with get_session() as s:
        repo = DeviceProfileRepository(s)
        p = repo.create(
            uid,
            CreateProfile(
                name="DEL1",
                device_type=DeviceType.desktop,
                window=Window(width=10, height=10),
                user_agent="ua",
                country="us",
            ),
        )
        s.flush()
        repo.soft_delete(uid, p.id)
        s.flush()
        # ensure it's marked deleted by fetching list and ensuring it's excluded
        from app.profiles.repository import ListFilters
        rows = repo.list_scoped(uid, ListFilters(limit=50))
        assert all(r.id != p.id for r in rows)


def test_update_optimistic_wrong_owner_raises_not_found(monkeypatch, seed_env):
    raw, uid = seed_env
    with get_session() as s:
        repo = DeviceProfileRepository(s)
        p = repo.create(
            uid,
            CreateProfile(
                name="WO1",
                device_type=DeviceType.desktop,
                window=Window(width=10, height=10),
                user_agent="ua",
                country="us",
            ),
        )
        s.flush()

        class FakeRow:
            owner_id = "other"
            version = p.version

        monkeypatch.setattr(DeviceProfileRepository, "get_scoped", lambda self, a, b: FakeRow())
        from app.profiles.repository import NotFoundError
        with pytest.raises(NotFoundError):
            repo.update_optimistic(uid, p.id, UpdateProfile(name="x", version=p.version))


def test_session_url_builder_uses_env_defaults(monkeypatch):
    for k in ["DATABASE_URL", "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DB_HOST", "h")
    monkeypatch.setenv("DB_PORT", "p")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "w")
    monkeypatch.setenv("DB_NAME", "d")
    from app.db import session as sess

    url = sess._current_db_url()
    assert url == "postgresql+psycopg://u:w@h:p/d"
