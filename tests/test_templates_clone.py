import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

from app.main import create_app
from app.auth.crypto import generate_api_key, hash_key
from app.db.models import DeviceType


def _make_url(db_name: str) -> str:
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER", "postgres")
    pwd = os.environ.get("DB_PASSWORD", "postgres")
    return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db_name}"


@pytest.fixture(scope="module")
def seed_env():
    try:
        test_db = f"zenrows_test_{uuid.uuid4().hex[:8]}"
        admin = create_engine(_make_url("postgres"), isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f"CREATE DATABASE {test_db}"))
        os.environ["DATABASE_URL"] = _make_url(test_db)
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")

        raw, prefix = generate_api_key()
        uid = f"usr_{uuid.uuid4().hex[:8]}"
        kid = f"key_{uuid.uuid4().hex[:8]}"
        eng = create_engine(os.environ["DATABASE_URL"], isolation_level="AUTOCOMMIT")
        with eng.connect() as conn:
            conn.execute(text("INSERT INTO users(id,email) VALUES (:i,:e)"), {"i": uid, "e": f"{uid}@x.z"})
            conn.execute(
                text(
                    "INSERT INTO api_keys(id,user_id,key_hash,key_prefix,name) VALUES (:id,:uid,:hash,:prefix,'t')"
                ),
                {"id": kid, "uid": uid, "hash": hash_key(raw), "prefix": prefix},
            )
        yield raw, uid
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Postgres not available: {exc}")
    finally:
        try:
            if "admin" in locals():
                with admin.connect() as conn:
                    try:
                        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db} WITH (FORCE)"))
                    except Exception:
                        pass
                admin.dispose()
        except Exception:
            pass


def test_given_seeded_templates_when_list_with_filter_then_templates_visible(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    from scripts.seed_templates import main as seed
    seed()
    r = client.get("/v1/device-profiles?is_template=true", headers={"X-API-Key": raw})
    assert r.status_code == 200
    body = r.json()
    data = body["data"] if isinstance(body, dict) else body
    assert any("Chrome on Windows" == i["name"] for i in data)


def test_given_template_when_clone_with_overrides_then_new_owned_profile(seed_env):
    raw, uid = seed_env
    app = create_app()
    client = TestClient(app)
    from scripts.seed_templates import main as seed
    seed()
    body = {
        "template_id": "tmpl_chrome_win",
        "overrides": {
            "name": "My Desktop",
            "country": "gb",
            "window": {"width": 1400, "height": 900},
        },
    }
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    assert r.status_code == 200
    data = r.json()
    assert data["owner_id"] == uid
    assert data["name"] == "My Desktop"
    assert data["country"] == "gb"
    assert data["window"]["width"] == 1400


def test_given_unknown_template_when_clone_then_404(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    body = {"template_id": "tmpl_missing"}
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    assert r.status_code == 404


def test_given_template_when_clone_without_overrides_then_defaults_used(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    from scripts.seed_templates import main as seed
    seed()
    body = {"template_id": "tmpl_iphone"}
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    assert r.status_code == 200
    data = r.json()
    assert data["is_template"] is False
    assert data["visibility"] == "private"
    assert data["name"].endswith(" Copy")


def test_given_invalid_override_country_when_clone_then_400(seed_env):
    raw, _ = seed_env
    app = create_app()
    client = TestClient(app)
    from scripts.seed_templates import main as seed
    seed()
    body = {"template_id": "tmpl_chrome_win", "overrides": {"country": "xx"}}
    r = client.post("/v1/device-profiles/", json=body, headers={"X-API-Key": raw})
    assert r.status_code in (400, 422)
