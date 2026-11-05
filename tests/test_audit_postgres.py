"""The append-only audit role and the close rules, on real PostgreSQL (spec B.10, WP-11; ADR-0054, ADR-0058).

These connect as the app's real runtime role. They assert what the database refuses, not what the code chooses to do.
Guarantees and their limits are stated in `docs/decisions.md` (ADR-0058).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

from app.domain.case_states import CaseState
from app.domain.roles import Identity, Role
from app.persistence.models import Case
from app.services import cases as svc
from app.services.instrumentation import events, record_system
from tests.arm_a import ArmA
from tests.pg_stack import OWNER_URL, clear_cases, make_pg_arm, needs_postgres

pytestmark = [pytest.mark.postgres, needs_postgres]
K01, MEMBER, STAY = "DV-001", "GR-85640", "BR-6638"
REFUSED = [
    "UPDATE {table} SET actor = 'someone-else'",
    "DELETE FROM {table}",
    "TRUNCATE {table}",
    "ALTER TABLE {table} DISABLE TRIGGER ALL",
    "ALTER TABLE {table} OWNER TO loyalty_app",
    "DROP TABLE {table}",
]


@pytest.fixture(scope="module")
def pg(generated: Path) -> Iterator[tuple[ArmA, Engine]]:
    arm, owner = make_pg_arm(generated)
    yield arm, owner
    owner.dispose()


@pytest.fixture
def arm(pg: tuple[ArmA, Engine]) -> ArmA:
    clear_cases(pg[1])
    return pg[0]


def a_logged_case(arm: ArmA) -> int:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        svc.start_work(s, arm.who("agent.ana"), case)
        record_system(s, Identity(1, "admin.ada", "Ada", Role.ADMINISTRATOR), "kill_switch_changed", engaged=False)
        s.commit()
        return case.id


def test_the_runtime_is_not_the_owner(arm: ArmA) -> None:
    with arm.sessions() as s:
        assert s.scalar(text("select current_user")) == "loyalty_app"
        assert s.scalar(text("select tableowner from pg_tables where tablename = 'case_events'")) == "loyalty_owner"
        assert OWNER_URL.split("//")[1].startswith("loyalty_owner:")


@pytest.mark.parametrize("table", ["case_events", "system_events"])
@pytest.mark.parametrize("statement", REFUSED)
def test_the_runtime_role_cannot_change_audit_history(arm: ArmA, table: str, statement: str) -> None:
    a_logged_case(arm)
    with arm.sessions() as s:
        before = s.scalar(text(f"select count(*) from {table}"))
        assert before > 0
        with pytest.raises(ProgrammingError, match=r"permission denied|must be owner"):
            s.execute(text(statement.format(table=table)))
        s.rollback()
        assert s.scalar(text(f"select count(*) from {table}")) == before


def test_the_runtime_role_can_add_and_read_events(arm: ArmA) -> None:
    case_id = a_logged_case(arm)
    with arm.sessions() as s:
        case = s.get(Case, case_id)
        assert case is not None
        svc.add_note(s, arm.who("agent.ana"), case, "Checked.")
        assert [e.action for e in events(s, case)][-1] == "note_added"


def test_the_runtime_role_cannot_change_the_schema_or_its_version(arm: ArmA) -> None:
    for statement in ("CREATE TABLE sneaky (id int)", "UPDATE alembic_version SET version_num = '0001'"):
        with arm.sessions() as s, pytest.raises(ProgrammingError, match="permission denied"):
            s.execute(text(statement))
    with arm.sessions() as s:
        assert s.scalar(text("select version_num from alembic_version")) >= "0004"


def test_the_owner_can_still_edit_so_the_guarantee_has_a_stated_limit(pg: tuple[ArmA, Engine], arm: ArmA) -> None:
    """Not a feature: the record of a limit. The owner role (and a superuser, and anyone with the backups) can rewrite
    history, so "append-only" here means the app can't, never that it's tamper-proof (ADR-0058)."""
    a_logged_case(arm)
    with pg[1].begin() as conn:
        changed = conn.execute(text("UPDATE system_events SET actor = 'rewritten'")).rowcount
    assert changed > 0


# ---------- the close rules (ADR-0054): until now they had run on SQLite only ----------


def worked_case(arm: ArmA) -> tuple[int, str]:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        svc.start_work(s, arm.who("agent.ana"), case)
        return case.id, case.received_at_utc


RULE_CODES = ["no_adjustment_credited", "wait_until", "not_checked_out", "deny_channel_ineligible", "deny_claim_window"]


@pytest.mark.parametrize("code", RULE_CODES)
def test_a_rule_based_close_is_refused_while_the_evidence_is_incomplete(arm: ArmA, code: str) -> None:
    case_id, _ = worked_case(arm)
    with arm.sessions() as s:
        case = s.get(Case, case_id)
        assert case is not None
        with pytest.raises(svc.WorkflowError, match="evidence is incomplete"):
            svc.close_case(s, arm.who("agent.ana"), case, code, "A long note that must not unlock this.", arm.rules)
        assert case.status == CaseState.INVESTIGATING


def test_not_found_needs_the_latest_search_to_have_found_nothing(arm: ArmA) -> None:
    case_id, _received = worked_case(arm)
    who = arm.who("agent.ana")
    with arm.sessions() as s:
        case = s.get(Case, case_id)
        assert case is not None
        with pytest.raises(svc.WorkflowError, match="search the member screen first"):
            svc.close_case(s, who, case, "deny_not_found", "", arm.rules)
        svc.log_search(s, case, who, "member", "member number", 0)  # JSON stored in Postgres, read back by the rule
        svc.log_search(s, case, who, "member", "member number", 1)
        with pytest.raises(svc.WorkflowError, match="search the member screen first"):
            svc.close_case(s, who, case, "deny_not_found", "", arm.rules)
        svc.log_search(s, case, who, "member", "member number", 0)
        svc.close_case(s, who, case, "deny_not_found", "", arm.rules)
        assert case.status == CaseState.RESOLVED and case.resolution_code == "deny_not_found"
        last = events(s, case)[-1]
        assert last.action == "case_closed" and last.detail["override"] is False
    with arm.sessions() as s:
        reread = s.get(Case, case_id)
        assert reread is not None and svc.latest_search_found_nothing(s, reread, "member") is True


def test_a_full_close_and_reopen_keeps_its_history(arm: ArmA) -> None:
    case_id, received = worked_case(arm)
    who = arm.who("agent.ana")
    with arm.sessions() as s:
        case = s.get(Case, case_id)
        assert case is not None
        svc.close_case(s, who, case, "deny_other", "Member asked to withdraw this claim.", arm.rules)
        svc.reopen(s, who, case, "The member changed their mind by phone.")
        assert case.status == CaseState.INVESTIGATING
        actions = [e.action for e in events(s, case)]
        assert actions[-2:] == ["case_closed", "case_reopened"]
        systems = arm.systems(received)
        svc.attach_member(s, who, case, systems, MEMBER)
        svc.attach_stay(s, who, case, systems, MEMBER, STAY)
        svc.attach_ledger(s, who, case, systems, MEMBER, show_older=True)
        svc.attach_policy(s, who, case, arm.index, "missing-points-requests#3")
        assert svc.request_adjustment(s, who, case, arm.rules).points == 14_840
