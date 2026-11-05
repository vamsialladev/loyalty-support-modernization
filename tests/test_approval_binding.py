"""Approval binding, expiry and invalidation (spec B.10, B.6; WP-03, WP-06, WP-07, POL-05; ADR-0059), on SQLite.

The real-Postgres versions of the Appendix C checks are in `tests/test_write_path_postgres.py`.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.approval_binding import BoundAction, binding_holds, binding_mac, canonical, evidence_hash
from app.domain.case_states import CaseState
from app.domain.customer_records import AdjustmentRequest, AdjustmentResult, LedgerEntry, Member, StayRecord
from app.domain.roles import Identity, Role
from app.main import create_app
from app.persistence.models import AdjustmentRequestRow, Approval, Case
from app.ports.customer_systems import CustomerSystems, TemporarilyUnavailable
from app.services import cases as svc
from app.services import policy_publishing
from app.services.customer_config import CustomerConfig
from app.services.instrumentation import events
from app.services.write_path import SharedWritePath, approval_of
from app.settings import AppSettings
from tests.arm_a import ArmA, Browser, field, make_arm_a
from tests.test_policies import draft_text

K01, MEMBER, STAY, POINTS = "DV-001", "GR-85640", "BR-6638", 14_840  # checkout 2025-11-29: policy v1
LATER_K01, LATER_MEMBER, LATER_STAY = "DV-094", "GR-80622", "BR-4403"  # checkout 2026-07-11: policy v2
LATE_POSTING, LATE_MEMBER, LATE_STAY = "DV-031", "GR-22429", "BR-1251"  # a posting lands on 2026-04-26
ADMIN = Identity(1, "admin.ada", "Ada", Role.ADMINISTRATOR)
CONFIG = CustomerConfig.load("hg-demo")
WP = SharedWritePath()


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def requested(
    arm: ArmA, s: Session, case_id: str = K01, member: str = MEMBER, stay: str = STAY
) -> tuple[Case, AdjustmentRequestRow]:
    (case,) = arm.load(s, case_id)
    who, systems = arm.who("agent.ana"), arm.systems(case.received_at_utc)
    svc.start_work(s, who, case)
    svc.attach_member(s, who, case, systems, member)
    svc.attach_stay(s, who, case, systems, member, stay)
    svc.attach_ledger(s, who, case, systems, member, show_older=True)
    svc.attach_policy(s, who, case, arm.index, "missing-points-requests#3")
    return case, svc.request_adjustment(s, who, case, arm.rules)


def approved(arm: ArmA, s: Session, *args: str, wp: SharedWritePath = WP) -> tuple[Case, AdjustmentRequestRow]:
    case, row = requested(arm, s, *args)
    result = wp.decide(s, arm.who("supervisor.sam"), row.id, arm.systems(case.received_at_utc), approve=True, reason="")
    assert result.status == "approved"
    return case, row


class Changed:
    """The customer systems, with chosen records changed since the approval. Counts submissions."""

    def __init__(
        self,
        inner: CustomerSystems,
        *,
        member: dict[str, Any] | None = None,
        stay: dict[str, Any] | None = None,
        entries: tuple[LedgerEntry, ...] = (),
        down: bool = False,
    ) -> None:
        self.inner, self.member, self.stay, self.entries, self.down = inner, member, stay, entries, down
        self.submits = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def get_member(self, member_number: str) -> Member:
        if self.down:
            raise TemporarilyUnavailable("member system down", code="unavailable")
        return replace(self.inner.get_member(member_number), **(self.member or {}))

    def find_stays(self, **kw: Any) -> list[StayRecord]:
        return [replace(r, **(self.stay or {})) for r in self.inner.find_stays(**kw)]

    def get_ledger(self, member_number: str) -> list[LedgerEntry]:
        return [*self.inner.get_ledger(member_number), *self.entries]

    def submit_adjustment(self, request: AdjustmentRequest, key: str) -> AdjustmentResult:
        self.submits += 1
        return self.inner.submit_adjustment(request, key)


# ---------- the binding itself ----------

ACTION = BoundAction(
    "hg", 1, "uid", MEMBER, STAY, POINTS, "missing_points", ("p@v1",), "e" * 64, "sam", "2026-01-01T00:00:00Z"
)


def test_canonical_form_ignores_key_order() -> None:
    assert canonical({"a": 1, "b": [2]}) == canonical({"b": [2], "a": 1})
    assert evidence_hash({"a": 1, "b": 2}) == evidence_hash({"b": 2, "a": 1})
    assert evidence_hash({"a": 1}) != evidence_hash({"a": 2})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("customer_id", "other"),
        ("request_id", 2),
        ("approval_uid", "other"),
        ("member_number", "GR-00000"),
        ("stay_id", "BR-0000"),
        ("points", POINTS + 1),
        ("reason_code", "other"),
        ("policy_refs", ("p@v2",)),
        ("evidence_hash", "f" * 64),
        ("approver", "sky"),
        ("expires_at_utc", "2027-01-01T00:00:00Z"),
    ],
)
def test_every_bound_field_changes_the_binding(name: str, value: object) -> None:
    mac = binding_mac(ACTION, "secret")
    assert binding_holds(ACTION, "secret", mac)
    assert not binding_holds(replace(ACTION, **{name: value}), "secret", mac)  # type: ignore[arg-type]


def test_the_binding_covers_every_field_it_declares() -> None:
    # A new field on BoundAction must get a line in the test above.
    assert len(asdict(ACTION)) == 11


def test_a_binding_made_with_another_secret_or_none_does_not_hold() -> None:
    mac = binding_mac(ACTION, "secret")
    assert not binding_holds(ACTION, "another-secret", mac)
    assert not binding_holds(ACTION, "secret", None)
    with pytest.raises(ValueError, match="no secret"):
        binding_mac(ACTION, "")


# ---------- requesting and approving ----------


def test_a_request_records_what_it_rests_on_and_an_approval_binds_it(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        assert row.checkout_day == "2025-11-29"
        assert row.policy_refs == ["guest-rewards-earning@v1", "missing-points-requests@v1"]
        assert row.evidence_hash is not None and len(row.evidence_hash) == 64
        approval = approval_of(s, row)
        assert approval is not None and approval.binding_mac is not None and approval.expires_at_utc is not None
        assert (approval.decided_at_utc[:10], approval.expires_at_utc[11:]) == (
            approval.decided_at_utc[:10],
            approval.decided_at_utc[11:],
        )
        assert case.status == CaseState.APPROVED


def test_no_published_policy_means_no_request(arm: ArmA) -> None:
    from sqlalchemy import update

    from app.persistence.models import PolicyVersionRow

    with arm.sessions() as s:
        s.execute(update(PolicyVersionRow).values(status="draft"))
        s.commit()
        (case,) = arm.load(s, K01)
        who, systems = arm.who("agent.ana"), arm.systems(case.received_at_utc)
        svc.start_work(s, who, case)
        svc.attach_member(s, who, case, systems, MEMBER)
        svc.attach_stay(s, who, case, systems, MEMBER, STAY)
        svc.attach_ledger(s, who, case, systems, MEMBER, show_older=True)
        svc.attach_policy(s, who, case, arm.index, "missing-points-requests#3")
        with pytest.raises(svc.WorkflowError, match="no single published policy"):
            svc.request_adjustment(s, who, case, arm.rules)
        assert case.status == CaseState.INVESTIGATING


CHANGES = [
    ({"stay": {"room_revenue_cents": 148_500}}, "outcome_or_amount"),
    ({"stay": {"taxes_cents": 999}}, "evidence_changed"),
    ({"stay": {"status": "in_house"}}, "outcome_changed"),
    ({"member": {"status": "merged", "merged_into": "GR-00001"}}, "evidence_changed"),
    (
        {"entries": (LedgerEntry("L-NEW", MEMBER, "posting", 100, "2026-01-01T00:00:00Z", STAY),)},
        "outcome_or_amount",
    ),
]


def _matches(reason: str | None, expected: str) -> bool:
    return reason in ("outcome_changed", "amount_changed") if expected == "outcome_or_amount" else reason == expected


@pytest.mark.parametrize(("change", "reason"), CHANGES)
def test_changed_evidence_stops_an_approval(arm: ArmA, change: dict[str, Any], reason: str) -> None:
    with arm.sessions() as s:
        case, row = requested(arm, s)
        systems = Changed(arm.systems(case.received_at_utc), **change)
        result = WP.decide(s, arm.who("supervisor.sam"), row.id, systems, approve=True, reason="")
        assert result.status == "invalidated"
        assert approval_of(s, row) is None
        assert case.status == CaseState.INVESTIGATING and row.status == "invalidated"
        assert _matches(row.invalidated_reason, reason)
        assert events(s, case)[-1].action == "approval_invalidated"


def test_an_unrelated_stays_posting_does_not_stop_an_approval(arm: ArmA) -> None:
    other = LedgerEntry("L-OTHER", MEMBER, "posting", 100, "2026-01-01T00:00:00Z", "ML-0000")
    with arm.sessions() as s:
        case, row = requested(arm, s)
        systems = Changed(arm.systems(case.received_at_utc), entries=(other,))
        assert WP.decide(s, arm.who("supervisor.sam"), row.id, systems, approve=True, reason="").status == "approved"


def test_an_outage_during_the_recheck_approves_nothing(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = requested(arm, s)
        systems = Changed(arm.systems(case.received_at_utc), down=True)
        with pytest.raises(svc.WorkflowError, match="nothing was approved"):
            WP.decide(s, arm.who("supervisor.sam"), row.id, systems, approve=True, reason="")
        assert case.status == CaseState.PENDING_APPROVAL and approval_of(s, row) is None


def test_a_rejection_needs_no_recheck(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = requested(arm, s)
        systems = Changed(arm.systems(case.received_at_utc), down=True)
        assert (
            WP.decide(s, arm.who("supervisor.sam"), row.id, systems, approve=False, reason="No.").status == "rejected"
        )
        assert case.status == CaseState.REJECTED


# ---------- executing ----------


@pytest.mark.parametrize(("change", "reason"), CHANGES)
def test_changed_evidence_stops_an_execution_with_nothing_submitted(
    arm: ArmA, change: dict[str, Any], reason: str
) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        systems = Changed(arm.systems(case.received_at_utc), **change)
        result = WP.execute(s, arm.who("supervisor.sam"), row.id, systems)
        assert result.status == "invalidated" and systems.submits == 0
        assert case.status == CaseState.INVESTIGATING and row.status == "invalidated"
        assert _matches(row.invalidated_reason, reason)


@pytest.mark.parametrize(
    ("target", "name", "value"),
    [
        ("row", "points", 1),
        ("row", "member_number", "GR-00000"),
        ("row", "stay_id", "BR-0000"),
        ("row", "reason_code", "goodwill"),
        ("row", "policy_refs", ["missing-points-requests@v2"]),
        ("row", "evidence_hash", "0" * 64),
        ("approval", "decided_by", "supervisor.sky"),
        ("approval", "expires_at_utc", "2099-01-01T00:00:00Z"),
        ("approval", "uid", "0" * 32),
        ("approval", "binding_mac", "0" * 64),
        ("approval", "binding_mac", None),
    ],
)
def test_editing_any_bound_field_in_the_database_ends_the_approval(
    arm: ArmA, target: str, name: str, value: object
) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s)
        approval = approval_of(s, row)
        assert approval is not None
        setattr(row if target == "row" else approval, name, value)
        s.commit()
        systems = Changed(arm.systems(case.received_at_utc))
        result = WP.execute(s, arm.who("supervisor.sam"), row.id, systems)
        assert result.status == "invalidated" and systems.submits == 0
        assert row.invalidated_reason == "binding_mismatch"


def test_an_approval_from_before_binding_must_be_approved_again(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = requested(arm, s)
        s.add(
            Approval(
                adjustment_request_id=row.id,
                uid="old-approval-from-milestone-five",
                decided_by="supervisor.sam",
                decision="approved",
                decided_at_utc="2026-11-01T00:00:00Z",
            )
        )
        row.status = "approved"
        svc.move(case, CaseState.APPROVED)
        s.commit()
        systems = Changed(arm.systems(case.received_at_utc))
        assert WP.execute(s, arm.who("supervisor.sam"), row.id, systems).status == "invalidated"
        assert systems.submits == 0 and row.invalidated_reason == "binding_mismatch"


def test_another_secret_cannot_use_the_approval(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s, wp=SharedWritePath(secret_key="the-secret-at-approval-time-0001"))
        rotated = SharedWritePath(secret_key="the-secret-after-rotation-0002")
        assert rotated.execute(s, arm.who("supervisor.sam"), row.id, arm.systems(case.received_at_utc)).status == (
            "invalidated"
        )


def test_no_secret_refuses_to_bind(arm: ArmA, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_SECRET_KEY")
    with arm.sessions() as s:
        case, row = requested(arm, s)
        with pytest.raises(svc.WorkflowError, match="APP_SECRET_KEY"):
            WP.decide(s, arm.who("supervisor.sam"), row.id, arm.systems(case.received_at_utc), approve=True, reason="")


@pytest.mark.parametrize(
    ("hours_later", "status"),
    [(23, "applied"), (24, "invalidated"), (25, "invalidated")],
)
def test_an_approval_lasts_twenty_four_hours(arm: ArmA, hours_later: int, status: str) -> None:
    decided = "2026-11-01T12:00:00Z"
    with arm.sessions() as s:
        case, row = approved(arm, s, wp=SharedWritePath(clock=lambda: decided))
        day = 1 + (12 + hours_later) // 24
        later = f"2026-11-{day:02d}T{(12 + hours_later) % 24:02d}:00:00Z"
        wp = SharedWritePath(clock=lambda: later)
        assert wp.execute(s, arm.who("supervisor.sam"), row.id, arm.systems(case.received_at_utc)).status == status
        if status == "invalidated":
            assert row.invalidated_reason == "expired" and case.status == CaseState.INVESTIGATING


def test_a_posting_that_lands_after_approval_stops_the_execution(arm: ArmA) -> None:
    """The labeler's planted event for D11, on the real mock API with its simulated clock."""
    with arm.sessions() as s:
        case, row = approved(arm, s, LATE_POSTING, LATE_MEMBER, LATE_STAY)
        case.sim_now_utc = "2026-04-27T00:00:00Z"
        s.commit()
        systems = Changed(arm.systems(svc.read_time(case)))
        result = WP.execute(s, arm.who("supervisor.sam"), row.id, systems)
        assert result.status == "invalidated" and systems.submits == 0
        assert row.invalidated_reason in ("outcome_changed", "amount_changed", "evidence_changed")


def test_after_invalidation_a_new_request_gets_a_new_approval_and_key(arm: ArmA) -> None:
    from app.services.write_path import idempotency_key

    with arm.sessions() as s:
        case, row = approved(arm, s)
        first = approval_of(s, row)
        assert first is not None
        first_key = idempotency_key("hg-demo", first)
        systems = Changed(arm.systems(case.received_at_utc), stay={"taxes_cents": 999})
        assert WP.execute(s, arm.who("supervisor.sam"), row.id, systems).status == "invalidated"
        with pytest.raises(svc.WorkflowError, match="only an approved"):
            WP.execute(s, arm.who("supervisor.sam"), row.id, arm.systems(case.received_at_utc))

        again = svc.request_adjustment(s, arm.who("agent.ana"), case, arm.rules)
        assert again.id != row.id
        systems = arm.systems(case.received_at_utc)
        assert WP.decide(s, arm.who("supervisor.sam"), again.id, systems, approve=True, reason="").status == "approved"
        second = approval_of(s, again)
        assert second is not None and idempotency_key("hg-demo", second) != first_key
        assert WP.execute(s, arm.who("supervisor.sam"), again.id, systems).status == "applied"
        assert case.status == CaseState.RESOLVED


@pytest.mark.parametrize("scenario", ["D06", "D07"])
def test_the_recheck_does_not_quietly_fix_arm_as_defects(arm: ArmA, scenario: str) -> None:
    """ADR-0044: arm A can't see the posting queue (D06) or link a re-post to its stay (D07), so it adjusts, and its own
    re-check must not stop it. The platform stopping these would hand arm A a fix the catalog gives to arm B."""
    case_id = arm.scenario(scenario)
    facts = arm.labels[case_id]["facts"]
    with arm.sessions() as s:
        case, row = requested(arm, s, case_id, facts["claimant"], facts["claimed_stay_ids"][0])
        systems = Changed(arm.systems(case.received_at_utc))
        assert WP.decide(s, arm.who("supervisor.sam"), row.id, systems, approve=True, reason="").status == "approved"
        assert WP.execute(s, arm.who("supervisor.sam"), row.id, systems).status == "applied"
        assert systems.submits == 1


# ---------- publishing a policy ----------


def retroactive_v3(s: Session) -> int:
    """A next version with the same rule values from 2026-07-05: the golden cases pass, but stays from then on change
    version."""
    row = policy_publishing.create_draft(s, ADMIN, draft_text(effective_from="2026-07-05", wait=14), "hg-demo")
    return row.id


def test_a_policy_change_ends_only_the_approvals_it_affects(arm: ArmA) -> None:
    with arm.sessions() as s:
        pending_case, pending = requested(arm, s, LATER_K01, LATER_MEMBER, LATER_STAY)
        old_case, old = approved(arm, s)  # checks out in 2025: version 1 still applies
        draft_id = retroactive_v3(s)
        policy_publishing.publish(s, ADMIN, draft_id, CONFIG)
        assert pending.status == "invalidated" and pending.invalidated_reason == "policy_changed"
        assert pending_case.status == CaseState.INVESTIGATING
        event = events(s, pending_case)[-1]
        assert event.action == "approval_invalidated" and event.actor == "admin.ada"
        assert event.detail["in_force"] == ["guest-rewards-earning@v2", "missing-points-requests@v3"]
        assert old.status == "approved" and old_case.status == CaseState.APPROVED


def test_a_policy_change_ends_an_approved_adjustment_too(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s, LATER_K01, LATER_MEMBER, LATER_STAY)
        policy_publishing.publish(s, ADMIN, retroactive_v3(s), CONFIG)
        assert row.status == "invalidated" and case.status == CaseState.INVESTIGATING
        with pytest.raises(svc.WorkflowError, match="only an approved"):
            WP.execute(s, arm.who("supervisor.sam"), row.id, arm.systems(case.received_at_utc))


def test_a_future_dated_policy_ends_nothing(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s, LATER_K01, LATER_MEMBER, LATER_STAY)
        draft = policy_publishing.create_draft(s, ADMIN, draft_text(), "hg-demo")
        policy_publishing.publish(s, ADMIN, draft.id, CONFIG)
        assert row.status == "approved" and case.status == CaseState.APPROVED
        assert WP.execute(s, arm.who("supervisor.sam"), row.id, arm.systems(case.received_at_utc)).status == "applied"


@pytest.mark.parametrize("state", [CaseState.EXECUTING, CaseState.EXECUTION_UNKNOWN])
def test_a_policy_change_leaves_a_submitted_adjustment_to_reconciliation(arm: ArmA, state: CaseState) -> None:
    with arm.sessions() as s:
        case, row = approved(arm, s, LATER_K01, LATER_MEMBER, LATER_STAY)
        case.status, row.status = state.value, "executing"
        s.commit()
        policy_publishing.publish(s, ADMIN, retroactive_v3(s), CONFIG)
        assert case.status == state and row.status == "executing"


def test_a_refused_publish_invalidates_nothing(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = requested(arm, s, LATER_K01, LATER_MEMBER, LATER_STAY)
        draft = policy_publishing.create_draft(s, ADMIN, draft_text(effective_from="2026-07-05", wait=30), "hg-demo")
        with pytest.raises(policy_publishing.PublishRefused):
            policy_publishing.publish(s, ADMIN, draft.id, CONFIG)
        assert row.status == "pending" and case.status == CaseState.PENDING_APPROVAL


# ---------- in the console ----------


def test_the_console_says_when_an_approval_could_not_stand(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = requested(arm, s, LATER_K01, LATER_MEMBER, LATER_STAY)
        case_id, request_id = case.id, row.id
        policy_publishing.publish(s, ADMIN, retroactive_v3(s), CONFIG)
        row.status, case.status = "pending", CaseState.PENDING_APPROVAL.value  # as if the supervisor's page was stale
        s.commit()
    b = Browser(TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory())))
    b.login("supervisor.sam", arm.password)
    done = b.post(f"/adjustments/{request_id}/decide", decision="approve")
    assert field(done.text, "case-status") == "Investigating"
    assert "so it can&#39;t stand" in field(done.text, "message")
    assert "policy_changed" in done.text and "approval_invalidated" in done.text
    page = b.get(f"/cases/{case_id}")
    assert "Execute adjustment" not in page.text
