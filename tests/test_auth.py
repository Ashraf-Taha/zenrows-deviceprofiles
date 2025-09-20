import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text, create_engine
from alembic.config import Config
from alembic import command

from app.main import create_app
from fastapi import APIRouter, Request
from app.auth.crypto import generate_api_key, hash_key


def _make_url(db_name: str) -> str:
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER", "postgres")
    pwd = os.environ.get("DB_PASSWORD", "postgres")
    return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db_name}"


@pytest.fixture(scope="module")
def seeded_key():
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


def test_given_missing_key_when_request_then_401(seeded_key):
    app = create_app()
    router = APIRouter()
    @router.get("/protected")
    def protected(request: Request):
        return {"user_id": getattr(request.state, "user_id", None)}
    app.include_router(router)
    client = TestClient(app)
    r = client.get("/readyz")
    assert r.status_code == 200
    r = client.get("/protected")
    assert r.status_code == 401


def test_given_valid_key_when_request_then_user_attached(seeded_key):
    raw, uid = seeded_key
    app = create_app()
    router = APIRouter()
    @router.get("/protected")
    def protected(request: Request):
        return {"user_id": getattr(request.state, "user_id", None)}
    app.include_router(router)
    client = TestClient(app)
    r = client.get("/protected", headers={"X-API-Key": raw})
    assert r.status_code == 200
    assert r.json()["user_id"] == uid


def test_given_revoked_key_when_request_then_401(seeded_key):
    raw, uid = seeded_key
    eng = create_engine(os.environ["DATABASE_URL"], isolation_level="AUTOCOMMIT")
    with eng.connect() as conn:
        conn.execute(text("UPDATE api_keys SET revoked_at=now()"))
    app = create_app()
    router = APIRouter()
    @router.get("/protected")
    def protected(request: Request):
        return {"user_id": getattr(request.state, "user_id", None)}
    app.include_router(router)
    client = TestClient(app)
    r = client.get("/protected", headers={"X-API-Key": raw})
    assert r.status_code == 401
