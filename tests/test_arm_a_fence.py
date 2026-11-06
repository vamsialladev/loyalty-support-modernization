"""The fence around arm A while arms B and C are built (spec F9, TEST-05; ADR-0063).

Recorded before any Milestone 7 code. Two checks, because either alone can miss a change:
- the source of arm A's legacy layer, its rules file and its scripted agent, byte for byte;
- what the scripted agent does with every dev case: path, final status, resolution, step count and points.

No score is computed or stored: nothing here compares a result with a label. A difference means arm A changed, which
pre-registration forbids. Regenerate only with a reason recorded in the defect catalog's change log:

    $env:ARM_A_FENCE_WRITE = "1"; uv run pytest tests/test_arm_a_fence.py; Remove-Item Env:ARM_A_FENCE_WRITE
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.persistence.models import AdjustmentRequestRow, Case
from benchmarks.agents.legacy_scripted import ScriptedLegacyAgent
from benchmarks.intake import load_case, read_split
from tests.arm_a import make_arm_a
from tests.conftest import ROOT

FENCE = ROOT / "tests/fixtures/arm_a_fence.json"
WRITE = os.environ.get("ARM_A_FENCE_WRITE") == "1"


def fenced_files() -> list[Path]:
    files = sorted((ROOT / "app/arms/legacy").rglob("*.py")) + sorted((ROOT / "config/legacy").rglob("*"))
    return [*files, ROOT / "benchmarks/agents/legacy_scripted.py"]


def source_hashes() -> dict[str, str]:
    """Line endings normalized, so a Windows checkout and CI agree."""
    out = {}
    for path in fenced_files():
        if path.is_file():
            out[path.relative_to(ROOT).as_posix()] = hashlib.sha256(
                path.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
    return out


def scripted_paths(template: dict[str, Any], tmp_path: Path) -> dict[str, list[dict[str, Any]]]:
    arm = make_arm_a(template, tmp_path)
    out: dict[str, list[dict[str, Any]]] = {}
    with arm.sessions() as s:
        for item in read_split("dev", arm.datasets):
            load_case(s, item)
        agent = ScriptedLegacyAgent(s, arm.factory(), arm.rules, arm.index)
        for case in list(s.scalars(select(Case).order_by(Case.id))):
            run = agent.run(case)
            query = select(AdjustmentRequestRow.points).where(AdjustmentRequestRow.case_id == case.id)
            out.setdefault(case.source_ref or "", []).append(
                {
                    "path": run.path,
                    "status": run.final_status,
                    "resolution": run.resolution_code,
                    "steps": run.steps,
                    "points": list(s.scalars(query)),
                    "queue": case.queue,
                    "reference_prefix": case.reference.split("-")[0],
                }
            )
    return out


def test_arm_a_source_and_behaviour_match_the_recorded_fence(mock_template: dict[str, Any], tmp_path: Path) -> None:
    current = {"source": source_hashes(), "scripted_dev_paths": scripted_paths(mock_template, tmp_path)}
    if WRITE:
        FENCE.parent.mkdir(exist_ok=True)
        FENCE.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        pytest.skip("wrote the fence")
    recorded = json.loads(FENCE.read_text(encoding="utf-8"))
    assert current["source"] == recorded["source"], "arm A's source changed: pre-registration forbids it"
    differing = [
        cid
        for cid in sorted(set(recorded["scripted_dev_paths"]) | set(current["scripted_dev_paths"]))
        if recorded["scripted_dev_paths"].get(cid) != current["scripted_dev_paths"].get(cid)
    ]
    assert not differing, f"arm A now behaves differently on {differing[:10]}"
    assert len(recorded["scripted_dev_paths"]) == 100


def test_the_fence_stores_no_score_and_no_label() -> None:
    text = FENCE.read_text(encoding="utf-8")
    for word in ("expected_outcome", "accuracy", "correct", "claimant_member_number", "scenarios"):
        assert word not in text
