"""The requirements matrix parses, uses known labels, and every test it cites exists."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import matrix_scores  # noqa: E402

ROWS = matrix_scores.parse((ROOT / "docs" / "requirements-matrix.md").read_text(encoding="utf-8"))


def test_matrix_has_rows_for_every_part():
    prefixes = {row["ID"].split("-")[0] for row in ROWS}
    for prefix in (
        "P0",
        "ACC",
        "DISC",
        "ARCH",
        "WP",
        "SEC",
        "TEST",
        "EVAL",
        "BENCH",
        "OPS",
        "PROTO",
        "TOOL",
        "KIT",
        "PORT",
        "ENT",
        "LGF",
        "DOC",
        "ML",
        "METH",
        "LIVE",
        "PA",
        "CONT",
        "REUSE",
    ):
        assert prefix in prefixes, f"no {prefix}-* rows"
    assert len(ROWS) >= 250


def test_ids_are_unique():
    ids = [row["ID"] for row in ROWS]
    assert len(ids) == len(set(ids))


def test_every_status_is_a_known_label():
    for row in ROWS:
        matrix_scores.status_kind(row["Status"])  # raises on an unknown label


def test_tiers_and_scores_are_valid():
    assert {row["Tier"] for row in ROWS} <= {"1", "2", "3", "4"}
    assert {row["Score"] for row in ROWS} <= set(matrix_scores.SCORES)


def test_cited_tests_exist():
    cited = set()
    for row in ROWS:
        cited.update(re.findall(r"(tests/[\w/]+\.py)::(\w+)", row["Evidence"]))
    assert cited, "the matrix should cite at least one test"
    for path, name in sorted(cited):
        source = (ROOT / path).read_text(encoding="utf-8")
        assert re.search(rf"^def {name}\(", source, re.MULTILINE), f"{path}::{name} is cited but does not exist"


def test_verified_rows_cite_evidence():
    for row in ROWS:
        if row["Status"] == "Implemented and verified":
            assert row["Evidence"] not in ("", "—"), f"{row['ID']} is verified without evidence"


def test_scores_count_only_verified():
    table = "\n".join(
        [
            "| ID | Requirement | Tier | Score | Evidence | Status |",
            "|---|---|---|---|---|---|",
            "| X-1 | a | 1 | core | t | Implemented and verified |",
            "| X-2 | b | 1 | core | — | Implemented but unverified |",
            "| X-3 | c | 2 | core | — | Planned (M4) |",
            "| X-4 | d | 2 | sec | — | Not applicable: no uploads |",
        ]
    )
    result = matrix_scores.scores(matrix_scores.parse(table))
    assert result["core"]["total"] == 3 and result["core"]["done"] == 1
    assert result["sec"]["done"] == 1


def test_unknown_status_raises():
    with pytest.raises(ValueError):
        matrix_scores.status_kind("Done")


def test_mismatched_cells_raise():
    with pytest.raises(ValueError):
        matrix_scores.parse("| ID | A | B |\n|---|---|---|\n| X | only two |")


def test_cli_prints_score_table(capsys):
    assert matrix_scores.main([]) == 0
    out = capsys.readouterr().out
    assert "Core product functionality" in out and "Tier 1:" in out
