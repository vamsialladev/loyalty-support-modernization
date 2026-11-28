"""Engine and session factory for the app database (Postgres in the stack, SQLite in offline tests).

**SQLite transactions take the write lock at their first write, and wait for it (TD-57).** A deferred `BEGIN` reads
under a shared lock and upgrades at its first write. When another connection already holds the write lock, SQLite
refuses that upgrade at once, whatever the busy timeout, because waiting could deadlock. So a transaction that read
and then wrote failed with "database is locked" whenever another writer was active. The worker's heartbeat (it reads
the clock, then extends the lease) and a running job are two such transactions: in Milestone 13 that requeued a job.

So no `BEGIN` is sent when SQLAlchemy starts a transaction. Statements that only read run without a lock, as each
statement does under Postgres's default READ COMMITTED. The first statement that writes, or a `SAVEPOINT`, is preceded
by `BEGIN IMMEDIATE`, which waits for the other writer (up to the 30 s busy timeout) instead of failing. From then on
the transaction holds the write lock to its commit. Reads never hold a lock, so a reader can't block a writer, which
is what made `BEGIN IMMEDIATE` on every transaction deadlock 70 tests in Milestone 12.

What changes for the code: reads before a transaction's first write no longer see one frozen snapshot, which is
already true on Postgres, where every deployment runs. Correctness that depends on it rests on constraints and
conditional updates, as it must on Postgres.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

_PENDING = "sqlite_begin_pending"
_READS = ("SELECT", "PRAGMA", "EXPLAIN")  # anything else, including WITH, is treated as a write: the safe side


def is_write(statement: str) -> bool:
    """Whether a statement needs the write lock. `SAVEPOINT` does: a rollback to it must undo what follows."""
    if not statement.strip():
        return False
    return statement.lstrip().split(None, 1)[0].upper() not in _READS


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
            conn.info[_PENDING] = True  # the BEGIN waits for the first write

        @event.listens_for(engine, "before_cursor_execute")
        def _before(conn, cursor, statement, _parameters, _context, _executemany):  # type: ignore[no-untyped-def]
            if conn.info.get(_PENDING) and is_write(statement):
                conn.info[_PENDING] = False
                cursor.execute("BEGIN IMMEDIATE")

        def _ended(conn: Any) -> None:
            conn.info.pop(_PENDING, None)

        event.listen(engine, "commit", _ended)
        event.listen(engine, "rollback", _ended)

        return engine
    return create_engine(url, pool_pre_ping=True)


def make_sessions(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
