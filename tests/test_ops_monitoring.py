"""Operations monitoring (OPS-03, ENT-18, ENT-19, ENT-32): queue and cost metrics, drift signals, online QA
sampling and the privacy-filtered analytics export. Synthetic cases only; nothing here scores correctness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.domain.roles import NotPermitted
from app.persistence.models import AiRun, AiStep, Case, CaseNote, QaSample
from app.services import analytics_export, drift, jobs, metrics, qa_sampling
from app.services import cases as svc
from app.services.drift import Signals, Window
from app.services.instrumentation import record
from benchmarks.agents.conventional_scripted import ScriptedConventionalAgent
from benchmarks.intake import load_case, read_split
from tests.arm_a import ArmA, make_arm_a
from tests.test_api import Api


class _AnyTime(str):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, str) and len(other) == 20 and other.endswith("Z")

    __hash__ = str.__hash__


ANY_TIME = _AnyTime("<a UTC time>")

PLANTED_EMAIL = "planted.member@mail.test"
PLANTED_NAME = "Zebedee Quillfeather"


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def _person_case(arm: ArmA, s: Any, text: str = "My points are missing.", arm_code: str = "B") -> Case:
    request = svc.IntakeRequest(received_at_utc="2026-07-01T10:00:00Z", contact_channel="email", text=text)
    return svc.create_case(s, arm.who("agent.ana"), request, arm=arm_code)


# ---------- metrics (OPS-03) ----------


def test_metrics_report_queue_age_cost_per_case_tool_use_and_spend(arm: ArmA) -> None:
    with arm.sessions() as s:
        case = _person_case(arm, s, arm_code="C")
        jobs.enqueue(s, "probe", {}, case_id=case.id)
        run = AiRun(
            case_id=case.id,
            caller="agent.ana",
            provider="mock",
            model_id="mock-1",
            is_mock=True,
            prompt_version="v1",
            policy_versions=[],
            status="finished",
            input_tokens=900,
            output_tokens=100,
            cost_microusd=2500,
            started_at_utc="2026-07-01T10:00:00Z",
        )
        s.add(run)
        s.flush()
        s.add_all(
            [
                AiStep(run_id=run.id, step=1, kind="tool", name="get_stay", status="ok"),
                AiStep(run_id=run.id, step=2, kind="tool", name="get_stay", status="not_found"),
                AiStep(run_id=run.id, step=3, kind="model", name="turn", status="ok"),
            ]
        )
        s.commit()
        found = metrics.collect(s, arm.who("supervisor.sam"))
    assert found.jobs_queued == 1 and found.oldest_queued_seconds is not None and found.oldest_queued_seconds >= 0
    (row,) = [r for r in found.rows if r.arm == "C"]
    assert row.ai_runs == 1 and row.ai_cost_microusd == 2500 and row.ai_cost_per_case_microusd == 2500
    assert found.tool_calls == {"get_stay": {"ok": 1, "not_found": 1}}
    assert set(found.spend_microusd) == {"day", "month"}


# ---------- drift (ENT-19) ----------


def _signals(cases: int, **values: float | None) -> Signals:
    return Signals(Window("2026-07-01", "2026-07-31"), cases, dict(values), {"points": 0.8, "other": 0.2})


def test_a_signal_drifts_only_past_its_threshold_and_with_enough_cases() -> None:
    before = _signals(100, escalation_rate=0.10, tokens_per_case=1000.0)
    after = _signals(100, escalation_rate=0.16, tokens_per_case=1300.0)
    thresholds = {drift.ESCALATION: 0.05, drift.TOKENS: 0.25, drift.OVERRIDE: 0.05}
    alerts = {a.signal: a for a in drift.compare(before, after, thresholds)}
    assert set(alerts) == {drift.ESCALATION, drift.TOKENS}  # override has no value in either window: no alert
    assert alerts[drift.ESCALATION].change == pytest.approx(0.06)
    assert alerts[drift.TOKENS].change == pytest.approx(0.30)
    assert alerts[drift.ESCALATION].runbook.startswith("docs/runbooks/")
    assert drift.compare(before, _signals(100, escalation_rate=0.14), thresholds) == []
    assert drift.compare(_signals(10, escalation_rate=0.1), _signals(10, escalation_rate=0.9), thresholds) == []


def test_a_change_in_the_category_mix_is_measured_as_a_distance() -> None:
    a, b = {"points": 0.8, "other": 0.2}, {"points": 0.4, "other": 0.2, "status": 0.4}
    assert drift.mix_distance(a, a) == 0.0
    assert drift.mix_distance(a, b) == pytest.approx(0.4)
    before, after = _signals(50), Signals(Window("2026-08-01", "2026-08-31"), 50, {}, b)
    (alert,) = drift.compare(before, after, {drift.MIX: 0.2})
    assert alert.signal == drift.MIX and alert.current == pytest.approx(0.4)


def test_drift_signals_come_from_stored_cases_and_leave_out_scripted_runs(arm: ArmA) -> None:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-001")
    with arm.sessions() as s:
        (scripted,) = load_case(s, item, arm="B")
        ScriptedConventionalAgent(s, arm.factory()).run(scripted)
        person = _person_case(arm, s)
        record(s, person, arm.who("agent.ana"), "case_escalated", reason="disputed stay")
        found = drift.compute(s, "hg-demo", Window("2026-01-01", "2026-12-31"))
    assert found.cases == 1  # the scripted case is left out
    assert found.values[drift.ESCALATION] == 1.0


def test_the_customer_configuration_carries_the_thresholds() -> None:
    from app.services.customer_config import CustomerConfig

    config = CustomerConfig.load("hg-demo")
    assert set(config.drift_thresholds) <= {
        drift.ESCALATION,
        drift.OVERRIDE,
        drift.VALIDATION,
        drift.CITATION,
        drift.TOOL_ERROR,
        drift.TOKENS,
        drift.MIX,
    }
    assert config.drift_thresholds and all(v > 0 for v in config.drift_thresholds.values())
    assert config.qa_sample_percent > 0 and config.qa_sample_arms


# ---------- QA sampling (ENT-18) ----------


def test_sampling_is_repeatable_keyed_and_close_to_its_rate() -> None:
    config = qa_sampling.SamplingConfig(rate_percent=10.0, key=b"k1")
    picks = [qa_sampling.chosen(f"LSM-{i:05d}", config) for i in range(5000)]
    assert picks == [qa_sampling.chosen(f"LSM-{i:05d}", config) for i in range(5000)]
    assert 0.08 < sum(picks) / len(picks) < 0.12
    other = [qa_sampling.chosen(f"LSM-{i:05d}", qa_sampling.SamplingConfig(10.0, key=b"k2")) for i in range(5000)]
    assert picks != other  # a different key picks different cases, so the choice can't be predicted
    assert not any(qa_sampling.chosen(f"LSM-{i}", qa_sampling.SamplingConfig(0.0)) for i in range(500))
    assert all(qa_sampling.chosen(f"LSM-{i}", qa_sampling.SamplingConfig(100.0)) for i in range(500))


def test_a_chosen_case_is_queued_once_and_reviewed_by_someone_else(arm: ArmA) -> None:
    every = qa_sampling.SamplingConfig(rate_percent=100.0, arms=("B",))
    with arm.sessions() as s:
        case = _person_case(arm, s)
        sample = qa_sampling.consider(s, case, "agent.ana", every)
        assert sample is not None and qa_sampling.consider(s, case, "agent.ana", every) is None
        s.commit()
        assert [p.case_id for p in qa_sampling.pending(s, arm.who("supervisor.sam"))] == [case.id]
        answers = {item: options[0] for item, options in qa_sampling.RUBRIC.items()}
        with pytest.raises(NotPermitted):
            qa_sampling.pending(s, arm.who("agent.ben"))
        with pytest.raises(qa_sampling.InvalidReview):
            qa_sampling.review(s, arm.who("supervisor.sam"), sample.id, {**answers, "outcome": "probably"})
        with pytest.raises(qa_sampling.InvalidReview):
            qa_sampling.review(s, arm.who("supervisor.sam"), sample.id, {"outcome": "right"})
        done = qa_sampling.review(s, arm.who("supervisor.sam"), sample.id, answers)
        assert done.status == qa_sampling.REVIEWED and done.reviewer == "supervisor.sam"
        with pytest.raises(qa_sampling.InvalidReview):
            qa_sampling.review(s, arm.who("auditor.abe"), sample.id, answers)
        summary = qa_sampling.summary(s, arm.who("auditor.abe"))
    assert summary["reviewed"] == 1 and "not the offline benchmark" in str(summary["source"])


def test_the_closer_cant_review_and_scripted_or_other_arm_cases_arent_sampled(arm: ArmA) -> None:
    every = qa_sampling.SamplingConfig(rate_percent=100.0, arms=("B",))
    with arm.sessions() as s:
        case = _person_case(arm, s)
        sample = qa_sampling.consider(s, case, "supervisor.sam", every)
        assert sample is not None
        s.commit()
        answers = {item: options[0] for item, options in qa_sampling.RUBRIC.items()}
        with pytest.raises(NotPermitted):
            qa_sampling.review(s, arm.who("supervisor.sam"), sample.id, answers)
        a_case = _person_case(arm, s, arm_code="A")
        assert qa_sampling.consider(s, a_case, "agent.ana", every) is None
        assert s.query(QaSample).count() == 1


def test_closing_a_case_considers_it_for_sampling_and_scripted_closers_are_never_sampled(
    arm: ArmA, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-001")
    monkeypatch.setattr(qa_sampling, "config_for", lambda _customer: qa_sampling.SamplingConfig(100.0, ("B",)))
    seen: list[tuple[str, str]] = []
    real = qa_sampling.consider

    def watching(s: Any, case: Case, closed_by: str, config: Any = None) -> Any:
        seen.append((case.status, closed_by))
        return real(s, case, closed_by, config)

    monkeypatch.setattr(qa_sampling, "consider", watching)
    with arm.sessions() as s:
        (case,) = load_case(s, item, arm="B")
        ScriptedConventionalAgent(s, arm.factory()).run(case)
        assert s.query(QaSample).count() == 0  # 100% rate, but the closer is a scripted actor
    assert seen and seen[-1][0] == "Resolved" and seen[-1][1].startswith("scripted-")


def test_an_adjustment_a_person_requested_is_sampled_when_it_executes(
    arm: ArmA, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The executed path resolves most adjusted cases (`write_path._applied`), so it must sample too (found while
    building: only the two close paths did at first)."""
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-001")
    monkeypatch.setattr(qa_sampling, "config_for", lambda _customer: qa_sampling.SamplingConfig(100.0, ("B",)))
    with arm.sessions() as s:
        (case,) = load_case(s, item, arm="B")
        agent = ScriptedConventionalAgent(s, arm.factory())
        agent.agent, agent.supervisor = arm.who("agent.ana"), arm.who("supervisor.sam")  # people, not scripted actors
        agent.run(case)
        s.refresh(case)
        samples = s.query(QaSample).all()
    assert case.status == "Resolved" and case.resolution_code == "adjusted"
    assert [(q.case_id, q.closed_by, q.status) for q in samples] == [(case.id, "agent.ana", qa_sampling.PENDING)]


def test_qa_review_over_the_api_with_roles_csrf_and_rubric_checks(arm: ArmA) -> None:
    every = qa_sampling.SamplingConfig(rate_percent=100.0, arms=("B",))
    with arm.sessions() as s:
        case = _person_case(arm, s)
        sample = qa_sampling.consider(s, case, "agent.ana", every)
        assert sample is not None
        s.commit()
        sample_id, reference = sample.id, case.reference
    supervisor, agent = Api(arm, "supervisor.sam"), Api(arm, "agent.ben")
    listed = supervisor.get("/qa/samples")
    assert listed.status_code == 200 and listed.json() == [
        {"id": sample_id, "case_reference": reference, "arm": "B", "status": "pending", "sampled_at_utc": ANY_TIME}
    ]
    assert agent.get("/qa/samples").status_code == 403
    answers = {item: options[0] for item, options in qa_sampling.RUBRIC.items()}
    assert supervisor.post(f"/qa/samples/{sample_id}/review", answers, csrf="wrong").status_code == 403
    bad = supervisor.post(f"/qa/samples/{sample_id}/review", {**answers, "outcome": "probably"})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_review"
    extra = supervisor.post(f"/qa/samples/{sample_id}/review", {**answers, "note": f"called {PLANTED_EMAIL}"})
    assert extra.status_code == 422  # no free text: unknown fields are refused, so a review can't hold personal data
    done = supervisor.post(f"/qa/samples/{sample_id}/review", answers)
    assert done.status_code == 200 and done.json()["status"] == "reviewed"
    summary = supervisor.get("/qa/summary").json()
    assert summary["reviewed"] == 1 and summary["answers"]["outcome"]["right"] == 1


def test_the_metrics_page_shows_queue_age_spend_and_tool_use(arm: ArmA) -> None:
    with arm.sessions() as s:
        case = _person_case(arm, s, arm_code="C")
        jobs.enqueue(s, "probe", {}, case_id=case.id)
        s.commit()
    page = Api(arm, "supervisor.sam").client.get("/metrics")
    assert page.status_code == 200
    for testid in ("jobs-oldest", "spend-day", "spend-month"):
        assert f'data-testid="{testid}"' in page.text


# ---------- analytics export (ENT-32) ----------


def test_the_daily_export_holds_counts_only_from_an_allow_list(arm: ArmA) -> None:
    with arm.sessions() as s:
        case = _person_case(arm, s, text=f"I am {PLANTED_NAME}, {PLANTED_EMAIL}, member GR-12345, stay BR-998877.")
        s.add(
            CaseNote(
                case_id=case.id,
                author="agent.ana",
                body=f"Called {PLANTED_NAME}",
                created_at_utc="2026-07-01T10:05:00Z",
            )
        )
        s.commit()
        rows = analytics_export.rows_for_day(s, "hg-demo", "2026-07-01")
        text = analytics_export.to_csv(rows)
        reference = case.reference
    assert rows and set(rows[0]) == set(analytics_export.COLUMNS)
    header = text.splitlines()[1].split(",")
    assert tuple(header) == analytics_export.COLUMNS
    for planted in (PLANTED_NAME, "Zebedee", PLANTED_EMAIL, "GR-12345", "BR-998877", reference, "agent.ana"):
        assert planted not in text, planted
    assert all(isinstance(v, int | float | str) or v is None for row in rows for v in row.values())
    assert {type(row["cases_received"]) for row in rows} == {int}


def test_a_day_with_no_cases_exports_only_the_header() -> None:
    assert analytics_export.to_csv([]).splitlines()[1].startswith("day,arm,worked_by")
