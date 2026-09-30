from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def get_engine() -> Engine:
    settings = get_settings()
    connect_args = {}
    if settings.database_type == "sqlite":
        connect_args = {"check_same_thread": False}
    return create_engine(settings.database_url, connect_args=connect_args)


SessionLocal = sessionmaker(autocommit=False, autoflush=False)


def init_session_factory(engine: Engine | None = None) -> sessionmaker:
    eng = engine or get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=eng)


@contextmanager
def get_db_session(engine: Engine | None = None):
    factory = init_session_factory(engine)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database(engine: Engine | None = None) -> None:
    eng = engine or get_engine()
    schema_path = Path(__file__).resolve().parent.parent / "database" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    # SQLite 不支持部分 PG 语法，schema 已按 SQLite 编写
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with eng.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def execute_query(sql: str, params: dict | None = None, engine: Engine | None = None):
    eng = engine or get_engine()
    with eng.connect() as conn:
        result = conn.execute(text(sql), params or {})
        if result.returns_rows:
            return [dict(row._mapping) for row in result]
        conn.commit()
        return []
