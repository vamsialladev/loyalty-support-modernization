"""Milestone 2 documents exist, cover what spec A.2 to A.4, E.2 and F4 require, and are linked (Appendix C)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# document -> phrases that must appear (one per required topic)
REQUIRED = {
    "docs/customer-discovery.md": [
        "FICTIONAL",
        "Fictional customer context",
        "Stakeholder map",
        "Personas",
        "interview guide",
        "Simulated sessions",
        "Assumptions to validate",
        "Who owns the problem",
        "What a successful resolution means",
        "When ordinary software is sufficient",
        "What AI adds",
        "Conditions for stopping or redesigning",
    ],
    "docs/business-requirements.md": [
        "Business requirements",
        "Nonfunctional requirements",
        "MVP scope",
        "Exclusions",
        "Success metrics and acceptance criteria",
        "Pilot and rollout plan",
        "Scope-change template",
        "Milestone plan",
    ],
    "docs/product-requirements.md": ["User stories", "What AI does and does not control"],
    "docs/workflow.md": [
        "Current workflow",
        "Proposed workflow",
        "Case states",
        "System boundaries and ownership",
        "Member journey",
    ],
    "docs/architecture.md": ["```mermaid", "Components", "tradeoffs", "Prototype vs pilot vs production"],
    "docs/legacy-discovery.md": [
        "Known functionality",
        "Missing functionality",
        "Configuration errors",
        "Data problems",
        "Operational delays",
        "UI friction",
        "System inventory",
        "Integration contracts",
        "Source register",
        "Data quality assessment",
    ],
    "docs/stage0-loyalty-addendum.md": [
        "4-check test",
        "SOW addendum",
        "Price (projection, method only)",
        "Security questionnaire deltas",
    ],
    "docs/kpi-tree.md": ["Layer 1", "Layer 2", "Layer 3", "Layer 4", "estimate under stated assumptions"],
    "docs/baseline-measurement-plan.md": ["instrumented", "scripted steps, not human time", "Root-cause analysis"],
    "docs/experiment-plan.md": ["A as-is", "Fairness rules", "Ablations"],
    "docs/governance.md": [
        "Responsibility boundaries",
        "RACI",
        "Technical controls",
        "Access request",
        "Security exception",
        "Risk acceptance",
    ],
    "docs/registers.md": ["Access and dependency register", "Project risk register"],
    "security/threat-model.md": ["Trust boundaries", "Actors", "Threats, prioritised"],
}


@pytest.mark.parametrize("doc", sorted(REQUIRED))
def test_document_covers_required_topics(doc):
    text = " ".join((ROOT / doc).read_text(encoding="utf-8").split())  # ignore line wrapping
    missing = [phrase for phrase in REQUIRED[doc] if phrase not in text]
    assert missing == [], f"{doc} is missing: {missing}"


@pytest.mark.parametrize("doc", sorted(REQUIRED))
def test_document_is_linked_from_readme(doc):
    assert f"]({doc})" in (ROOT / "README.md").read_text(encoding="utf-8"), f"README does not link {doc}"


def test_docs_threat_model_points_to_canonical_file():
    assert "../security/threat-model.md" in (ROOT / "docs" / "threat-model.md").read_text(encoding="utf-8")


def test_decisions_cover_spec_a3_topics():
    text = (ROOT / "docs" / "decisions.md").read_text(encoding="utf-8")
    for topic in (
        "what AI does and what stays deterministic",
        "build vs buy",
        "managed vs self-hosted",
        "integration through versioned REST",
        "REST for the core; MCP",
        "full-text search before embeddings",
        "one bounded agent",
        "data processing boundaries",
        "operational ownership",
        "Decision guide",
    ):
        assert topic in text, f"decisions.md has no ADR for {topic!r}"


def test_mermaid_blocks_are_closed():
    for doc in REQUIRED:
        text = (ROOT / doc).read_text(encoding="utf-8")
        assert text.count("```") % 2 == 0, f"{doc} has an unclosed code block"


def test_no_real_brand_names_in_simulated_sessions():
    text = (ROOT / "docs" / "customer-discovery.md").read_text(encoding="utf-8").lower()
    for brand in ("marriott", "hilton", "expedia", "booking.com", "hyatt"):
        assert brand not in text
