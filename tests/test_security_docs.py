"""The security documents exist, say what they must, and claim nothing unbacked (SEC-01, SEC-02, SEC-04, ENT-03)."""

from __future__ import annotations

import pytest

from tests.conftest import ROOT

REQUIRED = [
    "security/standards-baseline.md",
    "security/system-inventory.md",
    "security/data-flow.md",
    "security/threat-model.md",
    "security/risk-register.md",
    "security/control-matrix.md",
    "security/test-plan.md",
    "security/test-results.md",
    "security/residual-risks.md",
    "security/incident-runbooks.md",
    "security/production-readiness.md",
    "security/evidence/README.md",
    "docs/production-readiness.md",
    "docs/tool-and-access-register.md",
    "docs/data-flow-map.md",
    "docs/data-classification.md",
    "docs/customer-access-checklist.md",
    "docs/identity.md",
    "docs/credential-rotation.md",
    "docs/regulatory-applicability.md",
]
CLAIMS = ("soc 2 compliant", "is compliant", "fully secure", "perfect security", "tamper-proof", "injection is solved")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize("path", REQUIRED)
def test_each_document_exists(path: str) -> None:
    assert len(read(path)) > 100


@pytest.mark.parametrize("path", [p for p in REQUIRED if p.startswith("security/") and "evidence" not in p])
def test_no_document_makes_a_claim_it_cant_back(path: str) -> None:
    text = read(path).lower()
    for claim in CLAIMS:
        for found in (i for i in range(len(text)) if text.startswith(claim, i)):
            before = text[max(0, found - 40) : found]
            assert any(word in before for word in ("not ", "n't", "never", "no ")), (path, claim)


def test_the_baseline_records_versions_and_the_date() -> None:
    text = read("security/standards-baseline.md")
    for item in ("NIST AI 100-1", "NIST AI 600-1", "SP 800-218", "5.0.0", "2026-11-06"):
        assert item in text


def test_the_control_matrix_maps_the_whole_owasp_list() -> None:
    text = read("security/control-matrix.md")
    for number in range(1, 11):
        assert f"LLM{number:02d}" in text


def test_the_register_has_all_four_categories_and_marks_whats_simulated() -> None:
    text = read("docs/tool-and-access-register.md")
    for cell in ("| A |", "| B |", "| C |", "| D |", "**Simulated**", "never called"):
        assert cell in text


def test_results_say_what_wasnt_run() -> None:
    text = read("security/test-results.md")
    assert "NOT RUN" in text and "isn't solved" in text


def test_every_failure_mode_in_the_runbooks_is_there() -> None:
    text = read("security/incident-runbooks.md").lower()
    for incident in (
        "leaked model key",
        "compromised integration credential",
        "unauthorized data access",
        "malicious policy document",
        "unexpected agent action",
        "compromised dependency",
        "excessive model spend",
    ):
        assert incident in text
