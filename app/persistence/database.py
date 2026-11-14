"""Engine and session factory for the app database (Postgres in the stack, SQLite in offline tests)."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(engine, "connect")
        def _connect(dbapi_connection, _record):  # type: ignore[no-untyped-def]
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
            # Hand transactions to SQLAlchemy. Otherwise the driver starts none before SAVEPOINT, and RELEASE commits,
            # so a rollback would not undo what a savepoint wrapped (SQLAlchemy's documented recipe for SQLite).
            dbapi_connection.isolation_level = None

        @event.listens_for(engine, "begin")
        def _begin(conn):  # type: ignore[no-untyped-def]
            # IMMEDIATE takes the write lock first, so a second writer (the worker, another process) waits up to the
            # busy timeout. A deferred BEGIN upgrades at its first write and gets "database is locked" at once when
            # another connection holds the lock, whatever the timeout (TD-57; tests/test_sqlite_engine.py).
            conn.exec_driver_sql("BEGIN IMMEDIATE")

        return engine
    return create_engine(url, pool_pre_ping=True)


def make_sessions(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
