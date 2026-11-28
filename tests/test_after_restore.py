"""After a restore, every access the backup held as live is ended (ROLL-03, ADR-0096). Drill D4 found a session
revoked after the backup working again after the restore (verification log M13b row 11)."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.roles import Identity, Role
from app.persistence.database import make_engine, make_sessions
from app.persistence.models import ApiToken, BreakGlassGrant, SystemEvent, User, UserSession
from app.services import after_restore, security_events
from tests.conftest import ROOT

AUDITOR = Identity(0, "audit-reader", "Auditor", Role.AUDITOR)


@pytest.fixture
def db(tmp_path: Path) -> sessionmaker[Session]:
    url = f"sqlite:///{(tmp_path / 'restored.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    factory = make_sessions(make_engine(url))
    with factory() as s:
        s.add(User(username="ana", display_name="ana", role="agent", password_hash="x",
                   created_at_utc="2026-11-01T00:00:00Z"))  # fmt: skip
        s.flush()
        user_id = s.scalar(select(User.id).where(User.username == "ana"))
        for token, revoked in (("live-1", None), ("live-2", None), ("old", "2026-11-27T00:00:00Z")):
            s.add(UserSession(token_hash=token, user_id=user_id, csrf_token="c", created_at_utc="2026-11-28T00:00:00Z",
                              expires_at_utc="2026-11-28T08:00:00Z", revoked_at_utc=revoked))  # fmt: skip
        s.add(ApiToken(token_hash="t1", name="mcp", customer_id="hg-demo", created_by="adm",
                       created_at_utc="2026-11-28T00:00:00Z", expires_at_utc="2026-12-28T00:00:00Z"))  # fmt: skip
        s.add(
            BreakGlassGrant(
                user_id=user_id,
                granted_by="sam",
                reason="INC-1: stuck kill switch",
                granted_at_utc="2026-11-28T00:00:00Z",
                expires_at_utc="2026-11-28T00:30:00Z",
            )
        )
        s.commit()
    return factory


def test_every_live_session_token_and_grant_is_ended_and_recorded(db: sessionmaker[Session]) -> None:
    with db() as s:
        sealed = after_restore.seal_access(s, "restored from the 2026-11-28 backup")
    assert sealed == after_restore.Sealed(sessions=2, api_tokens=1, break_glass_grants=1)
    with db() as s:
        assert all(row.revoked_at_utc for row in s.scalars(select(UserSession)))
        assert all(row.revoked_at_utc for row in s.scalars(select(ApiToken)))
        [grant] = s.scalars(select(BreakGlassGrant)).all()
        assert grant.end_reason == "revoked" and grant.ended_by == "system-worker"
        [event] = s.scalars(select(SystemEvent).where(SystemEvent.action == "restore_access_sealed")).all()
        assert event.detail["sessions"] == 2 and event.detail["reason"] == "restored from the 2026-11-28 backup"
        [classified] = [e for e in security_events.events(s, AUDITOR) if e.action == "restore_access_sealed"]
    assert (classified.category, classified.severity) == ("privilege", 3)
    assert "reason" not in classified.detail  # the reason stays in the database


def test_running_it_twice_ends_nothing_more(db: sessionmaker[Session]) -> None:
    with db() as s:
        after_restore.seal_access(s, "restored from the 2026-11-28 backup")
        assert after_restore.seal_access(s, "restored from the 2026-11-28 backup, again") == after_restore.Sealed(
            0, 0, 0
        )


def test_a_reason_is_required(db: sessionmaker[Session]) -> None:
    with db() as s, pytest.raises(ValueError, match="which backup"):
        after_restore.seal_access(s, "oops")
    with db() as s:
        assert s.scalars(select(UserSession).where(UserSession.revoked_at_utc.is_(None))).all()  # nothing changed


def test_the_command_line_prints_counts_only(
    db: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DATABASE_URL", str(db.kw["bind"].url))
    assert after_restore.main(["--reason", "restored from the 2026-11-28 backup"]) == 0
    assert capsys.readouterr().out.startswith("ended 2 session(s), 1 API token(s) and 1 break-glass grant(s)")
