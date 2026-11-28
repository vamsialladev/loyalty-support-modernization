"""SQLite, used offline, by the browser tests' stack and by the benchmark, makes a second writer wait, not fail (TD-57).

Found 2026-11-14 when the browser job kept the test servers' logs: the app's "Attach to case" failed with
`database is locked` while the worker, a second process on the same file, claimed a job. Seen again in Milestone 13
(2026-11-27): the benchmark requeued an `investigate_case` job on the same error, most likely the worker's heartbeat
(it reads the clock, then extends the lease) racing the job's own read-then-write.

A deferred `BEGIN` starts as a reader and upgrades at its first write; when another connection already holds the write
lock, SQLite returns BUSY at once, whatever the busy timeout, to avoid a deadlock. Fixed (2026-11-28) by taking the
write lock with `BEGIN IMMEDIATE` at a transaction's first write, and holding no lock for reads before it
(`app/persistence/database.py`). These tests failed on the old engine (verification log, Milestone 13).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from app.persistence.database import is_write, make_engine


def _two_engines(tmp_path: Path) -> tuple[Engine, Engine]:
    url = f"sqlite:///{(tmp_path / 'locks.db').as_posix()}"
    first, second = make_engine(url), make_engine(url)  # two engines: as the app and the worker, two processes
    with first.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
        conn.execute(text("INSERT INTO t (v) VALUES ('seed')"))
    return first, second


def _count(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT count(*) FROM t")).scalar_one())


def test_a_reader_that_then_writes_waits_for_another_writer_instead_of_failing(tmp_path: Path) -> None:
    first, second = _two_engines(tmp_path)
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

    assert _count(first) == 2
    assert waited > 0.3, "the second writer should have waited for the first one's commit"
    first.dispose()
    second.dispose()


def test_two_read_then_write_transactions_both_succeed_like_a_heartbeat_and_a_job(tmp_path: Path) -> None:
    """The Milestone 13 shape: both sides read first (the clock, the job row), then write."""
    first, second = _two_engines(tmp_path)
    failures: list[BaseException] = []
    rounds = 15

    def heartbeat() -> None:
        try:
            for _ in range(rounds):
                with second.begin() as conn:
                    conn.execute(text("SELECT CURRENT_TIMESTAMP, v FROM t WHERE id = 1")).one()
                    conn.execute(text("UPDATE t SET v = 'beat' WHERE id = 1"))
                    time.sleep(0.01)
        except BaseException as exc:
            failures.append(exc)

    beat = threading.Thread(target=heartbeat)
    beat.start()
    for n in range(rounds):
        with first.begin() as conn:
            conn.execute(text("SELECT v FROM t WHERE id = 1")).scalar_one()
            time.sleep(0.005)  # a little work between the read and the write, as a job has
            conn.execute(text("INSERT INTO t (v) VALUES (:v)"), {"v": f"job-{n}"})
    beat.join()

    assert failures == []
    assert _count(first) == 1 + rounds
    first.dispose()
    second.dispose()


def test_an_open_read_only_transaction_doesnt_block_a_writer(tmp_path: Path) -> None:
    first, second = _two_engines(tmp_path)
    done = threading.Event()

    def writer() -> None:
        with second.begin() as conn:
            conn.execute(text("INSERT INTO t (v) VALUES ('worker')"))
        done.set()

    with first.begin() as conn:  # a reader that stays open, as a request or a test does
        conn.execute(text("SELECT v FROM t WHERE id = 1")).scalar_one()
        other = threading.Thread(target=writer)
        other.start()
        assert done.wait(5), "a reader held a lock that made the writer wait"
        other.join()
    assert _count(first) == 2
    first.dispose()
    second.dispose()


def test_a_rollback_to_a_savepoint_still_undoes_only_what_followed_it(tmp_path: Path) -> None:
    first, second = _two_engines(tmp_path)
    with first.connect() as conn:
        with conn.begin():
            conn.execute(text("INSERT INTO t (v) VALUES ('kept')"))
            nested = conn.begin_nested()
            conn.execute(text("INSERT INTO t (v) VALUES ('undone')"))
            nested.rollback()
        with conn.begin():  # a savepoint as the first statement also takes the write lock first
            nested = conn.begin_nested()
            conn.execute(text("INSERT INTO t (v) VALUES ('undone too')"))
            nested.rollback()
        rows = [r[0] for r in conn.execute(text("SELECT v FROM t ORDER BY id"))]
    assert rows == ["seed", "kept"]
    first.dispose()
    second.dispose()


def test_a_rolled_back_transaction_leaves_nothing_and_releases_the_lock(tmp_path: Path) -> None:
    first, second = _two_engines(tmp_path)
    with first.connect() as conn:
        transaction = conn.begin()
        conn.execute(text("INSERT INTO t (v) VALUES ('gone')"))
        transaction.rollback()
    with second.begin() as conn:  # would wait 30 s if the lock were still held
        conn.execute(text("INSERT INTO t (v) VALUES ('after')"))
    assert _count(first) == 2
    first.dispose()
    second.dispose()


@pytest.mark.parametrize(
    ("statement", "writes"),
    [
        ("SELECT 1", False),
        ("  select v from t", False),
        ("PRAGMA foreign_keys", False),
        ("INSERT INTO t VALUES (1)", True),
        ("UPDATE t SET v = 1", True),
        ("DELETE FROM t", True),
        ("SAVEPOINT sa_savepoint_1", True),
        ("CREATE TABLE x (id INTEGER)", True),
        ("WITH a AS (SELECT 1) INSERT INTO t SELECT * FROM a", True),
        ("", False),
    ],
)
def test_only_reads_skip_the_write_lock(statement: str, writes: bool) -> None:
    assert is_write(statement) is writes
