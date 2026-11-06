"""Each pre-registered defect arm B must fix, on the dev split, one defect at a time (spec F9; catalog section 2a).

Test code may read labels; arm B and its scripted agent never do. These tests check a defect's mechanics on named cases
and store nothing. No aggregate score is computed: thresholds aren't set yet (ADR-0048).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.persistence.models import AdjustmentRequestRow, Case, CaseEvent
from app.services import conventional
from benchmarks.agents.conventional_scripted import LABEL, ConventionalRun, ScriptedConventionalAgent
from benchmarks.intake import load_case, read_split
from tests.arm_a import ArmA, make_arm_a


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def run_scenario(arm: ArmA, s: Any, code: str, nth: int = 0) -> tuple[ConventionalRun, Case, dict[str, Any]]:
    cid = arm.scenario(code, nth=nth)
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == cid)
    (case, *_rest) = load_case(s, item, arm="B")
    return ScriptedConventionalAgent(s, arm.factory()).run(case), case, arm.labels[cid]


def scenario_ids(arm: ArmA, code: str) -> int:
    return sum(1 for lab in arm.labels.values() if lab["split"] == "dev" and lab["scenarios"] == [code])


def credited_points(s: Any, case: Case) -> list[int]:
    query = select(AdjustmentRequestRow.points).where(
        AdjustmentRequestRow.case_id == case.id, AdjustmentRequestRow.status == "executed"
    )
    return list(s.scalars(query))


def assert_engine_action(run: ConventionalRun, action: str) -> None:
    assert any(step.startswith(f"engine:{action}") for step in run.path), run.path


FIRST_CONTACT = ("K01", "K02", "K03", "K04", "K05", "K06", "D01", "D02", "D04", "D05", "D06", "D07", "D08", "D09")


@pytest.mark.parametrize("code", [*FIRST_CONTACT, "D12", "D13", "D15", "D17", "D21"])
def test_the_first_contact_takes_the_labelled_action_and_credits_only_what_is_owed(arm: ArmA, code: str) -> None:
    """`next_action` is what's right at this contact. `expected_outcome` can differ: a member told to wait who writes
    again later ends up credited, which the benchmark runner plays out (spec F7)."""
    with arm.sessions() as s:
        for nth in range(scenario_ids(arm, code)):
            run, case, label = run_scenario(arm, s, code, nth)
            assert_engine_action(run, label["next_action"])
            rec = conventional.latest_recommendation(s, case)
            assert rec is not None and rec.detail == label["next_action_detail"], (code, nth, run.path)
            assert rec.citations, (code, nth, "a decided case cites the policy")
            if label["next_action"] == "adjust":
                assert run.final_status == "Resolved", (code, nth, run.path)
                assert credited_points(s, case) == [label["owed_total"]], (code, nth, run.path)
            else:
                assert credited_points(s, case) == [], (code, nth, run.path)
                assert run.final_status == "Resolved", (code, nth, run.path)


def test_d03_derives_the_channel_or_asks(arm: ArmA) -> None:
    with arm.sessions() as s:
        for nth in range(scenario_ids(arm, "D03")):
            run, case, label = run_scenario(arm, s, "D03", nth)
            if label["clarification_needed"]:
                assert run.final_status == "Awaiting information"
                assert_engine_action(run, "request_info:booking_channel")
            else:
                assert credited_points(s, case) == [label["owed_total"]], run.path


def test_d03_the_members_answer_settles_it(arm: ArmA) -> None:
    with arm.sessions() as s:
        for nth in range(scenario_ids(arm, "D03")):
            _run, case, label = run_scenario(arm, s, "D03", nth)
            if not label["clarification_needed"]:
                continue
            agent = ScriptedConventionalAgent(s, arm.factory())
            conventional.supply_information(s, agent.agent, case, booking_channel=label["facts"]["reply_channel"])
            agent.worker.drain()
            s.expire_all()
            rec = conventional.latest_recommendation(s, case)
            assert rec is not None and rec.detail != "booking_channel"
            return
    pytest.skip("no D03 case in dev needs the member's answer")


def test_d10_two_contacts_for_one_stay_credit_once(arm: ArmA) -> None:
    with arm.sessions() as s:
        cid = arm.scenario("D10")
        item = next(c for c in read_split("dev", arm.datasets) if c.case_id == cid)
        first, second = load_case(s, item, arm="B")
        agent = ScriptedConventionalAgent(s, arm.factory())
        agent.run(first)
        agent.run(second)
        label = arm.labels[cid]
    member, stay = label["facts"]["claimant"], label["facts"]["claimed_stay_ids"][0]
    credits = [e for e in arm.systems().get_ledger(member) if e.kind == "adjustment" and e.stay_id == stay]
    assert len(credits) == 1


def test_d16_works_the_named_stay_and_asks_about_the_rest(arm: ArmA) -> None:
    with arm.sessions() as s:
        run, _case, _label = run_scenario(arm, s, "D16")
        assert "asked_about_more_stays" in run.path, run.path


def test_d16_several_explicit_numbers_become_linked_cases(arm: ArmA) -> None:
    label = next(lab for lab in arm.labels.values() if lab["split"] == "dev" and lab["scenarios"] == ["K01"])
    systems = arm.systems()
    member = systems.get_member(label["facts"]["claimant"])
    stays = sorted({r.stay_id for r in systems.find_stays(member_number=member.member_number)})
    if len(stays) < 2:
        pytest.skip("this member has one stay")
    text = f"Points missing for {stays[0]} and {stays[1]}.\nThanks, {member.first_name} {member.last_name}"
    from app.services.cases import IntakeRequest, create_case

    with arm.sessions() as s:
        agent = ScriptedConventionalAgent(s, arm.factory())
        request = IntakeRequest(
            received_at_utc="2026-10-01T12:00:00Z", contact_channel="email", text=text, sender_email=member.email
        )
        case = create_case(s, agent.agent, request, arm="B")
        run = agent.run(case)
        assert len(run.linked) == 1, run.path
        linked = conventional.group_cases(s, case)
        assert {c.group_ref for c in linked} == {case.reference} and len(linked) == 2
        assert {conventional.claimed_stay(s, c) for c in linked} == set(stays[:2])


def test_d18_a_different_surname_passes_only_on_two_other_identifiers(arm: ArmA) -> None:
    """Exact email plus an exact confirmation on that profile. No model needed, so it belongs to arm B (RFC-0002,
    F9)."""
    with arm.sessions() as s:
        for nth in range(scenario_ids(arm, "D18")):
            run, case, label = run_scenario(arm, s, "D18", nth)
            rec = conventional.latest_recommendation(s, case)
            assert rec is not None
            assert rec.member_number == label["claimant_member_number"], (nth, run.path, rec.detail)


def test_d19_vague_dates_are_asked_about_never_guessed(arm: ArmA) -> None:
    with arm.sessions() as s:
        for nth in range(scenario_ids(arm, "D19")):
            run, case, _label = run_scenario(arm, s, "D19", nth)
            assert run.final_status == "Awaiting information", run.path
            assert credited_points(s, case) == []


def test_d20_a_points_claim_with_a_complaint_goes_to_a_person_not_billing(arm: ArmA) -> None:
    with arm.sessions() as s:
        for nth in range(scenario_ids(arm, "D20")):
            run, case, label = run_scenario(arm, s, "D20", nth)
            if "refund_request" in label["out_of_scope_items"] and case.queue == "billing":
                continue  # nothing about points in the message
            assert run.final_status == "Escalated", run.path
            assert_engine_action(run, "escalate:multi_issue")


def test_d22_clean_documents_are_read_and_photos_are_flagged(arm: ArmA) -> None:
    """Arm B's baseline: a PDF's text layer and a plain email. A photo needs vision, which is arm C's (catalog, D22)."""
    with arm.sessions() as s:
        seen_read, seen_unread = False, False
        for nth in range(scenario_ids(arm, "D22")):
            run, case, label = run_scenario(arm, s, "D22", nth)
            rec = conventional.latest_recommendation(s, case)
            assert rec is not None
            assert run.final_status in {"Resolved", "Awaiting information", "Escalated"}, run.path
            if "attachment_not_read" in rec.flags:
                seen_unread = True
            else:
                seen_read = True
                assert rec.stay_id == label["facts"]["claimed_stay_ids"][0], run.path
        assert seen_read and seen_unread


def test_a_stay_found_by_its_date_passes_the_recheck_and_reads_every_record(arm: ArmA) -> None:
    """The re-check reads the stay by number. If the first read saw fewer records, the evidence hash would differ and
    every approval of a stay found by date would be invalidated, or a conflicting record would stay hidden."""
    from app.services.cases import IntakeRequest, create_case

    label = arm.labels["DV-001"]  # K01: stated with its dates, and no confirmation number in this message
    text = "I stayed at Beach Resort from November 25-29, 2025 but the points are missing.\nThanks, Clara Kowalski"
    request = IntakeRequest(
        received_at_utc=label["facts"]["received_at_utc"],
        contact_channel="email",
        text=text,
        sender_email="clara.kowalski4@example.com",
    )
    with arm.sessions() as s:
        agent = ScriptedConventionalAgent(s, arm.factory())
        case = create_case(s, agent.agent, request, arm="B")
        run = agent.run(case)
        rec = conventional.latest_recommendation(s, case)
        evidence = conventional.latest_evidence(s, case)
        assert rec is not None and evidence is not None
        assert evidence["stay_found_by"] == "by_date" and evidence["stay_id"] == "BR-6638"
        assert run.final_status == "Resolved" and credited_points(s, case) == [label["owed_total"]], run.path


def test_d23_routes_other_languages_to_a_person(arm: ArmA) -> None:
    with arm.sessions() as s:
        for nth in range(scenario_ids(arm, "D23")):
            run, case, _label = run_scenario(arm, s, "D23", nth)
            assert run.final_status == "Escalated" and credited_points(s, case) == [], run.path
            assert_engine_action(run, "escalate:non_english")


@pytest.mark.parametrize("code", ["D24", "D25"])
def test_d24_d25_escalate_and_never_credit(arm: ArmA, code: str) -> None:
    with arm.sessions() as s:
        for nth in range(scenario_ids(arm, code)):
            run, case, _label = run_scenario(arm, s, code, nth)
            assert run.final_status == "Escalated", run.path
            assert credited_points(s, case) == []


def test_d14_one_view_takes_far_fewer_steps_than_four_screens(
    arm: ArmA, mock_template: dict[str, Any], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Scripted step counts only, never a claim about human time (catalog D14; spec E.7)."""
    from benchmarks.agents.legacy_scripted import ScriptedLegacyAgent

    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-001")
    with arm.sessions() as s:
        (b_case,) = load_case(s, item, arm="B")
        b_run = ScriptedConventionalAgent(s, arm.factory()).run(b_case)
    other = make_arm_a(mock_template, tmp_path_factory.mktemp("arm-a"))
    with other.sessions() as s:
        (a_case,) = load_case(s, item)
        a_run = ScriptedLegacyAgent(s, other.factory(), other.rules, other.index).run(a_case)
    assert b_run.label == LABEL
    assert b_run.steps < a_run.steps, (b_run.steps, a_run.steps)


def test_every_dev_case_reaches_a_resting_state_without_errors(arm: ArmA) -> None:
    with arm.sessions() as s:
        for item in read_split("dev", arm.datasets):
            load_case(s, item, arm="B")
        cases = list(s.scalars(select(Case).where(Case.arm == "B").order_by(Case.id)))
        agent = ScriptedConventionalAgent(s, arm.factory())
        runs = [agent.run(case) for case in cases]
        assert len(runs) == 102
        resting = {"Resolved", "Escalated", "Awaiting information", "New"}
        assert [r.case_reference for r in runs if r.final_status not in resting] == []
        assert list(s.scalars(select(CaseEvent).where(CaseEvent.action == "system_error"))) == []
