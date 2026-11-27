"""Break-glass (ENT-26, ADR-0093): a time-limited administrator grant with a reason, a security event, a full audit
trail, expiry on its own, no renewal, off in the public demo, and no self-grant or hand-on by someone already raised."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.local_demo_identity import LocalDemoIdentity
from app.domain.roles import Identity, NotPermitted, Role, require_administrator, require_case_worker
from app.persistence.database import make_engine, make_sessions
from app.persistence.models import BreakGlassGrant, SystemEvent, User
from app.services import break_glass, security_events, sessions
from app.services.instrumentation import record_system
from tests.conftest import ROOT

T0 = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
REASON = "INC-12: the kill switch is stuck on"
AUDITOR = Identity(0, "audit-reader", "Auditor", Role.AUDITOR)


@pytest.fixture
def db(tmp_path: Path) -> sessionmaker[Session]:
    url = f"sqlite:///{(tmp_path / 'bg.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")  # the new migration, 0015, is part of what's tested
    factory = make_sessions(make_engine(url))
    with factory() as s:
        for username, role, active, customer in (
            ("ana", "agent", True, "hg-demo"),
            ("sam", "supervisor", True, "hg-demo"),
            ("sue", "supervisor", True, "hg-demo"),
            ("adm", "administrator", True, "hg-demo"),
            ("aud", "auditor", True, "hg-demo"),
            ("old", "supervisor", False, "hg-demo"),
            ("svc-bot", "agent", True, "hg-demo"),
            ("far", "agent", True, "other-co"),
        ):
            s.add(
                User(
                    username=username, display_name=username, role=role, password_hash="x", active=active,
                    created_at_utc="2026-11-01T00:00:00Z", customer_id=customer,
                )
            )  # fmt: skip
        s.commit()
    return factory


def events(factory: sessionmaker[Session], action: str) -> list[SystemEvent]:
    with factory() as s:
        return list(s.scalars(select(SystemEvent).where(SystemEvent.action == action)).all())


def grants(factory: sessionmaker[Session]) -> list[BreakGlassGrant]:
    with factory() as s:
        return list(s.scalars(select(BreakGlassGrant)).all())


def give(factory: sessionmaker[Session], **kw: object) -> BreakGlassGrant:
    args: dict[str, object] = {"user": "ana", "by": "sam", "minutes": 30, "reason": REASON, "public_demo": False}
    args.update(kw)
    with factory() as s:
        return break_glass.grant(s, now=args.pop("now", T0), **args)  # type: ignore[arg-type]


def signed_in(factory: sessionmaker[Session], username: str = "ana") -> str:
    provider = LocalDemoIdentity(factory)
    with factory() as s:
        user = s.scalar(select(User).where(User.username == username))
        assert user is not None
        token, _ = sessions.start(s, provider.lookup(user.id), now=T0)  # type: ignore[arg-type]
    return token


def who(factory: sessionmaker[Session], token: str, now: datetime, allowed: bool = True) -> Identity:
    with factory() as s:
        active = sessions.resolve(s, LocalDemoIdentity(factory), token, now, break_glass_allowed=allowed)
    assert active is not None
    return active.identity


def test_a_grant_raises_the_person_to_administrator_for_its_time_only(db: sessionmaker[Session]) -> None:
    token = signed_in(db)
    row = give(db)
    assert (row.granted_by, row.expires_at_utc) == ("sam", "2026-11-27T12:30:00Z")
    raised = who(db, token, T0 + timedelta(minutes=29))
    assert (raised.role, raised.break_glass_grant) == (Role.ADMINISTRATOR, row.id)
    require_administrator(raised)  # can manage configuration (the kill switch, policy publishing)
    with pytest.raises(NotPermitted):
        require_case_worker(raised)  # but can't work cases, so a grant can't approve or post money
    after = who(db, token, T0 + timedelta(minutes=30))  # expires on its own, at the minute
    assert (after.role, after.break_glass_grant) == (Role.AGENT, None)


def test_a_grant_is_a_loud_security_event_and_its_reason_never_leaves(db: sessionmaker[Session]) -> None:
    row = give(db)
    [granted] = events(db, "break_glass_granted")
    assert granted.actor == "sam" and granted.actor_kind == "human"
    assert granted.detail["reason"] == REASON and granted.detail["minutes"] == 30
    with db() as s:
        [event] = [e for e in security_events.events(s, AUDITOR) if e.action == "break_glass_granted"]
    assert (event.category, event.outcome, event.severity) == ("privilege", "success", 4)
    exported = security_events.to_ecs(event)
    assert exported["loyalty"]["detail"] == {"grant": row.id, "username": "ana", "minutes": 30,
                                             "expires_at_utc": "2026-11-27T12:30:00Z"}  # fmt: skip
    assert REASON not in str(exported)


def test_the_expiry_is_recorded_once_and_the_grant_row_keeps_its_end(db: sessionmaker[Session]) -> None:
    token = signed_in(db)
    row = give(db)
    for minutes in (31, 40):
        assert who(db, token, T0 + timedelta(minutes=minutes)).role is Role.AGENT
    [expired] = events(db, "break_glass_expired")
    assert expired.detail == {"grant": row.id, "username": "ana"}
    [ended] = grants(db)
    assert (ended.end_reason, ended.ended_at_utc) == ("expired", "2026-11-27T12:30:00Z")


def test_expire_due_closes_grants_nobody_came_back_for(db: sessionmaker[Session]) -> None:
    give(db, minutes=5)
    with db() as s:
        assert break_glass.expire_due(s, T0 + timedelta(minutes=4)) == 0
        assert break_glass.expire_due(s, T0 + timedelta(minutes=6)) == 1
        assert break_glass.expire_due(s, T0 + timedelta(minutes=7)) == 0
    assert len(events(db, "break_glass_expired")) == 1


def test_everything_done_under_a_grant_carries_its_number(db: sessionmaker[Session]) -> None:
    token = signed_in(db)
    row = give(db)
    raised = who(db, token, T0 + timedelta(minutes=1))
    with db() as s:
        record_system(s, raised, "kill_switch_changed", engaged=True)
        s.commit()
    [change] = events(db, "kill_switch_changed")
    assert change.actor == "ana" and change.detail["break_glass_grant"] == row.id


def test_the_public_demo_never_raises_anyone_even_with_an_open_grant(db: sessionmaker[Session]) -> None:
    token = signed_in(db)
    give(db)  # as if a grant existed in a demo database
    assert who(db, token, T0 + timedelta(minutes=1), allowed=False).role is Role.AGENT


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"public_demo": True}, "public_demo"),
        ({"minutes": 0}, "minutes"),
        ({"minutes": 61}, "minutes"),
        ({"reason": "  because   "}, "reason"),
        ({"user": "sam", "by": "sam"}, "self"),
        ({"by": "ana", "user": "sam"}, "grantor"),  # an agent can't grant
        ({"by": "old"}, "grantor"),  # an inactive account can't grant
        ({"by": "nobody"}, "grantor"),
        ({"user": "aud"}, "grantee"),  # an auditor stays independent
        ({"user": "adm"}, "grantee"),  # an administrator needs none
        ({"user": "svc-bot"}, "grantee"),  # a machine account is never raised
        ({"user": "old", "by": "sue"}, "grantee"),
        ({"user": "far"}, "customer"),
    ],
)
def test_each_refusal_grants_nothing_and_is_a_security_event(
    db: sessionmaker[Session], change: dict[str, object], code: str
) -> None:
    with pytest.raises(break_glass.Refused) as refused:
        give(db, **change)
    assert refused.value.code == code
    assert grants(db) == []
    [event] = events(db, "break_glass_refused")
    assert event.detail["kind"] == code
    with db() as s:
        [classified] = [e for e in security_events.events(s, AUDITOR) if e.action == "break_glass_refused"]
    assert (classified.outcome, classified.severity) == ("failure", 3)


def test_no_renewal_only_a_new_grant_after_the_first_ends(db: sessionmaker[Session]) -> None:
    first = give(db)
    with pytest.raises(break_glass.Refused) as refused:
        give(db, by="sue", now=T0 + timedelta(minutes=10))  # another grantor can't top it up either
    assert refused.value.code == "already_open"
    later = give(db, by="sue", now=T0 + timedelta(minutes=31))  # after it expired: a new grant, a new number
    assert later.id != first.id and later.expires_at_utc == "2026-11-27T13:01:00Z"
    assert [g.end_reason for g in grants(db)] == ["expired", None]
    assert not hasattr(break_glass, "extend")  # there is no command that extends a grant


def test_someone_under_break_glass_cannot_grant_or_revoke(db: sessionmaker[Session]) -> None:
    raised = give(db, user="sam", by="sue")  # sam, a supervisor, is raised
    with pytest.raises(break_glass.Refused) as refused:
        give(db, user="ana", by="sam", now=T0 + timedelta(minutes=1))
    assert refused.value.code == "grantor_elevated"
    with db() as s, pytest.raises(break_glass.Refused) as refused:
        break_glass.revoke(s, grant_id=raised.id, by="sam", reason="ending my own grant early", now=T0)
    assert refused.value.code == "revoker_elevated"


def test_a_revoked_grant_ends_at_once_and_is_recorded(db: sessionmaker[Session]) -> None:
    token = signed_in(db)
    row = give(db)
    with db() as s:
        break_glass.revoke(s, grant_id=row.id, by="sue", reason="INC-12 resolved, access no longer needed",
                           now=T0 + timedelta(minutes=5))  # fmt: skip
    assert who(db, token, T0 + timedelta(minutes=6)).role is Role.AGENT
    [revoked] = events(db, "break_glass_revoked")
    assert revoked.actor == "sue" and revoked.detail["grant"] == row.id
    [ended] = grants(db)
    assert (ended.end_reason, ended.ended_by, ended.ended_at_utc) == ("revoked", "sue", "2026-11-27T12:05:00Z")
    with db() as s, pytest.raises(break_glass.Refused) as refused:
        break_glass.revoke(s, grant_id=row.id, by="sue", reason="a second time, by mistake", now=T0)
    assert refused.value.code == "not_open"
    with db() as s, pytest.raises(break_glass.Refused) as refused:
        break_glass.revoke(s, grant_id=row.id + 1, by="ana", reason="an agent can't revoke anything")
    assert refused.value.code == "not_open"


def test_an_agent_cannot_revoke_and_a_short_reason_is_refused(db: sessionmaker[Session]) -> None:
    row = give(db)
    with db() as s, pytest.raises(break_glass.Refused) as refused:
        break_glass.revoke(s, grant_id=row.id, by="ana", reason="ending it myself, as the grantee", now=T0)
    assert refused.value.code == "revoker"
    with db() as s, pytest.raises(break_glass.Refused) as refused:
        break_glass.revoke(s, grant_id=row.id, by="sue", reason="done", now=T0)
    assert refused.value.code == "reason"


def test_the_command_line_grants_lists_and_refuses_in_the_public_demo(
    db: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    url = str(db.kw["bind"].url)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.delenv("PUBLIC_DEMO_MODE", raising=False)
    assert break_glass.main(["grant", "--user", "ana", "--by", "sam", "--minutes", "15", "--reason", REASON]) == 0
    assert "granted #1 to ana" in capsys.readouterr().out
    assert break_glass.main(["list"]) == 0
    assert "open: 1" in capsys.readouterr().out
    monkeypatch.setenv("PUBLIC_DEMO_MODE", "true")
    assert break_glass.main(["grant", "--user", "ana", "--by", "sue", "--reason", REASON]) == 2
    assert "refused (public_demo)" in capsys.readouterr().err


def test_the_console_allows_break_glass_except_in_the_public_demo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.main import create_app

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'app.db').as_posix()}")
    monkeypatch.setenv("MOCK_API_URL", "http://127.0.0.1:9")
    monkeypatch.delenv("PUBLIC_DEMO_MODE", raising=False)
    assert create_app().state.break_glass_allowed is True
    monkeypatch.setenv("PUBLIC_DEMO_MODE", "true")
    assert create_app().state.break_glass_allowed is False
