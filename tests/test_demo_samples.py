"""Sample cases in the public demo (owner, 2026-11-23; SEC-18, LIVE-02): after each daily reset the queue holds a few
synthetic cases across arms A, B and C, so a visitor never lands on an empty queue. One of them goes all the way to a
posting on the demo's live clock."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import demo_launch
from app.main import create_app
from app.persistence.models import AdjustmentRequestRow, Case, CaseEvent
from app.services import demo_samples
from app.services.job_handlers import build_handlers
from app.services.write_path import SharedWritePath
from app.settings import AppSettings
from app.worker import Worker
from tests.arm_a import ArmA, Browser, field, make_arm_a


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def live_clock(arm: ArmA, user: str) -> Browser:
    """The public demo runs with the simulated clock off (the mock API refuses it in demo mode)."""
    b = Browser(TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=False), arm.factory())))
    b.login(user, arm.password)
    return b


def drain(arm: ArmA) -> None:
    Worker(arm.sessions, build_handlers(SharedWritePath("hg-demo"), arm.factory())).drain()


def sample_case(arm: ArmA, key: str) -> Case:
    with arm.sessions() as s:
        case = s.scalars(select(Case).where(Case.source_ref == f"demo-sample:{key}")).one()
        s.expunge(case)
        return case


def test_the_samples_cover_arms_a_b_and_c_with_synthetic_contacts_only() -> None:
    samples = demo_samples.SAMPLES
    assert 3 <= len(samples) <= 5
    assert {sample.arm for sample in samples} == {"A", "B", "C"}
    assert len({sample.key for sample in samples}) == len(samples)
    for sample in samples:
        email = sample.request.sender_email
        assert email is None or email.endswith("@example.com"), sample.key  # reserved for examples (RFC 2606)
        assert sample.request.text.strip() and sample.what_to_try.strip(), sample.key


def test_an_empty_queue_gets_the_samples_once(arm: ArmA) -> None:
    with arm.sessions() as s:
        assert demo_samples.seed_samples(s) == len(demo_samples.SAMPLES)
    with arm.sessions() as s:
        cases = s.scalars(select(Case).order_by(Case.id)).all()
        assert [c.arm for c in cases] == [sample.arm for sample in demo_samples.SAMPLES]
        assert {c.status for c in cases} == {"New"} and {c.assigned_to for c in cases} == {None}
        assert {c.queue for c in cases} == {"points"}
        assert {c.created_by for c in cases} == {"system-demo-samples"}
        kinds = {e.actor_kind for e in s.scalars(select(CaseEvent).where(CaseEvent.action == "case_created"))}
        assert kinds == {"system"}  # the timeline shows the reset made them, not a visitor
    with arm.sessions() as s:
        assert demo_samples.seed_samples(s) == 0  # a queue with cases in it is left alone


def test_the_arm_b_sample_goes_all_the_way_to_a_posting_on_the_live_clock(arm: ArmA) -> None:
    with arm.sessions() as s:
        demo_samples.seed_samples(s)
    case = sample_case(arm, demo_samples.POSTING_SAMPLE)
    assert case.arm == "B"
    agent = live_clock(arm, "agent.ana")
    page = agent.get(f"/cases/{case.id}").text
    assert "Live demo sample" in page  # the sample says what to try
    agent.post(f"/cases/{case.id}/investigate")
    drain(arm)
    page = agent.get(f"/cases/{case.id}").text
    assert field(page, "engine-action") == "adjust"
    assert int(field(page, "points-owed")) == 14840
    assert field(agent.post(f"/cases/{case.id}/request-adjustment").text, "case-status") == "Pending approval"
    supervisor = live_clock(arm, "supervisor.sam")
    with arm.sessions() as s:
        rid = s.scalars(select(AdjustmentRequestRow.id).where(AdjustmentRequestRow.case_id == case.id)).one()
    supervisor.get(f"/cases/{case.id}")
    assert field(supervisor.post(f"/adjustments/{rid}/decide", decision="approve").text, "case-status") == "Approved"
    supervisor.post(f"/adjustments/{rid}/execute")
    drain(arm)
    done = supervisor.get(f"/cases/{case.id}").text
    assert field(done, "case-status") == "Resolved"
    assert field(done, "adjustment-status") == "executed"


def test_the_not_found_sample_asks_for_the_membership_number(arm: ArmA) -> None:
    with arm.sessions() as s:
        demo_samples.seed_samples(s)
    case = sample_case(arm, demo_samples.NOT_FOUND_SAMPLE)
    agent = live_clock(arm, "agent.ana")
    agent.get(f"/cases/{case.id}")
    agent.post(f"/cases/{case.id}/investigate")
    drain(arm)
    page = agent.get(f"/cases/{case.id}").text
    assert field(page, "engine-action") == "request_info"
    assert field(page, "engine-detail") == "member_not_found"


def test_the_arm_a_sample_can_be_started_by_hand(arm: ArmA) -> None:
    with arm.sessions() as s:
        demo_samples.seed_samples(s)
    case = sample_case(arm, demo_samples.LEGACY_SAMPLE)
    agent = live_clock(arm, "agent.ana")
    agent.get(f"/cases/{case.id}")
    started = agent.post(f"/cases/{case.id}/start").text
    assert field(started, "case-status") == "Investigating" and "assigned to agent.ana" in started


def test_the_seed_command_loads_the_samples_and_the_demo_reset_asks_for_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import seed
    from app.persistence.database import make_engine, make_sessions

    url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.delenv("DEMO_USER_PASSWORD", raising=False)
    assert seed.main(["--dataset", "demo", "--skip-mock", "--sample-cases"]) == 0
    with make_sessions(make_engine(url))() as s:
        assert len(s.scalars(select(Case)).all()) == len(demo_samples.SAMPLES)
    assert "--sample-cases" in demo_launch.SEED_ARGS  # what the daily reset runs, after emptying the cases
