"""Running one dataset case through one arm, from the first message to the settled ledger (F6, F7; RFC-0003).

The arms' scripted agents read no labels. This module is the evaluator around them: it plays the simulated member, lands
the planted late postings, and records what happened as a `CaseResult`. The label is used here only to answer as the
member and to know when a planted event happens, never to tell an arm anything else.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.arms.conventional import signals
from app.arms.legacy.checklist import Outcome
from app.arms.legacy.keyword_index import KeywordIndex
from app.arms.legacy.rules import LegacyRules
from app.domain.case_states import CaseState
from app.domain.eligibility import Eligibility, NextAction
from app.domain.roles import Identity
from app.persistence.models import (
    AdjustmentRequestRow,
    AiRun,
    Approval,
    Case,
    CaseEvidence,
    CaseRequest,
    Recommendation,
)
from app.ports.customer_systems import CustomerSystems
from app.services import cases as svc
from app.services import conventional
from app.services.cases import IntakeRequest
from app.services.write_path import DecisionResult, ExecutionResult, SharedWritePath, WritePath
from benchmarks.agents.as_is_write_path import AsIsWritePath
from benchmarks.agents.conventional_scripted import ScriptedConventionalAgent
from benchmarks.agents.legacy_scripted import ScriptedLegacyAgent
from benchmarks.intake import INTAKE, DatasetCase, load_case
from evaluations import member
from evaluations.scoring import CaseResult, Label
from evaluations.world import CUSTOMER, World

_ARM_A_ACTIONS = {
    Outcome.ADJUST.value: NextAction.ADJUST.value,
    Outcome.ALREADY_CREDITED.value: NextAction.NO_ADJUSTMENT_CREDITED.value,
    Outcome.WAIT.value: NextAction.WAIT_UNTIL.value,
    Outcome.NOT_CHECKED_OUT.value: NextAction.NOT_CHECKED_OUT.value,
    Outcome.DENY_CHANNEL.value: NextAction.DENY.value,
    Outcome.DENY_CLAIM_WINDOW.value: NextAction.DENY.value,
}
_ARM_A_ELIGIBILITY = {
    NextAction.ADJUST.value: Eligibility.ELIGIBLE.value,
    NextAction.NO_ADJUSTMENT_CREDITED.value: Eligibility.ELIGIBLE.value,
    NextAction.WAIT_UNTIL.value: Eligibility.INELIGIBLE.value,
    NextAction.NOT_CHECKED_OUT.value: Eligibility.INELIGIBLE.value,
    NextAction.DENY.value: Eligibility.INELIGIBLE.value,
    NextAction.REQUEST_INFO.value: Eligibility.INSUFFICIENT_EVIDENCE.value,
}
_ASKED = ("asked_for_english", "asked_for_member_number", "asked_for_confirmation")
LEGACY_POLICY = "missing-points-requests"
_OUTCOME_ORDER = ("adjusted", "escalated", "denied", "no_adjustment", "unresolved")


def arm_a_first_action(path: list[str]) -> str:
    """The first thing arm A's script decided, in the labels' vocabulary."""
    for step in path:
        if step in _ASKED:
            return NextAction.REQUEST_INFO.value
        if step in ("member_not_found", "stay_not_found"):
            return NextAction.DENY.value
        if step.startswith("checklist:"):
            return _ARM_A_ACTIONS.get(step.split(":", 1)[1], NextAction.ESCALATE.value)
    return "none"  # in the billing queue: nobody worked it


def first_result(recommendations: list[Recommendation]) -> Recommendation | None:
    """The arm's first recommended action. Arm C's investigation writes arm B's result first, and its own answer when
    the model finishes, so its first answer is the first row with a model run. Arm B has only the one kind."""
    for rec in recommendations:
        if rec.ai_run_id is not None:
            return rec
    return recommendations[0] if recommendations else None


def outcome_of(case: Case) -> str:
    state = CaseState(case.status)
    if state is CaseState.ESCALATED:
        return "escalated"
    if state is CaseState.REJECTED:
        return "no_adjustment"
    if state is CaseState.RESOLVED:
        code = case.resolution_code or ""
        if code.startswith("deny"):
            return "denied"
        return "no_adjustment" if code.startswith(("no_adjustment", "wait_until", "not_checked_out")) else "adjusted"
    return "unresolved"


def combined_outcome(outcomes: list[str]) -> str:
    """Several cases can serve one request. A credit on any of them means it was adjusted."""
    return next((name for name in _OUTCOME_ORDER if name in outcomes), "unresolved")


class _LostOnce:
    """The platform completes the first attempt and drops the reply (catalog section 3a). Evaluator only."""

    def __init__(self, systems: CustomerSystems, lossy: CustomerSystems) -> None:
        self._systems, self._lossy = systems, lossy
        self._lost = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._systems, name)

    def submit_adjustment(self, request: Any, idempotency_key: str) -> Any:
        if self._lost:
            return self._systems.submit_adjustment(request, idempotency_key)
        self._lost = True
        return self._lossy.submit_adjustment(request, idempotency_key)


class _HarnessWritePath:
    """What the evaluator plants around a write path, for every arm alike. It decides nothing itself.

    - A late posting lands between approval and execution, so a re-check can see it (D11).
    - With several contacts about one stay, execution waits until all of them are worked. That's the catalog's D10:
      two cases approved before either credit lands.
    - In the fault pass, the first submit for each request completes and its reply is lost.
    """

    def __init__(self, world: World, inner: Any, fault: str | None = None) -> None:
        self.world, self.fault = world, fault
        self.inner: WritePath = inner
        self.late: dict[str, str] = {}
        self.defer = False
        self.waiting: list[tuple[Identity, int]] = []
        self.faulted: set[int] = set()

    def decide(
        self, s: Session, who: Identity, request_id: int, systems: CustomerSystems, *, approve: bool, reason: str
    ) -> DecisionResult:
        return self.inner.decide(s, who, request_id, systems, approve=approve, reason=reason)

    def check_status(self, s: Session, who: Identity, request_id: int, systems: CustomerSystems) -> ExecutionResult:
        return self.inner.check_status(s, who, request_id, systems)

    def execute(self, s: Session, who: Identity, request_id: int, systems: CustomerSystems) -> ExecutionResult:
        if self.defer:
            self.waiting.append((who, request_id))
            return ExecutionResult("queued", "Waiting until the other contacts about this stay are worked.")
        return self._execute_now(s, who, request_id, systems)

    def _execute_now(self, s: Session, who: Identity, request_id: int, systems: CustomerSystems) -> ExecutionResult:
        row = s.get(AdjustmentRequestRow, request_id)
        assert row is not None
        case = s.get(Case, row.case_id)
        assert case is not None
        moment = self.late.get(case.source_ref or "")
        if moment:
            case.sim_now_utc = moment
            s.commit()
            systems = self.world.systems(moment)
        if self.fault and request_id not in self.faulted:
            self.faulted.add(request_id)
            lossy = self.world.systems(svc.read_time(case), self.fault)
            systems = cast(CustomerSystems, _LostOnce(systems, lossy))
        return self.inner.execute(s, who, request_id, systems)

    def flush(self, s: Session) -> None:
        """Run what waited, in order, and check any uncertain outcome once, as the scripts do."""
        waiting, self.waiting, self.defer = self.waiting, [], False
        for who, request_id in waiting:
            row = s.get(AdjustmentRequestRow, request_id)
            assert row is not None
            case = s.get(Case, row.case_id)
            assert case is not None
            s.refresh(case)
            if CaseState(case.status) is not CaseState.APPROVED:
                continue
            systems = self.world.systems(svc.read_time(case))
            self._execute_now(s, who, request_id, systems)
            s.refresh(case)
            if CaseState(case.status) is CaseState.EXECUTION_UNKNOWN:
                self.inner.check_status(s, who, request_id, systems)


def late_postings(label: Label) -> str | None:
    """When the planted posting lands, if there is one."""
    wanted = set(label["facts"].get("harness_late_postings") or [])
    times = [e["posted_at_utc"] for e in label["facts"]["ledger"] if e["entry_id"] in wanted]
    return max(times) if times else None


@dataclass
class _Trace:
    """What one journey did, for the result."""

    cases: list[Case] = field(default_factory=list)
    first_action: str = ""
    contacts: int = 0
    info_requests: int = 0
    reopened: bool = False
    waited_days: int = 0
    in_billing_queue: bool = False


def _reply_request(original: IntakeRequest, answer: member.Answer, at: str | None = None) -> IntakeRequest:
    return IntakeRequest(
        received_at_utc=at or original.received_at_utc,
        contact_channel=original.contact_channel,
        text=answer.text,
        sender_email=original.sender_email,
        form_member_number=answer.member_number or original.form_member_number,
        form_confirmation=answer.confirmation or original.form_confirmation,
        form_name=original.form_name,
        form_property=original.form_property,
    )


class Journey:
    """One arm's agent, in one world, for one run."""

    def __init__(
        self,
        world: World,
        s: Session,
        arm: str,
        ai_runtime: Any = None,
        *,
        second_look: bool = False,
        as_is_database: Path | None = None,
        fault: str | None = None,
    ) -> None:
        self.world, self.s, self.arm = world, s, arm
        self.result_arm = "A_as_is" if as_is_database else arm
        self.provider = ai_runtime.provider if ai_runtime else None
        # Off for the main analysis: agents follow their scripts as written (RFC-0003). On only for the sensitivity run.
        self.second_look = second_look
        inner: Any = (
            AsIsWritePath(as_is_database) if as_is_database else SharedWritePath(CUSTOMER, secret_key=world.secret_key)
        )
        write_path = _HarnessWritePath(world, inner, fault)
        self.harness = write_path
        if arm == "A":
            self.legacy = ScriptedLegacyAgent(
                s, world.systems, LegacyRules.load(CUSTOMER), KeywordIndex.load(), write_path
            )
        else:
            self.conventional = ScriptedConventionalAgent(s, world.systems, CUSTOMER, write_path, ai_runtime)

    # ---------- arm A: every reply is a new case, as the legacy tool has it (D10) ----------

    def _work_a(self, case: Case, label: Label, trace: _Trace, original: IntakeRequest) -> None:
        run = self.legacy.run(case)
        trace.cases.append(case)
        if not trace.first_action:
            trace.first_action = arm_a_first_action(run.path)
            trace.in_billing_queue = "in_billing_queue" in run.path
        self._look_again_a(case)
        asked = next((step for step in run.path if step in _ASKED), None)
        if asked is None:
            self._maybe_return_a(case, label, trace, original)
            return
        trace.info_requests += 1
        if trace.info_requests > member.MAX_REPLIES:
            return
        answer = member.answer(asked, label, original.text)
        trace.contacts += 1
        request = _reply_request(original, answer)
        follow_up = svc.create_case(
            self.s, INTAKE, request, customer_id=CUSTOMER, source_ref=case.source_ref, arm=self.arm
        )
        self._work_a(follow_up, label, trace, original)

    def _look_again_a(self, case: Case) -> None:
        """SENSITIVITY VARIANT ONLY: a person closes a case the re-check stopped. Not what arm A's script does.

        The main analysis leaves the case in `Investigating`, as the script does (RFC-0003). This shows what that choice
        costs. Arm A's checklist reads the ledger as of the claim, and would ask for the credit again, so the variant
        closes on the re-read ledger, logged as an override if the checklist disagrees.
        """
        if not self.second_look:
            return
        self.s.refresh(case)
        if CaseState(case.status) is not CaseState.INVESTIGATING:
            return
        stopped = self.s.scalars(
            select(AdjustmentRequestRow).where(
                AdjustmentRequestRow.case_id == case.id, AdjustmentRequestRow.invalidated_reason == "outcome_changed"
            )
        ).first()
        if stopped is None:
            return
        agent = self.legacy
        systems = self.world.systems(svc.read_time(case))
        svc.attach_ledger(self.s, agent.agent, case, systems, stopped.member_number, True)
        svc.close_case(
            self.s,
            agent.agent,
            case,
            "no_adjustment_credited",
            "The re-check found the points had posted.",
            agent.rules,
        )
        self.s.refresh(case)

    def _maybe_return_a(self, case: Case, label: Label, trace: _Trace, original: IntakeRequest) -> None:
        if case.resolution_code != "wait_until" or trace.reopened:
            return
        wait = svc.checklist_for(self.s, case, self.legacy.rules).wait_until
        if wait:
            self._return_after_waiting(case, wait, label, trace, original)

    # ---------- arms B and C ----------

    def _work_b(self, case: Case, label: Label, trace: _Trace, original: IntakeRequest) -> None:
        agent = self.conventional
        run = agent.run(case)
        trace.cases.append(case)
        trace.in_billing_queue = trace.in_billing_queue or "in_billing_queue" in run.path
        self._record_first_b(case, trace)
        self._look_again_b(case)
        for reference in run.linked:
            linked = self.s.scalars(select(Case).where(Case.reference == reference)).one()
            trace.cases.append(linked)
        self._answer_b(case, label, trace, original)
        if "asked_about_more_stays" in run.path:
            self._other_stays_b(case, label, trace, original)
        self._maybe_return_b(case, label, trace, original)

    def _look_again_b(self, case: Case) -> None:
        """SENSITIVITY VARIANT ONLY: investigate again after the re-check stopped a credit (RFC-0003)."""
        if not self.second_look:
            return
        self.s.refresh(case)
        if CaseState(case.status) is CaseState.INVESTIGATING and case.queue == signals.POINTS_QUEUE:
            self.conventional.look_again(case, [])
            self.s.refresh(case)

    def _record_first_b(self, case: Case, trace: _Trace) -> None:
        if trace.first_action:
            return
        query = select(Recommendation).where(Recommendation.case_id == case.id).order_by(Recommendation.id)
        first = first_result(list(self.s.scalars(query)))
        trace.first_action = first.action if first else "none"

    def _answer_b(self, case: Case, label: Label, trace: _Trace, original: IntakeRequest) -> None:
        agent = self.conventional
        path: list[str] = []
        while CaseState(case.status) is CaseState.AWAITING_INFORMATION:
            trace.info_requests += 1
            if trace.info_requests > member.MAX_REPLIES:
                return
            rec = conventional.latest_recommendation(self.s, case)
            answer = member.answer((rec.detail or "") if rec else "", label, original.text)
            trace.contacts += 1
            conventional.supply_information(
                self.s,
                agent.agent,
                case,
                reply_text=answer.text,
                booking_channel=answer.booking_channel,
                member_number=answer.member_number,
                confirmation=answer.confirmation,
            )
            agent.after_reply(case, path)
            self.s.refresh(case)

    def _other_stays_b(self, case: Case, label: Label, trace: _Trace, original: IntakeRequest) -> None:
        """The member names the other stay they mentioned (D16), with their first message, so they can be identified."""
        ids = [c.id for c in trace.cases]
        rows = self.s.scalars(select(Recommendation.stay_id).where(Recommendation.case_id.in_(ids)))
        handled = {stay for stay in rows if stay}
        for stay in member.other_stays(label, handled):
            trace.contacts += 1
            answer = member.Answer(text=f"{original.text}\nThe other stay is {stay}.", confirmation=stay)
            request = _reply_request(original, answer)
            other = svc.create_case(
                self.s, INTAKE, request, customer_id=CUSTOMER, source_ref=case.source_ref, arm=self.arm
            )
            self._work_b(other, label, trace, original)

    def _maybe_return_b(self, case: Case, label: Label, trace: _Trace, original: IntakeRequest) -> None:
        if case.resolution_code != "wait_until" or trace.reopened:
            return
        rec = conventional.latest_recommendation(self.s, case)
        if rec and rec.detail:
            self._return_after_waiting(case, rec.detail, label, trace, original)

    # ---------- the member comes back when told to wait (F6) ----------

    def _return_after_waiting(
        self, case: Case, wait_until: str, label: Label, trace: _Trace, original: IntakeRequest
    ) -> None:
        moment = member.return_moment(wait_until)
        stays = [stay["stay_id"] for stay in label["stays"]]
        earned = {stay["stay_id"]: stay["expected_final_points"] for stay in label["stays"]}
        if all(self.world.points_by(stay, moment) >= earned[stay] for stay in stays):
            return  # the points arrived while they waited
        trace.reopened = True
        trace.contacts += 1
        received = date.fromisoformat(original.received_at_utc[:10])
        trace.waited_days += max(0, (date.fromisoformat(wait_until[:10]) - received).days)
        answer = member.Answer(text=original.text)
        back = svc.create_case(
            self.s,
            INTAKE,
            _reply_request(original, answer, at=moment),
            customer_id=CUSTOMER,
            source_ref=case.source_ref,
            arm=self.arm,
        )
        if self.arm == "A":
            self._work_a(back, label, trace, original)
        else:
            self._work_b(back, label, trace, original)

    # ---------- one dataset case ----------

    def run(self, item: DatasetCase, label: Label, run_number: int, kind: str) -> CaseResult:
        moment = late_postings(label)
        if moment:
            self.harness.late[item.case_id] = moment
        started = time.perf_counter()
        created = load_case(self.s, item, CUSTOMER, self.arm)
        trace = _Trace(contacts=len(created))
        self.harness.defer = len(created) > 1
        for case, original in zip(created, item.requests, strict=False):
            if self.arm == "A":
                self._work_a(case, label, trace, original)
            else:
                self._work_b(case, label, trace, original)
        self.harness.flush(self.s)
        elapsed = time.perf_counter() - started
        return self._result(item, label, run_number, kind, trace, elapsed)

    def _result(
        self, item: DatasetCase, label: Label, run_number: int, kind: str, trace: _Trace, elapsed: float
    ) -> CaseResult:
        s = self.s
        s.expire_all()
        ids = [case.id for case in trace.cases]
        stays = {stay["stay_id"] for stay in label["stays"]}
        final = self.world.final_points(stays)
        requests = list(s.scalars(select(AdjustmentRequestRow).where(AdjustmentRequestRow.case_id.in_(ids))))
        approvals = list(
            s.scalars(select(Approval).where(Approval.adjustment_request_id.in_([r.id for r in requests])))
        )
        approved = any(a.decision == "approved" for a in approvals) if approvals else None
        executed = any(r.status == "executed" for r in requests)
        runs = list(
            s.scalars(select(AiRun).where(AiRun.case_id.in_(ids)))
        )  # for arm C, latency is the worst investigation
        return CaseResult(
            case_id=item.case_id,
            arm=self.result_arm,
            run=run_number,
            kind=kind,
            first_action=trace.first_action or "none",
            outcome=combined_outcome([outcome_of(case) for case in trace.cases]),
            final_points=final,
            duplicate_credits=self._duplicates(stays),
            unauthorized_actions=self._unauthorized(requests, approvals),
            contacts=trace.contacts,
            identified_stays=self._identified(ids),
            evidence_seen=self._evidence(ids),
            policies=self._policies(ids),
            eligibility=self._eligibility(trace, ids),
            approved=approved,
            executed=executed,
            latency_s=round(max((r.elapsed_ms for r in runs), default=elapsed * 1000) / 1000, 3),
            input_tokens=sum(r.input_tokens for r in runs),
            output_tokens=sum(r.output_tokens for r in runs),
            cost_usd=sum(r.cost_microusd for r in runs) / 1_000_000,
            ai_runs=len(runs),
            ai_fallbacks=sum(1 for r in runs if r.status != "finished"),
            ai_stops=tuple(r.stop_reason or "" for r in runs),
            interrupted=bool(getattr(self.provider, "stopped", False)),
            reopened=trace.reopened,
            simulated_days=member.simulated_days(trace.info_requests, trace.waited_days, trace.in_billing_queue),
        )

    def _duplicates(self, stays: set[str]) -> int:
        """H6: two adjustments for one stay on the platform."""
        return sum(count - 1 for count in self.world.adjustments_per_stay(stays).values() if count > 1)

    @staticmethod
    def _unauthorized(requests: list[AdjustmentRequestRow], approvals: list[Approval]) -> int:
        """H6: a self-approval, or a credit with no approval behind it, as the database shows them."""
        by_request = {a.adjustment_request_id: a for a in approvals}
        count = 0
        for row in requests:
            approval = by_request.get(row.id)
            if approval is not None and approval.decided_by == row.requested_by:
                count += 1
            if row.status == "executed" and (approval is None or approval.decision != "approved"):
                count += 1
        return count

    def _identified(self, ids: list[int]) -> tuple[str, ...]:
        if self.arm == "A":
            query = select(CaseEvidence.source_ref).where(CaseEvidence.case_id.in_(ids), CaseEvidence.kind == "stay")
            return tuple(sorted(set(self.s.scalars(query))))
        query_b = select(Recommendation.stay_id).where(Recommendation.case_id.in_(ids))
        return tuple(sorted({stay for stay in self.s.scalars(query_b) if stay}))

    def _evidence(self, ids: list[int]) -> tuple[str, ...]:
        """In the labels' terms. Only what an arm's records show it looked at, so a missing record fails the link."""
        seen: set[str] = set()
        rows = list(self.s.scalars(select(CaseEvidence).where(CaseEvidence.case_id.in_(ids))))
        for row in rows:
            seen.update(_evidence_names(row))
        if self.arm != "A":
            for rec in self.s.scalars(select(Recommendation).where(Recommendation.case_id.in_(ids))):
                seen.update(f"policy:{c['policy_id']}@v{c['version']}" for c in rec.citations)
                if rec.member_number:
                    seen.add("member_record")
            requests = self.s.scalars(select(CaseRequest).where(CaseRequest.case_id.in_(ids)))
            if any(request.attachment_names for request in requests):
                seen.add("attachment")
        return tuple(sorted(seen))

    def _policies(self, ids: list[int]) -> dict[str, tuple[str, ...]]:
        """What each stay's decision relied on. Arm A's rules have dated revisions and its policy hits name no version
        (D15), so its version is the position of the revision it applied: revisions and policy versions match one to one
        (`tests/test_runner.py`)."""
        if self.arm == "A":
            return self._policies_a(ids)
        out: dict[str, set[str]] = {}
        for rec in self.s.scalars(select(Recommendation).where(Recommendation.case_id.in_(ids))):
            if rec.stay_id:
                cited = {f"{c['policy_id']}@v{c['version']}" for c in rec.citations}
                out.setdefault(rec.stay_id, set()).update(cited)
        for row in self.s.scalars(select(AdjustmentRequestRow).where(AdjustmentRequestRow.case_id.in_(ids))):
            out.setdefault(row.stay_id, set()).update(row.policy_refs or [])
        return {stay: tuple(sorted(names)) for stay, names in out.items()}

    def _policies_a(self, ids: list[int]) -> dict[str, tuple[str, ...]]:
        out: dict[str, tuple[str, ...]] = {}
        rules = self.legacy.rules
        for case_id in ids:
            case = self.s.get(Case, case_id)
            assert case is not None
            stays = list(
                self.s.scalars(
                    select(CaseEvidence.source_ref).where(CaseEvidence.case_id == case_id, CaseEvidence.kind == "stay")
                )
            )
            if not stays:
                continue
            revision = svc.checklist_for(self.s, case, rules).rules_revision or ""
            days = [r.effective_from.isoformat() for r in rules.revisions]
            day = revision.rsplit(" ", 1)[-1]
            if day in days:
                for stay in stays:
                    out[stay] = (f"{LEGACY_POLICY}@v{days.index(day) + 1}",)
        return out

    def _eligibility(self, trace: _Trace, ids: list[int]) -> str | None:
        if self.arm == "A":
            return _ARM_A_ELIGIBILITY.get(trace.first_action)
        query = select(Recommendation).where(Recommendation.case_id.in_(ids)).order_by(Recommendation.id)
        first = first_result(list(self.s.scalars(query)))
        return first.status if first else None


def _evidence_names(row: CaseEvidence) -> set[str]:
    snapshot = row.snapshot if isinstance(row.snapshot, dict) else {}
    names: set[str] = set()
    if row.kind == "member":
        names.add("member_record")
    elif row.kind == "stay":
        names.add("stay_record")
    elif row.kind == "ledger":
        names.add("ledger")
    elif row.kind == "policy":
        names.add(f"policy:{row.source_ref.split('#', 1)[0]}")
    if snapshot.get("member"):
        names.add("member_record")
    if snapshot.get("records") or snapshot.get("stay_found_by"):  # looked for it, even if it's missing upstream (D24)
        names.add("stay_record")
    if "ledger" in snapshot:
        names.add("ledger")
    if snapshot.get("postings"):
        names.add("posting_queue")
    if snapshot.get("duplicate_profiles"):
        names.add("linked_profile")
    if snapshot.get("merged_profiles"):
        names.add("merge_map")
    if snapshot.get("member_stays"):
        names.add("all_stay_records")
    if snapshot.get("documents"):
        names.add("attachment")
    records = snapshot.get("records") or [snapshot]
    if any(isinstance(record, dict) and record.get("partner_confirmation") for record in records):
        names.add("partner_confirmation")
    return names
