from contextlib import contextmanager
from typing import Iterator
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


_engine = None
_engine_url = None


def _current_db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER", "postgres")
    pwd = os.environ.get("DB_PASSWORD", "postgres")
    db = os.environ.get("DB_NAME", "zenrows")
    return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}"


def _get_engine():
    global _engine, _engine_url
    url = _current_db_url()
    if _engine is None or _engine_url != url:
        _engine = create_engine(url, pool_pre_ping=True, future=True)
        _engine_url = url
    return _engine


@contextmanager
def get_session() -> Iterator[Session]:
    eng = _get_engine()
    with Session(eng) as s:
        yield s
