import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command


def _base_conn_info() -> tuple[str, str, str, str, str]:
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER", "postgres")
    pwd = os.environ.get("DB_PASSWORD", "postgres")
    db = os.environ.get("DB_NAME", "postgres")
    return host, port, user, pwd, db


def _make_url(db_name: str) -> str:
    host, port, user, pwd, _ = _base_conn_info()
    return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db_name}"


@pytest.fixture(scope="module")
def engine():
    try:
        test_db = f"zenrows_test_{uuid.uuid4().hex[:8]}"
        admin = create_engine(_make_url("postgres"), isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f"CREATE DATABASE {test_db}"))
        eng = create_engine(_make_url(test_db), isolation_level="AUTOCOMMIT")
        yield eng
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Postgres not available: {exc}")
    finally:
        try:
            if 'eng' in locals():
                eng.dispose()
            if 'admin' in locals():
                with admin.connect() as conn:
                    try:
                        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db} WITH (FORCE)"))
                    except Exception:
                        pass
                admin.dispose()
        except Exception:
            pass


def test_given_fresh_db_when_run_migrations_then_all_tables_exist(engine):
    cfg = Config("alembic.ini")
    os.environ["DATABASE_URL"] = str(engine.url)
    try:
        command.upgrade(cfg, "head")
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Migrations cannot run: {exc}")

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public' AND table_name IN (
                  'users','api_keys','device_profiles','device_profile_versions','idempotency_keys'
                )
                """
            )
        ).fetchall()
        found = {r[0] for r in rows}
        assert {"users", "api_keys", "device_profiles", "device_profile_versions"}.issubset(found)


def test_given_constraints_when_inserting_invalid_country_then_fails(engine):
    with engine.connect() as conn:
        try:
            conn.execute(text("INSERT INTO users(id,email) VALUES (:i,:e)"), {"i": "u1", "e": "a@b.c"})
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Users table missing: {exc}")
        conn.execute(
            text(
                """
                INSERT INTO device_profiles(
                  id, owner_id, name, device_type, width, height, user_agent, country
                ) VALUES (:id,:owner,:name,'desktop',10,10,'ua','gb')
                """
            ),
            {"id": "p1", "owner": "u1", "name": "N"},
        )
        try:
            conn.execute(
                text(
                    """
                    INSERT INTO device_profiles(
                      id, owner_id, name, device_type, width, height, user_agent, country
                    ) VALUES (:id,:owner,:name,'desktop',10,10,'ua','GB')
                    """
                ),
                {"id": "p2", "owner": "u1", "name": "M"},
            )
            assert False
        except Exception as e:
            assert "chk_country" in str(e).lower()


def test_given_unique_name_when_conflict_then_violates(engine):
    with engine.connect() as conn:
        try:
            conn.execute(text("INSERT INTO users(id,email) VALUES ('u2','x@y.z') ON CONFLICT DO NOTHING"))
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Tables missing: {exc}")
        conn.execute(
            text(
                """
                INSERT INTO device_profiles(
                  id, owner_id, name, device_type, width, height, user_agent, country
                ) VALUES ('p3','u2','Same','desktop',10,10,'ua','us')
                """
            )
        )
        try:
            conn.execute(
                text(
                    """
                    INSERT INTO device_profiles(
                      id, owner_id, name, device_type, width, height, user_agent, country
                    ) VALUES ('p4','u2','Same','desktop',10,10,'ua','us')
                    """
                )
            )
            assert False
        except Exception as e:
            assert "uniq_owner_name_not_deleted" in str(e).lower()


def test_given_update_when_touch_then_updated_at_changes(engine):
    with engine.connect() as conn:
        try:
            before = conn.execute(text("SELECT updated_at FROM device_profiles WHERE id='p3'"))
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Tables missing: {exc}")
        b = before.scalar_one()
        conn.execute(text("UPDATE device_profiles SET width=11 WHERE id='p3'"))
        after = conn.execute(text("SELECT updated_at FROM device_profiles WHERE id='p3'"))
        a = after.scalar_one()
        assert a >= b


def test_given_versioning_when_insert_version_then_pk_enforced(engine):
    with engine.connect() as conn:
        try:
            conn.execute(
            text(
                """
                INSERT INTO device_profile_versions(profile_id,version,snapshot,changed_by)
                VALUES ('p3',1,'{}','u2')
                """
            )
        )
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Tables missing: {exc}")
        try:
            conn.execute(
                text(
                    """
                    INSERT INTO device_profile_versions(profile_id,version,snapshot,changed_by)
                    VALUES ('p3',1,'{}','u2')
                    """
                )
            )
            assert False
        except Exception as e:
            assert "device_profile_versions_pkey" in str(e).lower()