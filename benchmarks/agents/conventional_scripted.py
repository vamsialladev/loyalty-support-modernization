"""The scripted arm B agent: the same services the console uses, with ordinary accounts (spec B.8; ADR-0048, ADR-0064).

Labelled **scripted, not human timing**, like arm A's. It runs arm B's mechanics; Milestone 10 scores it. Its policy,
fixed here, doesn't read labels or generator metadata:

1. A case in the billing queue is not worked.
2. Ask the worker to investigate, and read the engine's result.
3. Act on that result: ask the member the structured question; escalate with the reason; request approval; or close with
   the code the result supports. It never goes against the engine, so it never logs an override.
4. If the message mentions more stays than the rules can identify, send the question about them and carry on (D16).
5. Several explicit stays become linked cases; the agent works each of them.

The **simulated supervisor** follows a documented review policy (spec F7): approve when the stored result is `adjust`
from the engine; otherwise reject with the reason. Real reviewer behaviour comes only from UAT participants.

    uv run python -m benchmarks.agents.conventional_scripted --split dev --cases DV-001   # mechanics only, no scores
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.arms.conventional import signals
from app.domain.case_states import CaseState
from app.domain.eligibility import NextAction
from app.domain.roles import Identity
from app.persistence.models import Case, CaseEvent
from app.ports.customer_systems import CustomerSystems
from app.services import cases as svc
from app.services import conventional
from app.services.job_handlers import build_handlers
from app.services.write_path import SharedWritePath, WritePath
from app.worker import Worker
from benchmarks.agents.legacy_scripted import LABEL, ensure_scripted_users

SystemsFactory = Callable[[str | None], CustomerSystems]


@dataclass
class ConventionalRun:
    case_reference: str
    source_ref: str | None
    final_status: str
    resolution_code: str | None
    steps: int
    elapsed_ms: float
    path: list[str] = field(default_factory=list)
    linked: list[str] = field(default_factory=list)
    label: str = LABEL


def simulated_review(checklist: dict[str, object]) -> tuple[bool, str]:
    """The simulated supervisor's deterministic review policy (labelled simulated)."""
    if checklist.get("source") == "engine" and checklist.get("outcome") == NextAction.ADJUST.value:
        return True, ""
    return False, "The stored result does not support this adjustment."


class ScriptedConventionalAgent:
    def __init__(
        self, s: Session, systems_for: SystemsFactory, customer_id: str = "hg-demo", write_path: WritePath | None = None
    ) -> None:
        self.s, self.systems_for, self.customer_id = s, systems_for, customer_id
        self.write_path = write_path or SharedWritePath(customer_id)
        self.agent, self.supervisor = ensure_scripted_users(s)
        handlers = build_handlers(self.write_path, systems_for)  # type: ignore[arg-type]
        self.worker = Worker(sessionmaker(bind=s.get_bind(), expire_on_commit=False), handlers)

    def run(self, case: Case) -> ConventionalRun:
        started = time.perf_counter()
        path: list[str] = []
        linked: list[str] = []
        if case.queue != signals.POINTS_QUEUE:
            path.append("in_billing_queue")
        else:
            self._investigate(case)
            self._act(case, path)
            for other in self._siblings(case):
                linked.append(other.reference)
                self.s.refresh(other)
                if CaseState(other.status) is CaseState.INVESTIGATING:
                    self._act(other, path)
        self.s.refresh(case)
        steps = len(list(self.s.scalars(select(CaseEvent.id).where(CaseEvent.case_id == case.id))))
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        return ConventionalRun(
            case.reference, case.source_ref, case.status, case.resolution_code, steps, elapsed, path, linked
        )

    def _siblings(self, case: Case) -> list[Case]:
        self.s.refresh(case)
        return [c for c in conventional.group_cases(self.s, case) if c.id != case.id]

    def _investigate(self, case: Case) -> None:
        conventional.start_investigation(self.s, self.agent, case)
        self.worker.drain()
        self.s.expire_all()

    def _act(self, case: Case, path: list[str]) -> None:
        s, agent = self.s, self.agent
        rec = conventional.latest_recommendation(s, case)
        assert rec is not None, f"{case.reference} has no result: the worker didn't finish"
        action = NextAction(rec.action)
        path.append(f"engine:{rec.action}" + (f":{rec.detail}" if rec.detail else ""))
        systems = self.systems_for(svc.read_time(case))
        if "more_stays_mentioned" in rec.flags and action is not NextAction.REQUEST_INFO:
            conventional.mention_more_stays(s, agent, case, systems)
            path.append("asked_about_more_stays")
        if action is NextAction.REQUEST_INFO:
            conventional.ask_member(s, agent, case, systems)
        elif action is NextAction.ESCALATE or action is NextAction.REFRESH_EVIDENCE:
            svc.escalate(s, agent, case, f"Engine result: {rec.detail or rec.action}.")
        elif action is NextAction.ADJUST:
            self._adjust(case, agent, systems, path)
        else:
            code = conventional.recommended_close_code(rec)
            assert code is not None
            conventional.close_case(s, agent, case, code)

    def _adjust(self, case: Case, agent: Identity, systems: CustomerSystems, path: list[str]) -> None:
        s = self.s
        outcome = conventional.request_adjustment(s, agent, case)
        if outcome.row is None:
            path.append("group_over_limit")
            return
        approve, reason = simulated_review(outcome.row.checklist)
        path.append("supervisor:" + ("approved" if approve else "rejected"))
        self.write_path.decide(s, self.supervisor, outcome.row.id, systems, approve=approve, reason=reason)
        s.refresh(case)
        if not approve or CaseState(case.status) is not CaseState.APPROVED:
            return
        result = self.write_path.execute(s, self.supervisor, outcome.row.id, systems)
        path.append(f"execute:{result.status}")
        s.refresh(case)
        if CaseState(case.status) is CaseState.EXECUTION_UNKNOWN:
            path.append(f"reconcile:{self.write_path.check_status(s, self.supervisor, outcome.row.id, systems).status}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m benchmarks.agents.conventional_scripted")
    parser.add_argument("--split", default="dev", choices=("dev", "validation"))
    parser.add_argument("--cases", required=True, help="comma-separated case IDs (mechanics check only)")
    args = parser.parse_args(argv)

    from app.persistence.database import make_engine, make_sessions
    from app.services.systems import mock_systems_factory
    from app.settings import AppSettings
    from benchmarks.intake import load_case, read_split

    settings = AppSettings.from_env()
    wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
    with make_sessions(make_engine(settings.database_url))() as s:
        agent = ScriptedConventionalAgent(s, mock_systems_factory(settings), settings.customer_id)
        for item in (c for c in read_split(args.split) if c.case_id in wanted):
            load_case(s, item, arm="B")
            query = select(Case).where(Case.source_ref == item.case_id, Case.arm == "B").order_by(Case.id)
            for case in s.scalars(query).all():
                if case.status != CaseState.NEW.value:
                    print(f"{item.case_id} {case.reference}: already worked ({case.status}); skipped")
                    continue
                run = agent.run(case)
                print(f"{item.case_id} {run.case_reference}: {run.steps} steps, {run.elapsed_ms} ms ({run.label})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
