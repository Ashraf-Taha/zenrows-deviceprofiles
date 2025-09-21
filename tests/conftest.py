import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

from app.auth.crypto import generate_api_key, hash_key


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
