"""Model lifecycle and the release gate (ENT-15, BENCH-13, ENT-22; ADR-0082). Offline: no model is called."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.ai.config import AiConfig, Limits, ModelPrice, ai_config
from app.ai.lifecycle import review
from scripts import release_gate

TODAY = date(2026, 11, 14)


def _config(**models: ModelPrice) -> AiConfig:
    return AiConfig(Limits(), dict(models))


def test_a_model_retiring_soon_or_retired_or_deprecated_blocks() -> None:
    config = _config(
        soon=ModelPrice(1, 1, "2026-11-01", retires_on="2026-12-20"),
        gone=ModelPrice(1, 1, "2026-11-01", retires_on="2026-11-01"),
        old=ModelPrice(1, 1, "2026-11-01", deprecated=True),
        later=ModelPrice(1, 1, "2026-11-01", retires_on="2027-06-30"),
    )
    findings = review(config, TODAY)
    blocks = {f.model: f.message for f in findings if f.severity == "block"}  # a model can have several findings
    assert "in 36 days" in blocks["soon"] and "retired" in blocks["gone"] and "deprecated" in blocks["old"]
    assert "later" not in blocks
    assert ("later", "info", "retires on 2027-06-30") in {(f.model, f.severity, f.message) for f in findings}


def test_no_date_is_never_guessed_and_a_stale_check_is_flagged() -> None:
    findings = review(_config(m=ModelPrice(1, 1, "2026-06-01")), TODAY)
    assert {(f.severity, f.message) for f in findings} == {
        ("info", "no retirement date published as of 2026-06-01"),
        ("warn", "price and status last checked 2026-06-01: re-read the provider's pages"),
    }


def test_an_unlisted_model_blocks() -> None:
    (finding,) = review(_config(), TODAY, model="claude-unknown")
    assert finding.severity == "block"


def test_the_committed_configuration_passes_the_review_today() -> None:
    config = ai_config("hg-demo")
    assert not [f for f in review(config, TODAY) if f.severity == "block"]
    assert all(price.retires_on is None for price in config.models.values())  # none published: nothing invented


def test_the_harness_refuses_a_model_past_its_retirement_date() -> None:
    from app.ai.harness import _price

    class Provider:
        model_id = "retired"

    retired = _config(retired=ModelPrice(1, 1, "2026-01-01", retires_on="2026-02-01"))
    assert _price(retired, Provider()) is None  # type: ignore[arg-type]


def test_a_shadow_run_uses_the_prompt_ai_prompt_names_and_the_default_otherwise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.ai import harness
    from app.services.assisted import mock_runtime

    asked: list[str] = []

    class Stop(Exception):
        pass

    def recorder(name: str = "arm_c_v1") -> Any:
        asked.append(name)
        raise Stop

    monkeypatch.setattr(harness, "load_prompt", recorder)
    case = SimpleNamespace(customer_id="hg-demo")
    for value in ("arm_c_v2_candidate", ""):
        monkeypatch.setenv("AI_PROMPT", value)
        with pytest.raises(Stop):
            harness.run_loop(None, None, case, mock_runtime(), None, None, [])  # type: ignore[arg-type]
    assert asked == ["arm_c_v2_candidate", harness.DEFAULT_PROMPT]


# ---------- the release gate ----------


def _write(folder: Path, records: list[dict[str, object]]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return folder


def test_the_gate_finds_a_changed_decision_and_a_missing_case(tmp_path: Path) -> None:
    base = release_gate.load(
        _write(
            tmp_path / "base",
            [
                {"case_id": "DV-001", "run": 1, "outcome": "adjust", "final_points": 100},
                {"case_id": "DV-002", "run": 1, "outcome": "deny", "final_points": 0},
            ],
        )
    )
    same = release_gate.load(
        _write(
            tmp_path / "same",
            [
                {"case_id": "DV-001", "run": 1, "outcome": "adjust", "final_points": 100, "latency_s": 9.9},
                {"case_id": "DV-002", "run": 1, "outcome": "deny", "final_points": 0},
            ],
        )
    )
    changed = release_gate.load(
        _write(
            tmp_path / "changed",
            [
                {"case_id": "DV-001", "run": 1, "outcome": "adjust", "final_points": 90},
            ],
        )
    )
    assert release_gate.compare(base, same) == []  # latency isn't a decision
    diff = release_gate.compare(base, changed)
    assert "DV-001 run 1: final_points 100 -> 90" in diff
    assert "DV-002 run 1: missing from the candidate" in diff


def test_only_changes_that_can_alter_arm_c_trigger_the_gate() -> None:
    assert release_gate.ai_changes(["docs/decisions.md", "app/web/console.py"]) == []
    assert release_gate.ai_changes(["config/prompts/arm_c_v1.md", "README.md"]) == ["config/prompts/arm_c_v1.md"]
    assert release_gate.ai_changes(["app/ai/loop.py", "policies/hg-demo/earning.md"]) == [
        "app/ai/loop.py",
        "policies/hg-demo/earning.md",
    ]


def test_feedback_becomes_candidates_with_codes_only(mock_template: dict[str, Any], tmp_path: Path) -> None:
    from app.persistence.models import Feedback, QaSample
    from app.services import cases as svc
    from evaluations import feedback_candidates as fc
    from tests.arm_a import make_arm_a

    arm = make_arm_a(mock_template, tmp_path)
    with arm.sessions() as s:
        request = svc.IntakeRequest("2026-07-01T10:00:00Z", "email", "I am Zebedee Quillfeather, z.q@mail.test")
        one = svc.create_case(s, arm.who("agent.ana"), request, arm="C")
        two = svc.create_case(s, arm.who("agent.ana"), request, arm="C")
        answers = {
            "outcome": "wrong",
            "evidence": "complete",
            "policy_cited": "right",
            "explanation": "clear",
            "member_message": "ready",
        }
        s.add(
            QaSample(
                case_id=one.id,
                arm="C",
                rate_percent=10,
                status="reviewed",
                closed_by="agent.ana",
                sampled_at_utc="2026-07-02T00:00:00Z",
                reviewer="supervisor.sam",
                answers=answers,
            )
        )
        s.add(
            Feedback(
                case_id=two.id,
                kind="recommendation",
                rating="not_helpful",
                reason_code="wrong_stay",
                comment="Called Zebedee on 312-555-0142",
                author="agent.ana",
                created_at_utc="2026-07-02T00:00:00Z",
            )
        )
        s.add(
            Feedback(
                case_id=one.id,
                kind="recommendation",
                rating="helpful",
                author="agent.ben",
                created_at_utc="2026-07-02T00:00:00Z",
            )
        )
        s.commit()
        found = fc.collect(s)
        first, second = one.reference, two.reference
    assert {(c.case_reference, c.source, c.codes) for c in found} == {
        (first, "qa", "outcome=wrong"),
        (second, "feedback", "not_helpful=wrong_stay"),
    }  # the helpful feedback isn't a candidate
    text = fc.sheet(found)
    for planted in ("Zebedee", "Quillfeather", "z.q@mail.test", "312-555-0142", "agent.ana"):
        assert planted not in text, planted
    assert text.splitlines()[0] == ",".join(fc.COLUMNS)


def test_only_reviewed_rows_can_be_promoted() -> None:
    from evaluations import feedback_candidates as fc

    header = ",".join(fc.COLUMNS)
    with pytest.raises(fc.NotReviewed, match="no reviewer"):
        fc.promotable(f"{header}\nLSM-1,C,qa,outcome=wrong,deny,,add\n")
    with pytest.raises(fc.NotReviewed, match="label must be"):
        fc.promotable(f"{header}\nLSM-1,C,qa,outcome=wrong,maybe,sam,add\n")
    rows = fc.promotable(f"{header}\nLSM-1,C,qa,outcome=wrong,deny,sam,add\nLSM-2,C,qa,outcome=unsure,,,\n")
    assert [r["case_reference"] for r in rows] == ["LSM-1"]  # undecided rows are left for later, not promoted


def test_the_known_good_baseline_is_committed_and_names_its_commit() -> None:
    manifest = json.loads((release_gate.BASELINE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["kind"] == "mock" and manifest["config"]["arm"] == "C" and len(manifest["app_commit"]) == 40
    assert len(release_gate.load(release_gate.BASELINE)) >= 100
