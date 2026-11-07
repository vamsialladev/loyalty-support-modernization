"""One factor at a time (spec E.4; BENCH-08; docs/experiment-plan.md section 5). On dev only. **LIVE: costs money.**

Each is a new, labelled experiment that changes no pre-registered verdict. Rules-only against the bounded agent is
already B against C. The prompt and the model have one allowed version each here, so they aren't varied.

    uv run python -m evaluations.ablations --budget-usd 0.25
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

import app.ai.harness
import app.services.assisted
from app.adapters.anthropic_model import AnthropicModel
from app.ai.config import AiConfig, ai_config
from app.ai.harness import AiRuntime, SpendCaps
from benchmarks.intake import read_split
from evaluations.live_model import GuardedModel
from evaluations.run import DATASET, SEED_DATA, read_labels, run_cases, write_run
from evaluations.run_config import ROOT, hard_cap_usd, load
from evaluations.world import CUSTOMER, seed_template

ABLATIONS: dict[str, dict[str, Any]] = {
    "no-repair": {"max_repairs": 0},
    "three-turns": {"max_turns": 3},
    "half-context": {"context_chars": 4000},
}
RESERVE = 0.0  # held-out has finished: nothing is left to reserve for


def _changed(over: dict[str, Any], customer_id: str) -> AiConfig:
    config = ai_config(customer_id)
    return replace(config, limits=replace(config.limits, **over))


def run_one(name: str, over: dict[str, Any], budget_usd: float) -> None:
    config = load("arm-c-live")
    assert config.model is not None
    price = ai_config(CUSTOMER).models[config.model]
    guarded = GuardedModel(
        AnthropicModel(config.model),
        price,
        cap_usd=hard_cap_usd(),
        run_limit_usd=budget_usd,
        reserve_usd=RESERVE,
        run_name=f"ablation-{name}",
        kind="ablation",
    )
    runtime = AiRuntime(guarded, SpendCaps(per_run_usd=0.10, daily_usd=hard_cap_usd(), monthly_usd=hard_cap_usd()))
    changed: Any = partial(_changed, over)
    app.ai.harness.ai_config = changed  # type: ignore[attr-defined]
    app.services.assisted.ai_config = changed  # type: ignore[attr-defined]
    try:
        items = read_split("dev", DATASET)
        with tempfile.TemporaryDirectory(prefix="benchmark-", ignore_cleanup_errors=True) as tmp:
            folder = Path(tmp)
            template = seed_template(SEED_DATA, folder)
            results = run_cases(config, items, read_labels("dev", DATASET), template, folder / "run", runtime=runtime)
    finally:
        app.ai.harness.ai_config = ai_config  # type: ignore[attr-defined]
        app.services.assisted.ai_config = ai_config  # type: ignore[attr-defined]
    out = write_run(f"ablation-{name}", config, "dev", results, DATASET, planned_cases=len(items))
    print(f"{name}: {len(results)}/{len(items)} cases, ${sum(r.cost_usd for r in results):.4f}, in {out.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluations.ablations")
    parser.add_argument("--budget-usd", type=float, required=True, help="each ablation's limit")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")  # values are never printed
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("NOT RUN: a live run needs ANTHROPIC_API_KEY in this repo's .env")
        return 0
    for name, over in ABLATIONS.items():
        run_one(name, over, args.budget_usd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
