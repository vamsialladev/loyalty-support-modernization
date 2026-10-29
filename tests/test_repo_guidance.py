"""Milestone 1 guidance and tracking files exist and say what they must (spec 0.5, 0.6, 0.7, D.2, H.2)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

TRACKING = [
    "implementation-plan.md",
    "implementation-status.md",
    "requirements-matrix.md",
    "feature-checklist.md",
    "verification-log.md",
    "decisions.md",
    "known-limitations.md",
    "session-handoff.md",
]
MILESTONE_1_DOCS = [
    "continuity.md",
    "portfolio-presentation-addendum.md",
    "backlog.md",
    "tool-access-matrix.md",
    "accounts-setup.md",
    "portfolio-coverage-map.md",
]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", TRACKING + MILESTONE_1_DOCS)
def test_tracking_files_exist(name):
    path = ROOT / "docs" / name
    assert path.is_file(), f"docs/{name} is missing"
    assert len(path.read_text(encoding="utf-8").strip()) > 200, f"docs/{name} is nearly empty"


def test_claude_md_has_mode_guidance():
    text = read("CLAUDE.md")
    section = text.split("## Model and mode guidance", 1)[1].split("\n## ", 1)[0]
    assert "Opus for all milestones" in section
    assert "wait for the owner to confirm" in section
    for milestone in ("**6**", "**8**", "**10**", "**11**"):
        assert milestone in section
    assert "two fix attempts" in section
    assert "/model" in section and "Shift+Tab" in section
    assert "docs/portfolio-presentation-addendum.md" in text


def test_claude_md_keeps_the_d2_rules():
    text = read("CLAUDE.md")
    for rule in ("Never weaken or delete a failing test", "deterministic Python only", "Never push without"):
        assert rule in text


def test_agent_guides_point_to_claude_md():
    agents = read("AGENTS.md")
    cursor = read(".cursor/rules/project-standard.mdc")
    for text in (agents, cursor):
        assert "CLAUDE.md" in text and "docs/MASTER-SPEC.md" in text
        assert "deterministic Python" in text
    assert re.search(r"^alwaysApply: true$", cursor, re.MULTILINE)


def test_decisions_cover_resolved_topics():
    text = read("docs/decisions.md")
    for n in range(1, 11):
        assert f"## ADR-{n:04d}:" in text, f"ADR-{n:04d} (spec 0.6) is missing"


def test_backlog_lists_stage_10():
    text = read("docs/backlog.md")
    assert "Stage 10" in text
    for item in ("Kafka", "AIOps", "Outbox", "Java", "Workflow-automation"):
        assert item in text


def test_addendum_saved_and_tracked():
    addendum = read("docs/portfolio-presentation-addendum.md")
    assert "Narrated with a generated voice; captions included." in addendum
    matrix = read("docs/requirements-matrix.md")
    for n in range(1, 11):
        row = next((line for line in matrix.splitlines() if line.startswith(f"| PA-{n:02d} |")), None)
        assert row is not None, f"PA-{n:02d} missing from the requirements matrix"
        assert "| 4 |" in row, f"PA-{n:02d} must be Tier 4"


def test_continuity_records_required_topics():
    text = read("docs/continuity.md")
    for topic in (
        "Beach Resort",
        "Mountain Lodge",
        "Guest Rewards",
        "Platinum",
        "Writing tone",
        "How metrics are presented",
        "Status vocabulary",
        "synthetic data shapes",
        "CI and eval conventions",
    ):
        assert topic in text, f"continuity.md does not cover {topic!r}"


PURPOSE_DOCS = [
    "project-purpose.md",
    "real-system-swap-guide.md",
    "onboarding.md",
    "technical-strategy.md",
    "scaling-and-limits.md",
    "tech-debt-register.md",
    "tco.md",
    "rfcs/README.md",
    "executive-brief.md",
    "role-coverage-map.md",
    "data-sources.md",
    "using-at-a-company.md",
    "fde-tool-map.md",
    "owner-exercises.md",
]

ROLES = [
    "Forward Deployed / Solutions Engineer",
    "AI / Applied AI Engineer",
    "ML Engineer / Applied Scientist",
    "MLOps / LLMOps Engineer",
    "Data Engineer",
    "Backend / Platform Engineer",
    "Site Reliability Engineer",
    "Security Engineer",
    "Solutions / Enterprise Architect",
    "Staff / Principal Engineer",
    "Engineering Manager / Tech Lead",
    "Product Manager",
    "Technical Program Manager",
    "QA / Test Engineer",
    "Customer Success / Support Lead",
    "Responsible AI / Governance",
    "Executive sponsor",
]


def test_project_purpose_recorded():
    purpose = read("docs/project-purpose.md")
    for phrase in ("reusable, end-to-end Forward Deployed Engineer project", "Principal engineering", "Showcase kits"):
        assert phrase in purpose
    claude = read("CLAUDE.md")
    assert "## Project purpose" in claude and "docs/project-purpose.md" in claude
    assert "What would change this decision" in read("docs/decisions.md")


@pytest.mark.parametrize("name", PURPOSE_DOCS)
def test_purpose_documents_exist(name):
    assert len(read(f"docs/{name}").strip()) > 300, f"docs/{name} is missing or nearly empty"


def test_role_coverage_map_lists_every_role():
    text = read("docs/role-coverage-map.md")
    rows = [line for line in text.splitlines() if line.startswith("| ") and not line.startswith("| Role")]
    named = {line.split("|")[1].strip() for line in rows}
    assert set(ROLES) <= named, f"missing roles: {set(ROLES) - named}"
