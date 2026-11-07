"""What a supervisor who rubber-stamps can do (ENT-07, LGF-10; spec F7, E2). **Simulated, with seeded wrong proposals.**

On validation cases where the right answer is no credit, a wrong "adjust" is planted on the stored recommendation, as
if a bad result had got through. The simulated supervisor then approves it at a set rate. The question: how many points
move? It measures the write path's re-check, not real reviewers. Real reviewer behaviour comes only from UAT
participants
(Milestone 18).

    uv run python -m evaluations.automation_bias
"""

from __future__ import annotations

import json
import random
import sys
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.domain.case_states import CaseState
from app.domain.eligibility import NextAction
from app.services import conventional
from app.services.cases import WorkflowError, read_time
from app.services.job_handlers import build_handlers
from app.services.write_path import SharedWritePath
from app.worker import Worker
from benchmarks.agents.legacy_scripted import ensure_scripted_users
from benchmarks.intake import DatasetCase, load_case, read_split
from evaluations.run import DATASET, RESULTS, SEED_DATA, read_labels
from evaluations.world import CUSTOMER, World, make_world, seed_template

RATES = (0.0, 0.25, 0.5, 1.0)
SEED = 9
SEEDED_POINTS = 1_000
OUT = RESULTS / "deterministic" / "automation-bias-validation.json"
LABEL = "SYNTHETIC. Simulated supervisor, seeded wrong proposals, deterministic arm B. Not real reviewer behaviour."


def seeded_case(
    world: World, s: Session, item: DatasetCase, approve: bool, path: SharedWritePath, worker: Worker
) -> dict[str, Any]:
    """Plant the wrong proposal on one case, then decide it. Returns what happened."""
    agent, supervisor = ensure_scripted_users(s)
    case = load_case(s, item, CUSTOMER, "B")[0]
    conventional.start_investigation(s, agent, case)
    worker.drain()
    s.expire_all()
    rec = conventional.latest_recommendation(s, case)
    if rec is None or rec.stay_id is None or rec.member_number is None:
        return {"seeded": False}
    rec.action, rec.detail, rec.points_owed = NextAction.ADJUST.value, None, SEEDED_POINTS
    s.commit()
    systems = world.systems(read_time(case))
    try:
        outcome = conventional.request_adjustment(s, agent, case)
    except WorkflowError:
        return {"seeded": True, "stopped_at": "request"}
    if outcome.row is None:
        return {"seeded": True, "stopped_at": "request"}
    decision = path.decide(s, supervisor, outcome.row.id, systems, approve=approve, reason="" if approve else "wrong")
    s.refresh(case)
    if decision.status != "approved" or CaseState(case.status) is not CaseState.APPROVED:
        return {"seeded": True, "approved": decision.status == "approved", "stopped_at": f"decision:{decision.status}"}
    executed = path.execute(s, supervisor, outcome.row.id, systems)
    return {"seeded": True, "approved": True, "stopped_at": f"execution:{executed.status}"}


def run_rate(rate: float, items: list[DatasetCase], template: Path, folder: Path) -> dict[str, Any]:
    rng = random.Random(SEED)  # noqa: S311 - a fixed seed for a simulation, not security
    world = make_world(template, folder)
    path = SharedWritePath(CUSTOMER, secret_key=world.secret_key)
    results = []
    with world.sessions() as s:
        ensure_scripted_users(s)
        handlers = build_handlers(path, world.systems, None)
        worker = Worker(world.sessions, handlers)
        for item in items:
            approve = rng.random() < rate
            result = seeded_case(world, s, item, approve, path, worker)
            results.append({"case_id": item.case_id, "approve": approve, **result})
    stays = world.adjustments_per_stay({stay for row in _stays(items) for stay in row})
    world.close()
    seeded = [r for r in results if r.get("seeded")]
    return {
        "rate": rate,
        "cases": len(items),
        "seeded": len(seeded),
        "approved": sum(1 for r in seeded if r.get("approved")),
        "credits_on_the_platform": sum(stays.values()),
        "stopped_at": sorted({str(r.get("stopped_at")) for r in seeded}),
        "results": results,
    }


def _stays(items: list[DatasetCase]) -> list[set[str]]:
    labels = read_labels("validation", DATASET)
    return [{stay["stay_id"] for stay in labels[item.case_id]["stays"]} for item in items]


def main() -> int:
    labels = read_labels("validation", DATASET)
    items = [
        item
        for item in read_split("validation", DATASET)
        if labels[item.case_id]["expected_outcome"] != "adjusted" and not labels[item.case_id]["owed_total"]
    ]
    with tempfile.TemporaryDirectory(prefix="benchmark-", ignore_cleanup_errors=True) as tmp:
        folder = Path(tmp)
        template = seed_template(SEED_DATA, folder)
        rows = [run_rate(rate, items, template, folder / f"rate-{rate}") for rate in RATES]
    OUT.write_text(json.dumps({"label": LABEL, "rows": rows}, indent=2) + "\n", encoding="utf-8", newline="\n")
    for row in rows:
        print({k: v for k, v in row.items() if k != "results"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
