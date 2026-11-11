"""The protocol research documents exist and keep the spec's reporting rules (PROTO-01, SEC-01, PURP-05; spec G.1)."""

from __future__ import annotations

import re

import pytest

from tests.conftest import ROOT

DOCS = [
    "docs/protocol-catalog.md",
    "docs/protocol-selection.md",
    "docs/protocol-compatibility.md",
    "docs/protocol-adoption-evidence.md",
    "docs/protocol-learning-labs.md",
    "docs/protocol-test-results.md",
]
CORE_FIELDS = (
    "Purpose and layer",
    "Official source",
    "Governance",
    "Pinned specification",
    "SDK and license",
    "Status",
    "Authentication",
    "Limitations",
    "Verification date",
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize("path", DOCS)
def test_each_research_document_exists_and_says_its_a_simulation(path: str) -> None:
    text = read(path)
    assert len(text) > 300
    assert "Simulated engagement" in text or "simulated engagement" in text or "Read 2026-11-11" in text


def test_every_core_protocol_has_the_full_record() -> None:
    text = read("docs/protocol-catalog.md")
    sections = re.split(r"\n### ", text)
    for name in ("MCP: Model Context Protocol", "A2A: Agent2Agent Protocol", "AG-UI: Agent-User Interaction Protocol"):
        section = next(s for s in sections if s.startswith(name))
        for field in CORE_FIELDS:
            assert f"| {field}" in section, (name, field)


def test_acp_is_always_spelled_out() -> None:
    """Spec G.1: "Always spell out which ACP is meant". A bare "ACP" must sit next to its full name."""
    for path in [*DOCS, "docs/rfcs/RFC-0004-protocols.md"]:
        for line in read(path).splitlines():
            if re.search(r"\bACPs?\b", line) and "three" not in line:
                assert any(n in line for n in ("Agent Client", "Agent Communication", "Agentic Commerce")), (path, line)
    catalog = read("docs/protocol-catalog.md")
    for full in ("Agent Client Protocol", "Agent Communication Protocol", "Agentic Commerce Protocol"):
        assert full in catalog


def test_the_draft_ag_ui_version_isnt_presented_as_the_pin() -> None:
    catalog = read("docs/protocol-catalog.md")
    assert "**1.1 is a draft**" in catalog
    assert "Pinned specification | **1.0**" in catalog


def test_no_adoption_claim_without_evidence() -> None:
    text = read("docs/protocol-adoption-evidence.md").lower()
    for claim in ("widely adopted", "industry standard", "everyone uses", "de facto"):
        for found in (m.start() for m in re.finditer(re.escape(claim), text)):
            before = text[max(0, found - 40) : found]
            assert any(word in before for word in ("not ", "n't", "never", "no ")), claim


def test_results_without_a_run_say_not_run() -> None:
    text = read("docs/protocol-test-results.md")
    assert "NOT RUN" in text
    for row in (r for r in text.splitlines() if r.startswith("| ") and "Pass" in r):
        assert re.search(r"tests/|security/evidence/|docs/", row), row  # a pass names its evidence


def test_the_baseline_records_the_protocol_specs_and_agentic_list() -> None:
    text = read("security/standards-baseline.md")
    for item in ("2026-07-28", "A2A specification", "AG-UI specification", "Agentic Applications", "2026-11-11"):
        assert item in text
    matrix = read("security/control-matrix.md")
    for number in range(1, 11):
        assert f"ASI{number:02d}" in matrix


def test_the_milestone_11_rfc_has_every_template_section() -> None:
    text = read("docs/rfcs/RFC-0004-protocols.md")
    # The template's "Risks" section is titled "What could go wrong, and what stops it" here, as in RFC-0003.
    for heading in ("## Context", "## Options considered", "## Decision", "## What could go wrong", "## Rollout"):
        assert heading in text
    assert "## Open questions" in text
    assert "RFC-0004" in read("docs/rfcs/README.md")
