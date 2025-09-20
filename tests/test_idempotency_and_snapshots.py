from fastapi.testclient import TestClient
from sqlalchemy import text, create_engine
import os

from app.main import create_app
from app.core.idempotency import IdempotencyStore
from app.db.session import get_session
from app.profiles.dto import UpdateProfile, Window
from app.profiles.pipeline import IdentityResponse
from app.db.models import DeviceType
from tests.test_profiles import seed_env


def test_given_positive_ttl_when_get_then_returns_response(seed_env):
    raw, uid = seed_env
    with get_session() as s:
        store = IdempotencyStore(s)
        store.save(uid, "k2", {"ok": True})
        s.commit()
        s.expunge_all()
        got = IdempotencyStore(s, ttl_seconds=3600).get(uid, "k2")
        assert got == {"ok": True}


def test_given_naive_datetime_when_get_with_active_ttl_then_returns(monkeypatch):
    from datetime import datetime
    with get_session() as s:
        store = IdempotencyStore(s, ttl_seconds=3600)

        class Row:
            response = {"ok": True}
            created_at = datetime.utcnow()

        class FakeScalar:
            def first(self):
                return Row()

        class FakeResult:
            def scalars(self):
                return FakeScalar()

        monkeypatch.setattr(s, "execute", lambda q: FakeResult())
        got = store.get("o", "k")
        assert got == {"ok": True}


def test_given_profile_created_when_updated_then_version_snapshots_increment(seed_env):
    raw, uid = seed_env
    with get_session() as s:
        from app.profiles.repository import DeviceProfileRepository
        from app.profiles.dto import CreateProfile, HeaderKV
        from app.db.models import Visibility
        repo = DeviceProfileRepository(s)
        p = repo.create(
            uid,
            CreateProfile(
                name="SNAP1",
                device_type=DeviceType.desktop,
                window=Window(width=10, height=10),
                user_agent="ua",
                country="us",
                custom_headers=[HeaderKV(key="x", value="y")],
                is_template=True,
                visibility=Visibility.private,
            ),
        )
        s.flush()
        updated = repo.update_optimistic(uid, p.id, UpdateProfile(name="SNAP2", version=p.version))
        s.flush()
        pid = p.id
        s.commit()
        assert updated.name == "SNAP2"
    eng = create_engine(os.environ["DATABASE_URL"], isolation_level="AUTOCOMMIT")
    with eng.connect() as conn:
        cnt = conn.execute(text("SELECT COUNT(*) FROM device_profile_versions WHERE profile_id=:pid"), {"pid": pid}).scalar()
        assert cnt and cnt >= 2


def test_given_unknown_profile_when_patch_then_404(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    payload = {"name": "x", "version": 1}
    r = client.patch("/v1/device-profiles/prof_missing", json=payload, headers={"X-API-Key": raw})
    assert r.status_code == 404


def test_given_uppercase_country_when_update_then_normalized():
    u = UpdateProfile(name="a", version=1, country="DE", window=Window(width=1, height=1), device_type=DeviceType.desktop)
    assert u.country == "de"


def test_given_identity_response_when_transform_then_passthrough():
    ir = IdentityResponse()
    class R:
        pass
    x = R()
    assert ir.transform(x) is x


def test_given_expired_ttl_when_get_with_aware_datetime_then_none(monkeypatch):
    from datetime import datetime, timezone, timedelta
    with get_session() as s:
        store = IdempotencyStore(s, ttl_seconds=1)

        class Row:
            response = {"ok": True}
            created_at = datetime.now(timezone.utc) - timedelta(days=2)

        class FakeScalar:
            def first(self):
                return Row()

        class FakeResult:
            def scalars(self):
                return FakeScalar()

        monkeypatch.setattr(s, "execute", lambda q: FakeResult())
        val = store.get("o", "k")
        assert val is None
