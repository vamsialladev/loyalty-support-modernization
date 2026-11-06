"""Operational metrics and the day-one page (UI-01, ADR-0062): observed counts, aggregates only, behind sign-in."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.roles import NotPermitted
from app.main import create_app
from app.services import cases as svc
from app.services import metrics
from app.settings import AppSettings
from benchmarks.agents.conventional_scripted import ScriptedConventionalAgent
from benchmarks.intake import load_case, read_split
from evaluations.discovery_analysis import analyse, console_summary, load
from tests.arm_a import ArmA, Browser, make_arm_a
from tests.conftest import ROOT

DAY_ONE = ROOT / "app/web/day_one"


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def browser(arm: ArmA, user: str, landing: str = "Points queue") -> Browser:
    b = Browser(TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory())))
    b.login(user, arm.password, landing)
    return b


def test_scripted_cases_are_counted_apart_from_peoples(arm: ArmA) -> None:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-001")
    other = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-002")
    with arm.sessions() as s:
        (scripted,) = load_case(s, item, arm="B")
        ScriptedConventionalAgent(s, arm.factory()).run(scripted)
        request = svc.IntakeRequest(received_at_utc="2026-07-01T10:00:00Z", contact_channel="email", text="Points.")
        svc.create_case(s, arm.who("agent.ana"), request, arm="B")
        load_case(s, other)
        found = metrics.collect(s, arm.who("supervisor.sam"))
    # The intake actor is a person in the log only until a scripted actor touches the case; a loaded case nobody worked
    # counts with the people, on its own arm.
    rows = {(r.arm, r.kind): r for r in found.rows}
    assert set(rows) == {("A", "human"), ("B", "human"), ("B", "scripted")}
    worked = rows[("B", "scripted")]
    assert worked.cases == 1 and worked.adjustments_executed == 1 and worked.points_executed == 14840
    assert worked.investigations == 1 and worked.engine_results == {"adjust": 1} and worked.by_status == {"Resolved": 1}
    assert worked.median_steps is not None and worked.median_steps > 1
    assert rows[("B", "human")].cases == 1 and rows[("B", "human")].adjustments_executed == 0
    assert rows[("A", "human")].cases == 1


def test_metrics_say_they_are_counts_not_scores(arm: ArmA) -> None:
    with arm.sessions() as s:
        found = metrics.collect(s, arm.who("auditor.abe"))
    assert "not whether it was right" in found.note and found.rows == []
    source = (ROOT / "app/services/metrics.py").read_text(encoding="utf-8")
    assert "expected_outcome" not in source and "accuracy" not in source


@pytest.mark.parametrize("user", ["agent.ana", "agent.ben"])
def test_agents_dont_read_the_metrics(arm: ArmA, user: str) -> None:
    with arm.sessions() as s, pytest.raises(NotPermitted):
        metrics.collect(s, arm.who(user))
    b = browser(arm, user)
    assert b.get("/metrics").status_code == 403
    assert b.get("/day-one").status_code == 403
    assert b.get("/day-one/charts/pareto.png").status_code == 403
    assert '<a href="/metrics">' not in b.get("/queue").text


@pytest.mark.parametrize(
    ("user", "landing"),
    [("supervisor.sam", "Points queue"), ("auditor.abe", "Points queue"), ("admin.ada", "Configuration")],
)
def test_who_can_read_them_and_the_pages_render_empty(arm: ArmA, user: str, landing: str) -> None:
    b = browser(arm, user, landing)
    page = b.get("/metrics")
    assert page.status_code == 200 and "No cases yet." in page.text
    assert '<a href="/metrics">' in page.text
    day_one = b.get("/day-one")
    assert day_one.status_code == 200 and "SYNTHETIC history" in day_one.text
    assert "Over-credited" in day_one.text and 'alt="Bar chart of failed cases' in day_one.text
    chart = b.get("/day-one/charts/pareto.png")
    assert chart.status_code == 200 and chart.headers["content-type"] == "image/png"


def test_the_day_one_charts_need_a_session_and_a_listed_name(arm: ArmA) -> None:
    anonymous = TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory()))
    assert anonymous.get("/day-one/charts/pareto.png", follow_redirects=False).status_code == 303
    assert anonymous.get("/static/day-one/pareto.png").status_code == 404  # not under /static, which needs no sign-in
    b = browser(arm, "supervisor.sam")
    for name in ("summary.json", "..%2F..%2Fconsole.py", "nope.png"):
        assert b.get(f"/day-one/charts/{name}").status_code in (404,), name


def test_the_export_traces_to_the_analysis_and_the_report(generated: Path) -> None:
    cases, events = load(generated)
    expected = console_summary(analyse(cases, events, generated))
    stored = json.loads((DAY_ONE / "summary.json").read_text(encoding="utf-8"))
    for key, value in expected.items():
        assert stored[key] == value, key
    report = (ROOT / "docs/day-one-discovery.md").read_text(encoding="utf-8")
    assert f"**{stored['cases']:,} missing-points" in report
    assert f"**{stored['failed']:,} ({stored['failed_percent']}%)**" in report
    assert f"about {stored['predicted_share_b']}% of these failures" in report
    for chart in stored["charts"]:
        assert (DAY_ONE / chart["file"]).read_bytes() == (ROOT / "docs/images/day-one" / chart["file"]).read_bytes(), (
            chart["file"]
        )


def test_the_export_holds_no_case_and_no_person() -> None:
    text = (DAY_ONE / "summary.json").read_text(encoding="utf-8")
    assert not re.search(r"GR-\d{5}|BR-\d{4}|ML-\d{4}|TRV-\d|DV-\d|@", text)
    for word in ("case_id", "member_number", "claimant", "guest_name", "ground_truth"):
        assert word not in text
    allowed = {"driver", "name", "cases", "failed", "predicted"}
    assert all(set(row) == allowed for row in json.loads(text)["drivers"])
