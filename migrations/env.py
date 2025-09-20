from __future__ import annotations

import os
from dotenv import load_dotenv
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url
from alembic import context
from app.db.base import Base
from app.db import models  # noqa: F401

config = context.config
load_dotenv()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url() -> str:
    url_env = os.environ.get("DATABASE_URL")
    if url_env:
        try:
            parsed = make_url(url_env)
            # When DATABASE_URL is built from str(engine.url), password is masked as '***'.
            if parsed.password and str(parsed.password) == "***":
                pwd = os.environ.get("DB_PASSWORD")
                if pwd is not None:
                    parsed = parsed.set(password=pwd)
                    try:
                        return parsed.render_as_string(hide_password=False)
                    except Exception:
                        # Fallback for older SQLAlchemy (should not happen in this project)
                        return str(parsed).replace("***", pwd)
                # No password available; return as-is and let connection fail rather than switching DBs.
                return url_env
            return url_env
        except Exception:
            # Fall back to components below if parsing fails
            pass

    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    db = os.environ.get("DB_NAME", "zenrows")
    user = os.environ.get("DB_USER", "postgres")
    pwd = os.environ.get("DB_PASSWORD", "postgres")
    return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}"

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
