"""One command runs a benchmark (spec E.3, Appendix B; BENCH-03). It stores what happened, and decides nothing.

    uv run python -m evaluations.run --arm b --split dev --provider none

Results go to `benchmarks/results/<deterministic|mock|live>/<run name>/`: `results.jsonl`, one record per case, and
`manifest.json`, with the versions that produced them. Raw records are kept, so a corrected metric can re-score old runs
without spending anything. **The held-out split needs `--confirm-frozen`, and a clean tree.**
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from app.adapters.anthropic_model import AnthropicModel
from app.adapters.mock_model import RulesMockModel
from app.ai.config import ai_config
from app.ai.harness import AiRuntime, SpendCaps
from benchmarks.intake import DatasetCase, read_split
from evaluations.journey import Journey
from evaluations.live_model import GuardedModel
from evaluations.run_config import ROOT, THRESHOLDS, RunConfig, hard_cap_usd, load
from evaluations.scoring import CaseResult
from evaluations.world import CUSTOMER, drop_the_duplicate_index, make_world, seed_template

DATASET = ROOT / "benchmarks" / "datasets" / "v1"
SEED_DATA = ROOT / "seed_data" / "v1"
RESULTS = ROOT / "benchmarks" / "results"
CONFIG_BY_ARM = {"a": "arm-a", "a-as-is": "arm-a-as-is", "b": "arm-b", "c-mock": "arm-c-mock", "c-live": "arm-c-live"}
SYNTHETIC = "SYNTHETIC data. Scripted agents and a simulated member and supervisor: not human timing, not real people."


class RunRefused(Exception):
    pass


def read_labels(split: str, dataset_dir: Path = DATASET) -> dict[str, dict[str, Any]]:
    """Evaluator only: `tests/test_generator.py` keeps this out of the app."""
    lines = (dataset_dir / "labels" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()
    return {row["case_id"]: row for row in (json.loads(line) for line in lines if line.strip())}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603, S607


def tree_status() -> str:
    """What's changed in the code and data. A run's own results don't make the tree dirty."""
    return _git("status", "--porcelain", "--", ".", ":!benchmarks/results", ":!benchmarks/reports")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refuse_unless_frozen(split: str, confirm_frozen: bool, tree_status: str) -> None:
    """Never tune on held-out data (spec E.1, F9): that run needs a deliberate flag, and a commit that says what ran."""
    if split != "heldout":
        return
    if not confirm_frozen:
        raise RunRefused("the held-out split needs --confirm-frozen: it's only for a frozen configuration")
    if tree_status.strip():
        raise RunRefused("the held-out split needs a clean working tree, so the commit says exactly what ran")


def runtime_for(config: RunConfig, run_name: str, split: str, budget_usd: float | None) -> AiRuntime | None:
    """No model for arms A and B. A mock for a pipeline check. Live only with a budget, and behind the ledger."""
    if config.arm != "C":
        return None
    if config.provider == "mock":
        return AiRuntime(RulesMockModel())
    load_dotenv(ROOT / ".env")  # values are never printed
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RunRefused("a live run needs ANTHROPIC_API_KEY in this repo's .env")
    assert config.model is not None and config.cost_ceiling_usd is not None
    if budget_usd is None or budget_usd <= 0:
        raise RunRefused("a live run needs --budget-usd")
    if budget_usd > config.cost_ceiling_usd:
        raise RunRefused(f"--budget-usd is above this configuration's ceiling of ${config.cost_ceiling_usd:.2f}")
    price = ai_config(CUSTOMER).models.get(config.model)
    if price is None:
        raise RunRefused(f"{config.model} isn't on the allowed list")
    thresholds = yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))["live_spend"]
    guarded = GuardedModel(
        AnthropicModel(config.model),
        price,
        cap_usd=hard_cap_usd(),
        run_limit_usd=budget_usd,
        reserve_usd=0.0 if split == "heldout" else float(thresholds["heldout_reserve_usd"]),
        run_name=run_name,
    )
    # The world's own spend table starts empty each run, so the ledger is what holds across runs.
    return AiRuntime(guarded, SpendCaps(per_run_usd=0.10, daily_usd=hard_cap_usd(), monthly_usd=hard_cap_usd()))


def run_cases(
    config: RunConfig,
    items: Sequence[DatasetCase],
    labels: dict[str, dict[str, Any]],
    template: Path,
    folder: Path,
    run_number: int = 1,
    *,
    second_look: bool = False,
    runtime: AiRuntime | None = None,
    fault: str | None = None,
) -> list[CaseResult]:
    """A fresh world per run: no run can see another's credits."""
    if config.arm == "C" and runtime is None:
        raise RunRefused("arm C needs a provider")
    world = make_world(template, folder)
    as_is = config.arm == "A_as_is"
    if as_is:
        drop_the_duplicate_index(world.app_engine)
    arm = "A" if as_is else config.arm
    results: list[CaseResult] = []
    try:
        with world.sessions() as s:
            journey = Journey(
                world,
                s,
                arm,
                runtime,
                second_look=second_look,
                as_is_database=folder / "app.db" if as_is else None,
                fault=fault,
            )
            for number, item in enumerate(items, 1):
                result = journey.run(item, labels[item.case_id], run_number, config.kind)
                results.append(result)
                if result.interrupted:
                    break
                if number % 10 == 0:
                    print(f"  {number}/{len(items)} cases", flush=True)
    finally:
        world.close()
    return results


def write_run(
    name: str,
    config: RunConfig,
    split: str,
    results: Sequence[CaseResult],
    dataset_dir: Path,
    root: Path = RESULTS,
    *,
    second_look: bool = False,
    fault: str | None = None,
    planned_cases: int | None = None,
) -> Path:
    folder = root / config.kind / name
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "results.jsonl").open("w", encoding="utf-8", newline="\n") as out:
        for result in results:
            out.write(json.dumps(asdict(result), sort_keys=True) + "\n")
    manifest = {
        "name": name,
        "kind": config.kind,
        "after_stop": "second look (sensitivity variant)" if second_look else "script as written",
        "label": SYNTHETIC,
        "split": split,
        "cases": len(results),
        "planned_cases": planned_cases if planned_cases is not None else len(results),
        "interrupted": any(r.interrupted for r in results),
        "fault": fault,
        "run_number": results[0].run if results else None,
        "total_cost_usd": round(sum(r.cost_usd for r in results), 6),
        "config": asdict(config),
        "dataset_version": config.dataset_version,
        "dataset_sha256": _sha256(dataset_dir / f"{split}.jsonl"),
        "labels_sha256": _sha256(dataset_dir / "labels" / f"{split}.jsonl"),
        "app_commit": _git("rev-parse", "HEAD"),
        "tree_clean": not tree_status(),
        "finished_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return folder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluations.run")
    parser.add_argument("--arm", required=True, choices=sorted(CONFIG_BY_ARM))
    parser.add_argument("--split", required=True, choices=("dev", "validation", "heldout", "stress", "fairness"))
    parser.add_argument("--cases", default="", help="comma-separated case IDs, for a smoke run")
    parser.add_argument("--name", default="", help="the run's folder name")
    parser.add_argument("--confirm-frozen", action="store_true")
    parser.add_argument("--run-number", type=int, default=1)
    parser.add_argument("--budget-usd", type=float, help="live runs: this run's limit, under the owner's cap")
    parser.add_argument("--fault", choices=("commit_then_lost",), help="the lost-response pass (catalog section 3a)")
    parser.add_argument(
        "--second-look",
        action="store_true",
        help="sensitivity variant: work a case again after the re-check stops its credit (RFC-0003)",
    )
    args = parser.parse_args(argv)

    config = load(CONFIG_BY_ARM[args.arm])
    try:
        refuse_unless_frozen(args.split, args.confirm_frozen, tree_status())
        items = read_split(args.split, DATASET)
        wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
        if wanted:
            items = [item for item in items if item.case_id in wanted]
        labels = read_labels(args.split)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        name = args.name or f"{args.arm}-{args.split}-{stamp}"
        runtime = runtime_for(config, name, args.split, args.budget_usd)
        with tempfile.TemporaryDirectory(prefix="benchmark-", ignore_cleanup_errors=True) as tmp:
            folder = Path(tmp)
            template = seed_template(SEED_DATA, folder)
            results = run_cases(
                config,
                items,
                labels,
                template,
                folder / "run",
                args.run_number,
                second_look=args.second_look,
                runtime=runtime,
                fault=args.fault,
            )
    except RunRefused as refused:
        print(f"REFUSED: {refused}")
        return 2
    out = write_run(
        name,
        config,
        args.split,
        results,
        DATASET,
        second_look=args.second_look,
        fault=args.fault,
        planned_cases=len(items),
    )
    cost = sum(r.cost_usd for r in results)
    state = "INTERRUPTED" if any(r.interrupted for r in results) else "complete"
    print(f"{config.kind} run {state}: {len(results)}/{len(items)} cases, ${cost:.4f}, in {out.relative_to(ROOT)}.")
    print(SYNTHETIC)
    return 0


if __name__ == "__main__":
    sys.exit(main())
