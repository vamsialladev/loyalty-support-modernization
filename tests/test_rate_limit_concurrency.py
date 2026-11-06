"""Pages that load several things at once must not block each other on the rate limit.

Found by CI on Milestone 9: `/day-one` loads its charts together, and each request read, then wrote. On SQLite, requests
doing that hold a read lock while they wait to write, so they wait on each other until the 30 s timeout. Postgres has
its own concurrency test in `tests/test_security_postgres.py`.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from sqlalchemy import select

from app.adapters.local_demo_identity import LocalDemoIdentity, ensure_demo_users
from app.domain.roles import Identity, Role
from app.persistence.database import make_engine, make_sessions
from app.persistence.models import Base, RateLimit, User
from app.services import rate_limit
from app.services import sessions as signed_in

REQUESTS = 8
ROUNDS = 25
BUSY_TIMEOUT_SECONDS = 30  # `app/persistence/database.py`


def test_requests_that_read_first_all_get_counted_and_none_hits_a_locked_database(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'limits.db'}")
    RateLimit.metadata.create_all(engine, tables=[RateLimit.metadata.tables["rate_limits"]])
    sessions = make_sessions(engine)
    with sessions() as s:  # the row exists, as it does for anyone already signed in
        rate_limit.hit(s, "user:1", 1_000, 3_600)
    errors: list[str] = []
    all_have_read = threading.Barrier(REQUESTS)

    def request() -> None:
        with sessions() as s:
            s.scalars(select(RateLimit)).all()  # what looking up the session does first: it takes a read lock
            all_have_read.wait(timeout=30)
            try:
                rate_limit.hit(s, "user:1", 1_000, 3_600)
            except Exception as exc:
                errors.append(type(exc).__name__)

    threads = [threading.Thread(target=request) for _ in range(REQUESTS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert errors == []
    with sessions() as s:
        assert s.scalars(select(RateLimit.hits).where(RateLimit.key == "user:1")).one() == REQUESTS + 1
    engine.dispose()


def test_signing_requests_in_at_the_same_time_doesnt_stall(tmp_path: Path) -> None:
    """The real path: `resolve` reads, the identity provider opens its own connection, then the hit writes.

    A connection held open across that lookup can't finish while a writer waits, and the writer waits for it.
    """
    engine = make_engine(f"sqlite:///{tmp_path / 'requests.db'}")
    Base.metadata.create_all(engine)
    sessions = make_sessions(engine)
    provider = LocalDemoIdentity(sessions)
    with sessions() as s:
        ensure_demo_users(s, "a-test-password-of-enough-length")
        s.commit()
        user = s.scalars(select(User).where(User.username == "agent.ana")).one()
        who = Identity(user.id, user.username, user.display_name, Role(user.role))
        token, _csrf = signed_in.start(s, who)
    errors: list[str] = []
    slowest = [0.0]

    def requests() -> None:
        for _ in range(ROUNDS):
            started = time.monotonic()
            with sessions() as s:
                try:
                    assert signed_in.resolve(s, provider, token) is not None
                    rate_limit.hit(s, "user:1", 1_000_000, 3_600)
                except Exception as exc:
                    errors.append(type(exc).__name__)
            slowest[0] = max(slowest[0], time.monotonic() - started)

    threads = [threading.Thread(target=requests) for _ in range(REQUESTS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=300)
    assert errors == []
    assert slowest[0] < BUSY_TIMEOUT_SECONDS, "a request waited out the whole lock timeout"
    engine.dispose()
