"""Does a complaint mixed into a points claim reach anyone (ENT-39)? Case success doesn't check this, so this does.

On the dev and validation cases that carry out-of-scope items. **LIVE for arm C: costs a little.**

    uv run python -m evaluations.out_of_scope --budget-usd 0.05
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.domain.case_states import CaseState
from app.persistence.models import Case, CaseEvent
from benchmarks.intake import read_split
from evaluations.journey import Journey
from evaluations.run import DATASET, RESULTS, SEED_DATA, read_labels, runtime_for
from evaluations.run_config import load
from evaluations.world import make_world, seed_template

OUT = RESULTS / "live" / "out-of-scope-check.json"
LABEL = "SYNTHETIC. Dev and validation cases with out-of-scope items. Arm C is live. Not an evaluation of wording."


def check_arm(arm: str, split: str, runtime: Any, template: Path, folder: Path) -> list[dict[str, Any]]:
    labels = read_labels(split, DATASET)
    items = [item for item in read_split(split, DATASET) if labels[item.case_id]["out_of_scope_items"]]
    world = make_world(template, folder)
    rows = []
    with world.sessions() as s:
        journey = Journey(world, s, arm, runtime)
        for item in items:
            result = journey.run(item, labels[item.case_id], 1, "live" if arm == "C" else "deterministic")
            cases = list(s.scalars(select(Case).where(Case.source_ref == item.case_id)))
            ids = [case.id for case in cases]
            events = list(s.scalars(select(CaseEvent.action).where(CaseEvent.case_id.in_(ids))))
            rows.append(
                {
                    "case_id": item.case_id,
                    "arm": arm,
                    "items": labels[item.case_id]["out_of_scope_items"],
                    "outcome": result.outcome,
                    "routed_by_the_system": "out_of_scope_routed" in events,
                    "seen_by_a_person": any(CaseState(case.status) is CaseState.ESCALATED for case in cases),
                    "in_billing_queue": any(case.queue != "points" for case in cases),
                    "cost_usd": result.cost_usd,
                }
            )
    world.close()
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluations.out_of_scope")
    parser.add_argument("--budget-usd", type=float, required=True)
    args = parser.parse_args(argv)
    rows: list[dict[str, Any]] = []
    runtime = runtime_for(load("arm-c-live"), "out-of-scope-check", "heldout", args.budget_usd)
    with tempfile.TemporaryDirectory(prefix="benchmark-", ignore_cleanup_errors=True) as tmp:
        folder = Path(tmp)
        template = seed_template(SEED_DATA, folder)
        for split in ("dev", "validation"):
            for arm in ("A", "B", "C"):
                rows += check_arm(arm, split, runtime if arm == "C" else None, template, folder / f"{split}-{arm}")
    OUT.write_text(json.dumps({"label": LABEL, "rows": rows}, indent=2) + "\n", encoding="utf-8", newline="\n")
    for arm in ("A", "B", "C"):
        mine = [r for r in rows if r["arm"] == arm]
        reached = sum(r["routed_by_the_system"] or r["seen_by_a_person"] or r["in_billing_queue"] for r in mine)
        print(f"arm {arm}: the complaint reached someone or a queue in {reached}/{len(mine)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
