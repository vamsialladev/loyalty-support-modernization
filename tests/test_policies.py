"""Stored policies, retrieval by date, exact excerpts and controlled publishing (spec B.6; POL-02 to POL-06), on SQLite.

Postgres full-text search itself is in `tests/test_policy_postgres.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.policy import MISSING_POINTS, PolicyRef
from app.domain.roles import Identity, NotPermitted, Role
from app.main import create_app
from app.persistence.database import make_engine, make_sessions
from app.persistence.models import PolicyChunk, PolicyVersionRow, SystemEvent
from app.services import policies, policy_publishing
from app.services.customer_config import CustomerConfig
from app.services.policy_publishing import PublishRefused, load_golden_cases, publish_problems
from app.settings import AppSettings
from tests.arm_a import Browser, make_arm_a
from tests.conftest import ROOT

CUSTOMER = "hg-demo"
CONFIG = CustomerConfig.load(CUSTOMER)
POLICY_DIR = ROOT / "policies/hg-demo"
ADMIN = Identity(1, "admin.ada", "Ada", Role.ADMINISTRATOR)
AGENT = Identity(2, "agent.ana", "Ana", Role.AGENT)
V2 = (POLICY_DIR / "missing-points-requests-v2.md").read_text(encoding="utf-8")


@pytest.fixture
def s(tmp_path: Path) -> Iterator[Session]:
    url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    with make_sessions(make_engine(url))() as session:
        policies.load_policy_set(session, CUSTOMER, POLICY_DIR)
        yield session


def draft_text(version: int = 3, effective_from: str = "2026-12-01", wait: int = 7) -> str:
    """A next version of the missing-points policy, from version 2's text."""
    return (
        V2.replace("version: 2\n", f"version: {version}\n", 1)
        .replace("effective_from: 2026-07-01", f"effective_from: {effective_from}", 1)
        .replace("status: published", "status: draft", 1)
        .replace("supersedes: 1", "supersedes: 2", 1)
        .replace("waiting_period_days: 14", f"waiting_period_days: {wait}", 1)
    )


def row_of(s: Session, version: int, policy_id: str = MISSING_POINTS) -> PolicyVersionRow:
    return s.scalars(
        select(PolicyVersionRow).where(PolicyVersionRow.policy_id == policy_id, PolicyVersionRow.version == version)
    ).one()


# ---------- loading ----------


def test_the_policy_set_loads_once_and_each_section_is_stored(s: Session) -> None:
    rows = policies.version_rows(s, CUSTOMER)
    assert {(r.policy_id, r.version, r.status) for r in rows} == {
        ("guest-rewards-earning", 1, "superseded"),
        ("guest-rewards-earning", 2, "published"),
        ("missing-points-requests", 1, "superseded"),
        ("missing-points-requests", 2, "published"),
    }
    assert policies.load_policy_set(s, CUSTOMER, POLICY_DIR) == []
    v2 = row_of(s, 2)
    chunks = s.scalars(select(PolicyChunk).where(PolicyChunk.policy_version_id == v2.id)).all()
    assert [c.section_id for c in chunks] == v2.sections
    assert v2.source_text == V2 and len(v2.checksum) == 64


def test_a_stored_version_never_changes_silently(s: Session, tmp_path: Path) -> None:
    folder = tmp_path / "edited"
    folder.mkdir()
    (folder / "v2.md").write_text(V2.replace("14 days", "15 days"), encoding="utf-8")
    with pytest.raises(policies.PolicyChanged, match="publish a new version"):
        policies.load_policy_set(s, CUSTOMER, folder)


# ---------- which version applies ----------


def test_the_version_is_chosen_by_checkout_date(s: Session) -> None:
    assert policies.claim_policy_refs(s, CUSTOMER, date(2026, 6, 30)) == [
        "guest-rewards-earning@v2",
        "missing-points-requests@v1",
    ]
    assert policies.claim_policy_refs(s, CUSTOMER, date(2026, 7, 1)) == [
        "guest-rewards-earning@v2",
        "missing-points-requests@v2",
    ]
    assert policies.has_single_claim_policy(s, CUSTOMER, date(2026, 7, 1))
    assert not policies.has_single_claim_policy(s, CUSTOMER, date(2024, 1, 1))


def test_a_citation_opens_the_exact_excerpt_and_version(s: Session) -> None:
    cited = policies.excerpt(s, CUSTOMER, MISSING_POINTS, 2, "7.3")
    assert cited is not None
    assert cited.ref == PolicyRef(MISSING_POINTS, 2, "7.3") and cited.heading == "Corporate travel program"
    assert "`CORP`" in cited.text and cited.source_checksum == row_of(s, 2).checksum and cited.retrieved_at_utc
    assert policies.excerpt(s, CUSTOMER, MISSING_POINTS, 1, "7.3") is None  # version 1 has no such section
    v1 = policies.excerpt(s, CUSTOMER, MISSING_POINTS, 1, "3")
    assert v1 is not None and "30 days" in v1.text


def test_search_looks_only_at_the_versions_in_force_on_the_date(s: Session) -> None:
    after = policies.search(s, CUSTOMER, "corporate travel", date(2026, 8, 1))
    assert [str(c.ref) for c in after] == ["missing-points-requests@v2#7.3"]
    assert policies.search(s, CUSTOMER, "corporate travel", date(2026, 6, 1)) == []
    timing = policies.search(s, CUSTOMER, "claim", date(2026, 6, 1))
    assert "missing-points-requests@v1#3" in [str(c.ref) for c in timing]


def test_search_with_no_policy_in_force_or_no_words_finds_nothing(s: Session) -> None:
    assert policies.search(s, CUSTOMER, "points", date(2024, 1, 1)) == []
    assert policies.search(s, CUSTOMER, "   ", date(2026, 8, 1)) == []


# ---------- publishing ----------


def test_publishing_a_future_version_supersedes_the_one_before(s: Session) -> None:
    draft = policy_publishing.create_draft(s, ADMIN, draft_text(), CUSTOMER)
    assert draft.status == "draft" and draft.created_by == "admin.ada"
    # A draft applies to no stay and can't be cited.
    assert policies.claim_policy_refs(s, CUSTOMER, date(2026, 12, 15)) == [
        "guest-rewards-earning@v2",
        "missing-points-requests@v2",
    ]
    assert policies.excerpt(s, CUSTOMER, MISSING_POINTS, 3, "3") is None

    published = policy_publishing.publish(s, ADMIN, draft.id, CONFIG)
    assert published.status == "published" and published.published_by == "admin.ada"
    assert published.regression is not None and published.regression["golden_cases"] >= 14
    v2 = row_of(s, 2)
    assert (v2.status, v2.effective_to) == ("superseded", "2026-11-30")
    assert "missing-points-requests@v2" in policies.claim_policy_refs(s, CUSTOMER, date(2026, 11, 30))
    assert "missing-points-requests@v3" in policies.claim_policy_refs(s, CUSTOMER, date(2026, 12, 1))
    actions = [e.action for e in s.scalars(select(SystemEvent).order_by(SystemEvent.id))]
    assert actions == ["policy_draft_created", "policy_published"]


def test_changing_what_an_earlier_date_means_is_refused_by_the_golden_cases(s: Session) -> None:
    draft = policy_publishing.create_draft(s, ADMIN, draft_text(effective_from="2026-08-01", wait=30), CUSTOMER)
    with pytest.raises(PublishRefused, match="golden case") as refused:
        policy_publishing.publish(s, ADMIN, draft.id, CONFIG)
    assert any("day the 14-day wait ends" in p for p in refused.value.problems)
    assert row_of(s, 3).status == "draft" and row_of(s, 2).status == "published" and row_of(s, 2).effective_to is None
    event = s.scalars(select(SystemEvent).where(SystemEvent.action == "policy_publish_refused")).one()
    assert event.detail["problems"] == refused.value.problems


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (draft_text(version=4), "next version"),
        (draft_text(effective_from="2026-06-01"), "starts on or before"),
        (draft_text().replace("  claim_window_months: 12\n", ""), "claim_window_months is missing"),
        (draft_text().replace("claim_window_months: 12", "claim_window_months: soon"), "invalid value"),
        (draft_text().replace("supervisor_approval_required: true", "supervisor_approval_required: false"), "invalid"),
        (draft_text().replace("eligible_channels: [direct, phone]", "eligible_channels: direct"), "invalid value"),
    ],
)
def test_a_draft_with_a_bad_version_date_or_rule_is_refused(s: Session, text: str, message: str) -> None:
    draft = policy_publishing.create_draft(s, ADMIN, text, CUSTOMER)
    with pytest.raises(PublishRefused, match=message):
        policy_publishing.publish(s, ADMIN, draft.id, CONFIG)
    assert row_of(s, 2).status == "published"


def test_an_unknown_policy_is_refused(s: Session) -> None:
    text = draft_text(version=1).replace("policy_id: missing-points-requests", "policy_id: gift-cards", 1)
    draft = policy_publishing.create_draft(s, ADMIN, text, CUSTOMER)
    with pytest.raises(PublishRefused, match="not a known policy"):
        policy_publishing.publish(s, ADMIN, draft.id, CONFIG)


def test_a_published_version_cannot_be_published_again_or_replaced(s: Session) -> None:
    with pytest.raises(PublishRefused, match="already published"):
        policy_publishing.publish(s, ADMIN, row_of(s, 2).id, CONFIG)
    with pytest.raises(PublishRefused, match="already exists"):
        policy_publishing.create_draft(s, ADMIN, V2.replace("14 days", "15 days"), CUSTOMER)
    with pytest.raises(PublishRefused, match="no such policy"):
        policy_publishing.publish(s, ADMIN, 99_999, CONFIG)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("not a policy", "can't be read"),
        (V2.replace("customer: hg-demo", "customer: cedarpoint"), "is for cedarpoint"),
        ("x" * (policy_publishing.MAX_DRAFT_CHARS + 1), "longer than"),
    ],
)
def test_a_bad_document_never_becomes_a_draft(s: Session, text: str, message: str) -> None:
    with pytest.raises(PublishRefused, match=message):
        policy_publishing.create_draft(s, ADMIN, text, CUSTOMER)


def test_only_an_administrator_manages_policies(s: Session) -> None:
    with pytest.raises(NotPermitted):
        policy_publishing.create_draft(s, AGENT, draft_text(), CUSTOMER)
    draft = policy_publishing.create_draft(s, ADMIN, draft_text(), CUSTOMER)
    with pytest.raises(NotPermitted):
        policy_publishing.publish(s, AGENT, draft.id, CONFIG)


def test_the_committed_set_passes_its_own_golden_cases() -> None:
    from app.domain.policy import parse_document

    versions = tuple(parse_document(p.read_text(encoding="utf-8")).version for p in POLICY_DIR.glob("*.md"))
    candidate = next(v for v in versions if v.policy_id == MISSING_POINTS and v.version == 2)
    others = tuple(v for v in versions if v is not candidate)
    golden = load_golden_cases(CUSTOMER)
    assert len(golden) >= 14
    assert publish_problems(candidate, others, golden, CONFIG.rules) == []


# ---------- in the console ----------


@pytest.fixture
def console(mock_template: dict[str, Any], tmp_path: Path) -> Any:
    arm = make_arm_a(mock_template, tmp_path)
    return arm, TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory()))


def signed_in(console: Any, username: str, landing: str = "Points queue") -> Browser:
    arm, client = console
    browser = Browser(client)
    browser.login(username, arm.password, landing=landing)
    return browser


def test_an_administrator_stores_and_publishes_a_draft_in_the_console(console: Any) -> None:
    b = signed_in(console, "admin.ada", landing="Configuration")
    assert b.post("/admin/policies/draft", source=draft_text()).status_code == 200
    page = b.get("/admin")
    assert "Run checks and publish" in page.text and "policy_draft_created" in page.text
    arm = console[0]
    with arm.sessions() as s:
        draft_id = row_of(s, 3).id
    done = b.post(f"/admin/policies/{draft_id}/publish")
    assert done.status_code == 200 and "policy_published" in done.text
    with arm.sessions() as s:
        assert row_of(s, 3).published_by == "admin.ada"


def test_a_refused_publish_shows_why(console: Any) -> None:
    b = signed_in(console, "admin.ada", landing="Configuration")
    b.post("/admin/policies/draft", source=draft_text(version=9))
    with console[0].sessions() as s:
        draft_id = row_of(s, 9).id
    refused = b.post(f"/admin/policies/{draft_id}/publish")
    assert refused.status_code == 409 and "next version" in refused.text


@pytest.mark.parametrize("username", ["agent.ana", "supervisor.sam"])
def test_others_cannot_reach_configuration(console: Any, username: str) -> None:
    b = signed_in(console, username)
    assert b.get("/admin").status_code == 403
    assert b.post("/admin/policies/draft", source=draft_text()).status_code == 403


def test_an_auditor_reads_cases_and_changes_nothing(console: Any) -> None:
    arm = console[0]
    with arm.sessions() as s:
        (case,) = arm.load(s, "DV-001")
        case_id = case.id
    b = signed_in(console, "auditor.abe")
    page = b.get(f"/cases/{case_id}")
    assert page.status_code == 200 and "Start work" not in page.text and "Add a note" not in page.text
    assert "Member search" not in page.text and "New case" not in page.text
    assert b.get("/cases/new").status_code == 403
    assert b.get(f"/cases/{case_id}/member").status_code == 403
    assert b.post(f"/cases/{case_id}/start").status_code == 403
    assert b.post(f"/cases/{case_id}/notes", body="audit").status_code == 403


def test_an_administrator_works_no_cases(console: Any) -> None:
    arm = console[0]
    with arm.sessions() as s:
        (case,) = arm.load(s, "DV-001")
        case_id = case.id
    b = signed_in(console, "admin.ada", landing="Configuration")
    assert "Configuration" in b.get("/queue").text
    assert b.get(f"/cases/{case_id}").status_code == 403


def test_an_excerpt_opens_for_a_signed_in_user_and_its_text_is_escaped(console: Any) -> None:
    b = signed_in(console, "agent.ana")
    page = b.get("/policies/missing-points-requests/v2/7.3")
    assert page.status_code == 200 and "Corporate travel program" in page.text and "Version 2" in page.text
    assert b.get("/policies/missing-points-requests/v1/7.3").status_code == 404
    arm, client = console
    with arm.sessions() as s:
        chunk = s.scalars(select(PolicyChunk).where(PolicyChunk.section_id == "7.3")).one()
        chunk.text = "<script>alert(1)</script>"
        s.commit()
    assert "<script>alert(1)" not in b.get("/policies/missing-points-requests/v2/7.3").text
    client.cookies.clear()
    assert "Sign in" in client.get("/policies/missing-points-requests/v2/7.3").text
