"""Export Stage 9's cases and arm C's live runs in eval-harness's format (REUSE-03).

    uv run python -m evaluations.export_eval_harness

Writes `benchmarks/exports/eval-harness/`:
- `p9.jsonl`: the dev and held-out cases, in the harness's case schema. Labels keep their own names under `expected`.
- `p9-arm-c-live.jsonl` and `.meta.json`: a saved harness run. Each output carries the verdicts Stage 9's own scoring
  gave it (`scored`), the way the harness reproduces Projects 1 and 2 with their own metric code at pinned commits.

Only arm C's **live** runs are exported. Mock results never leave this repo as evidence. Validation and stress stay
here, because the harness has no such splits. **SYNTHETIC data.**
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from evaluations.compare import load_run
from evaluations.run import DATASET, RESULTS, read_labels
from evaluations.run_config import ROOT
from evaluations.scoring import (
    CaseResult,
    Label,
    case_success,
    correct_action,
    false_approval,
    false_denial,
    ledger_correct,
)

OUT = ROOT / "benchmarks" / "exports" / "eval-harness"
PROJECT = "loyalty-support-modernization"
SPLITS = {"dev": "dev", "heldout": "held-out"}
PROPERTY_BY_PREFIX = {"BR": "beach-resort", "ML": "mountain-lodge"}
TAGS = {"D23": "multilingual", "S01": "prompt-injection", "S02": "prompt-injection", "D20": "multi-issue"}
RUNS = (("dev", "c-live-dev"), ("heldout", "c-heldout-r1"), ("heldout", "c-heldout-r2"), ("heldout", "c-heldout-r3"))
PRICE_IN, PRICE_OUT = 0.10, 0.50  # per million tokens, from config/ai/hg-demo.yaml, checked 2026-11-06


def property_of(label: Label) -> str:
    """From the claimed stay's prefix, which every case has, even when the stay record is missing upstream (D24)."""
    stays = [s["stay_id"] for s in label["stays"]] + list(label["facts"].get("claimed_stay_ids") or [])
    for stay in stays:
        prefix = stay.split("-", 1)[0]
        if prefix in PROPERTY_BY_PREFIX:
            return PROPERTY_BY_PREFIX[prefix]
    raise ValueError(f"{label['case_id']}: no stay to take a property from")


def case_row(label: Label, request: Mapping[str, Any], split: str, commit: str) -> dict[str, Any]:
    escalate = label["next_action"] == "escalate"
    tags = sorted({TAGS[s] for s in label["scenarios"] if s in TAGS} | ({"must-escalate"} if escalate else set()))
    body = "\n\n".join(r["text"] for r in sorted(request["requests"], key=lambda r: r["received_at_utc"]))
    return {
        "id": label["case_id"],
        "project": PROJECT,
        "property": property_of(label),
        "category": label["scenarios"][0],
        "categories": list(label["scenarios"]),
        "split": SPLITS[split],
        "input": {"email": {"subject": "Missing points", "body": body}},
        "expected": {
            "behaviour": "escalate" if escalate else "answer",
            "next_action": label["next_action"],
            "next_action_detail": label["next_action_detail"],
            "expected_outcome": label["expected_outcome"],
            "eligibility": label["eligibility"],
            "clarification_needed": label["clarification_needed"],
            "expected_final_points": {s["stay_id"]: s["expected_final_points"] for s in label["stays"]},
        },
        "tags": tags,
        "origin": f"exported from Stage 9 (loyalty-support-modernization) at {commit}",
        "notes": "SYNTHETIC. Labels from scenario facts; not independently reviewed.",
    }


def scored(result: CaseResult, label: Label) -> dict[str, bool]:
    """Stage 9's own verdicts, as the pre-registered definitions give them (docs/hypotheses.md section 1)."""
    return {
        "case_success": case_success(result, label),
        "ledger_correct": ledger_correct(result, label),
        "correct_action": correct_action(result, label),
        "no_false_approval": not false_approval(result, label),
        "no_false_denial": not false_denial(result, label),
        "no_duplicate_credit": result.duplicate_credits == 0,
        "no_unauthorized_action": result.unauthorized_actions == 0,
    }


def output_row(result: CaseResult, label: Label) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "run": result.run,
        "kind": "answer",
        "text": "",
        "latency_s": result.latency_s,
        "api_calls": result.ai_runs,
        "tokens_in": result.input_tokens,
        "tokens_out": result.output_tokens,
        "scored": scored(result, label),
    }


def _read_requests(split: str) -> dict[str, dict[str, Any]]:
    lines = (DATASET / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()
    return {row["case_id"]: row for row in (json.loads(line) for line in lines if line.strip())}


def export(out: Path = OUT) -> tuple[int, int]:
    runs = {name: load_run(RESULTS / "live" / name) for _split, name in RUNS}
    commits = {run.manifest["app_commit"][:7] for run in runs.values()}
    commit = ", ".join(sorted(commits))
    cases, outputs = [], []
    for split in SPLITS:
        labels, requests = read_labels(split, DATASET), _read_requests(split)
        cases += [case_row(labels[case], requests[case], split, commit) for case in sorted(labels)]
    for split, name in RUNS:
        labels = read_labels(split, DATASET)
        run = runs[name]
        if run.manifest["kind"] != "live" or run.manifest["interrupted"]:
            raise ValueError(f"{name}: only complete live runs are exported")
        # The dev run is run 1; held-out's three runs keep their numbers. The harness reads runs per split.
        outputs += [output_row(r, labels[r.case_id]) for r in run.results]
    meta = {
        "run_id": "p9-arm-c-live-2026-11-07",
        "project": PROJECT,
        "label": "Stage 9 arm C, live (Milestone 10)",
        "date": "2026-11-07",
        "mode": "live",
        "kind": "candidate",
        "model": "claude-haiku-5-5",
        "settings": {"arm": "C", "configuration": "frozen at 50b69f6"},
        "price_in": PRICE_IN,
        "price_out": PRICE_OUT,
        "description": "Arm C on dev (1 run) and held-out (3 runs). Verdicts from Stage 9's own scoring. SYNTHETIC.",
        "ref": commit,
        "source": f"live runs of loyalty-support-modernization @ {commit}",
    }
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "p9.jsonl", cases)
    _write_jsonl(out / "p9-arm-c-live-2026-11-07.jsonl", sorted(outputs, key=lambda o: (o["run"], o["case_id"])))
    (out / "p9-arm-c-live-2026-11-07.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    return len(cases), len(outputs)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    cases, outputs = export()
    print(f"exported {cases} cases and {outputs} live outputs to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
