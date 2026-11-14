"""SQLite, used offline and by the browser tests' stack, must make a second writer wait, not fail (TD-57).

Found 2026-11-14 when the browser job kept the test servers' logs: the app's "Attach to case" failed with
`database is locked` while the worker, a second process on the same file, claimed a job. A deferred `BEGIN` starts as
a reader and upgrades at its first write; when another connection already holds the write lock, SQLite returns BUSY at
once, whatever the busy timeout, to avoid a deadlock. `BEGIN IMMEDIATE` takes the write lock first, so it waits.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from sqlalchemy import text

from app.persistence.database import make_engine


def test_a_reader_that_then_writes_waits_for_another_writer_instead_of_failing(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'locks.db').as_posix()}"
    first, second = make_engine(url), make_engine(url)  # two engines: as the app and the worker, two processes
    with first.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
        conn.execute(text("INSERT INTO t (v) VALUES ('seed')"))

    holding = threading.Event()

    def writer_that_holds_the_lock() -> None:
        with second.begin() as conn:
            conn.execute(text("UPDATE t SET v = 'worker' WHERE id = 1"))
            holding.set()
            time.sleep(1.0)  # the worker's claim, held for a moment

    other = threading.Thread(target=writer_that_holds_the_lock)
    other.start()
    assert holding.wait(5)
    started = time.monotonic()
    with first.begin() as conn:  # the app: read, then write, while the other writer holds the lock
        conn.execute(text("SELECT v FROM t WHERE id = 1")).scalar_one()
        conn.execute(text("INSERT INTO t (v) VALUES ('app')"))
    other.join()
    waited = time.monotonic() - started

    with first.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM t")).scalar_one() == 2
    assert waited > 0.3, "the second writer should have waited for the first one's commit"
    first.dispose()
    second.dispose()
