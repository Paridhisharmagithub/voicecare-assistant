from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import BACKEND_DIR, settings


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///") and ":memory:" not in url:
        relative = url.removeprefix("sqlite:///")
        database_path = Path(relative)
        if not database_path.is_absolute():
            database_path = BACKEND_DIR / database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{database_path.as_posix()}"
    return url


DB_URL = _database_url()
_engine_kwargs = {"pool_pre_ping": True}
if DB_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DB_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
