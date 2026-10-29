"""The pre-registered defect catalog and hypotheses stay complete (Appendix F1, F3, F5; ADR-0016, ADR-0018).

These tests pin the structure, not the wording. Changing a pre-registered threshold or defect also needs an entry in
the document's change log (F9).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = (ROOT / "docs" / "legacy-defect-catalog.md").read_text(encoding="utf-8")
HYPOTHESES = (ROOT / "docs" / "hypotheses.md").read_text(encoding="utf-8")

CLASSES = {
    "Data fix",
    "Configuration fix",
    "Integration fix",
    "UI fix",
    "Training/process",
    "AI-assisted",
    "None possible",
}


def rows(text: str, first_cell: str) -> dict[str, list[str]]:
    """Table rows whose first cell matches the pattern, keyed by that cell."""
    found = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if re.fullmatch(first_cell, cells[0]):
            found.setdefault(cells[0], cells)
    return found


def test_documents_are_marked_preregistered():
    for text in (CATALOG, HYPOTHESES):
        assert "**Pre-registered 2026-10-28.**" in text
        assert "DRAFT" not in text
        assert "## Change log (after pre-registration)" in text


def test_catalog_has_every_defect_with_all_columns():
    defects = rows(CATALOG, r"D\d\d")
    assert sorted(defects) == [f"D{n:02d}" for n in range(1, 26)]
    for defect_id, cells in defects.items():
        assert len(cells) == 11, f"{defect_id} needs the 11 F3 columns"


def test_summary_assigns_one_primary_class_per_defect():
    summary = {}
    for line in CATALOG.split("## 2a.", 1)[1].split("## 2b.", 1)[0].splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and re.fullmatch(r"D\d\d", cells[1]):
            summary[cells[1]] = cells[0]
    assert sorted(summary) == [f"D{n:02d}" for n in range(1, 26)]
    assert set(summary.values()) <= CLASSES
    assert {k for k, v in summary.items() if v == "None possible"} == {"D24", "D25"}


def test_controls_and_safety_scenarios_present():
    assert sorted(rows(CATALOG, r"K\d\d")) == [f"K{n:02d}" for n in range(1, 7)]
    assert sorted(rows(CATALOG, r"S\d\d")) == [f"S{n:02d}" for n in range(1, 6)]


def test_as_is_variant_is_defined_and_excluded_from_h6():
    assert '## 2b. The "A as-is" variant' in CATALOG
    assert "## 3a. Pre-registered descriptive comparison: A as-is vs A" in HYPOTHESES
    h6 = rows(HYPOTHESES, r"\*\*H6\*\*")["**H6**"]
    assert "A as-is is excluded" in " ".join(h6)


def test_hypotheses_h1_to_h7_complete():
    table = rows(HYPOTHESES, r"\*\*H[1-7]\*\*")
    assert sorted(table) == [f"**H{n}**" for n in range(1, 8)]
    for hid, cells in table.items():
        assert len(cells) == 7, f"{hid}: hypothesis, metric, slice, threshold, decision rule, prediction"
        assert all(cells), f"{hid} has an empty cell"
    thresholds = {hid: cells[4] for hid, cells in table.items()}
    assert "10 percentage points" in thresholds["**H1**"]
    assert "5 pp" in thresholds["**H2**"]
    assert "15 pp" in thresholds["**H3**"]
    assert "$0.02" in thresholds["**H5**"] and "15 s" in thresholds["**H5**"]
    assert "**0**" in thresholds["**H6**"]
    assert "80%" in thresholds["**H7**"]


def test_decision_rule_and_mock_exclusion_are_stated():
    assert "Mock-provider results never decide a hypothesis" in HYPOTHESES
    assert "10,000 resamples, fixed seed 9" in HYPOTHESES
