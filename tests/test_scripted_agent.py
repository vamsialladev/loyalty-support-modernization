"""The scripted legacy agent (Appendix B; ADR-0048): mechanics only. Nothing here scores arm A against labels;
that is Milestone 10's job, after the thresholds file is committed (spec E.3, E.6).
"""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.domain.case_states import TERMINAL, CaseState
from app.persistence.models import Case, CaseEvent
from app.services import cases as svc
from app.services.instrumentation import events
from benchmarks.agents.legacy_scripted import (
    LABEL,
    SCRIPTED_AGENT,
    SCRIPTED_SUPERVISOR,
    ScriptedLegacyAgent,
    is_english,
    signoff_name,
    simulated_review,
)
from tests.arm_a import ArmA, make_arm_a

RESTING = {*TERMINAL, CaseState.AWAITING_INFORMATION}


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def agent_for(arm: ArmA, s: Any) -> ScriptedLegacyAgent:
    return ScriptedLegacyAgent(s, arm.factory(), arm.rules, arm.index)


def test_k01_runs_end_to_end_and_is_labelled_scripted(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, "DV-001")
        run = agent_for(arm, s).run(case)
        assert run.final_status == CaseState.RESOLVED and run.resolution_code == "adjusted"
        assert run.label == LABEL == "scripted, not human timing"
        assert run.steps == len(events(s, case)) and run.elapsed_ms > 0
        actors = {e.actor for e in events(s, case)}
        assert actors == {"intake", SCRIPTED_AGENT, SCRIPTED_SUPERVISOR}
        assert {e.actor_kind for e in events(s, case) if e.actor != "intake"} == {"scripted"}
        searches = [e.action for e in events(s, case) if e.action.startswith("search_")]
        assert {"search_member", "search_stay", "search_ledger", "search_policy"} <= set(searches)  # four screens


def test_instrumentation_records_inputs_by_kind_not_value(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, "DV-001")
        agent_for(arm, s).run(case)
        rows = [e for e in events(s, case) if e.action.startswith("search_")]
        text = repr([e.detail for e in rows])
        assert "GR-85640" not in text and "BR-6638" not in text and "@" not in text
        assert all(set(e.detail) == {"by", "results"} for e in rows)


def test_non_english_requests_get_a_request_for_english_d23(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, arm.scenario("D23"))
        run = agent_for(arm, s).run(case)
        assert run.path == ["asked_for_english"] and run.final_status == CaseState.AWAITING_INFORMATION


def test_a_billing_queue_case_is_left_alone_d20(arm: ArmA) -> None:
    refund = sorted(
        cid
        for cid, lab in arm.labels.items()
        if lab["split"] == "dev" and lab["scenarios"] == ["D20"] and "refund_request" in lab["out_of_scope_items"]
    )[0]
    with arm.sessions() as s:
        (case,) = arm.load(s, refund)
        run = agent_for(arm, s).run(case)
        assert run.path == ["in_billing_queue"] and run.final_status == CaseState.NEW


def test_a_d10_pair_is_worked_as_two_cases_with_one_credit(arm: ArmA) -> None:
    """Worked one after the other, the second case's ledger already shows the first case's credit."""
    with arm.sessions() as s:
        first, second = arm.load(s, arm.scenario("D10"))
        agent = agent_for(arm, s)
        assert agent.run(first).resolution_code == "adjusted"
        assert agent.run(second).resolution_code in {"no_adjustment_credited", "duplicate_prevented"}
        member = arm.labels[first.source_ref]["claimant_member_number"]
        stay = arm.labels[first.source_ref]["facts"]["claimed_stay_ids"][0]
    credits = [e for e in arm.systems().get_ledger(member) if e.kind == "adjustment" and e.stay_id == stay]
    assert len(credits) == 1


def test_every_dev_case_reaches_a_resting_state_without_errors(arm: ArmA, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mechanics over the whole dev split: no crash, no system error, every case ends somewhere a human would leave
    it. The agent must never open a label file while doing it."""
    from benchmarks.intake import read_split

    opened: list[str] = []
    real_open = builtins.open

    def watching_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    with arm.sessions() as s:
        from benchmarks.intake import load_case

        for item in read_split("dev", arm.datasets):  # loaded before the watch starts
            load_case(s, item)
        cases = list(s.scalars(select(Case).order_by(Case.id)))
        agent = agent_for(arm, s)
        monkeypatch.setattr(builtins, "open", watching_open)
        monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: opened.append(str(self)) or "")
        runs = [agent.run(case) for case in cases]
        monkeypatch.undo()
        assert not [p for p in opened if "labels" in p.replace("\\", "/")]
        assert len(runs) == 102  # 100 dev cases, two of them D10 pairs
        for run, case in zip(runs, cases, strict=True):
            assert CaseState(run.final_status) in RESTING or case.queue == "billing", (run.case_reference, run.path)
            assert run.steps >= 1 and run.label == LABEL
        # request_adjustment only accepts an "adjust" checklist, so the simulated supervisor must approve every one.
        assert [r.case_reference for r in runs if r.final_status == CaseState.REJECTED] == []
        errors = list(s.scalars(select(CaseEvent).where(CaseEvent.action == "system_error")))
        assert errors == []


def _intake(text: str, **form: str) -> Any:
    from app.services.cases import IntakeRequest

    return IntakeRequest(received_at_utc="2026-06-18T12:00:00Z", contact_channel="web_form", text=text, **form)


def test_with_nothing_to_search_it_asks_instead_of_denying(arm: ArmA) -> None:
    """ADR-0054: "not found" needs a search that found nothing. No number, name or email means no search."""
    with arm.sessions() as s:
        agent = agent_for(arm, s)
        case = svc.create_case(s, agent.agent, _intake("My points are missing from my last stay."))
        run = agent.run(case)
        assert run.path == ["asked_for_member_number"] and run.final_status == CaseState.AWAITING_INFORMATION
        assert run.resolution_code is None


def test_a_search_that_found_nothing_is_still_denied_as_not_found(arm: ArmA) -> None:
    with arm.sessions() as s:
        agent = agent_for(arm, s)
        request = _intake("My points are missing.", form_member_number="GR-00000")
        case = svc.create_case(s, agent.agent, request)
        run = agent.run(case)
        assert run.path == ["member_not_found"] and run.resolution_code == "deny_not_found"
        assert [e.detail["results"] for e in events(s, case) if e.action == "search_member"] == [0]
        assert events(s, case)[-1].detail["override"] is False


def test_reading_helpers() -> None:
    assert signoff_name("Hello\nThanks, Clara Kowalski") == "Clara Kowalski"
    assert signoff_name("Hello\nClara Kowalski") == "Clara Kowalski"
    assert signoff_name("Hello\nThank you!") is None
    assert is_english("Hello, I stayed at Beach Resort but the points are not on my account.")
    assert is_english("Missing points. Beach Resort, December 16-17, 2025.\nEthan Marsh")
    assert not is_english("Bonjour, j'ai séjourné au Mountain Lodge et les points n'apparaissent pas.")
    assert not is_english("Hallo, die Punkte für meinen Aufenthalt sind nicht gutgeschrieben.")


def test_the_simulated_supervisor_only_approves_a_fully_passed_adjust_checklist() -> None:
    passed = {"outcome": "adjust", "lines": [{"passed": True}, {"passed": True}]}
    assert simulated_review(passed) == (True, "")
    assert simulated_review({**passed, "lines": [{"passed": True}, {"passed": False}]})[0] is False
    assert simulated_review({**passed, "outcome": "wait_until"})[0] is False
