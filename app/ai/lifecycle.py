"""Model lifecycle: deprecation and retirement tracking (spec E4; ENT-15; ADR-0082).

Each allowed model in `config/ai/<customer>.yaml` carries what the provider has announced: `deprecated`, and
`retires_on` when a retirement date is published (empty when none is). This review turns that, and the age of the
price check, into findings, so an upgrade is planned before the provider forces one. Nothing here guesses a date:
an empty `retires_on` means "none published as of `checked_on`", and the finding says to re-check.

    uv run python -m app.ai.lifecycle                # every allowed model
    uv run python -m app.ai.lifecycle --model claude-haiku-5-5

Exit 1 when the model in use is deprecated, retired or retiring within the warning window: the same rule the harness
uses at run time (a deprecated or unlisted model fails safe to arm B's result). The upgrade procedure is in
`docs/ai-system-card.md`; a model change goes through the release gate (`scripts/release_gate.py`).
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta

from app.ai.config import AiConfig, ai_config

WARN_DAYS = 60  # time to run the release gate, an ablation and the owner's approval before a forced change
RECHECK_DAYS = 90  # how old a "checked_on" may get before the provider's pages are read again


@dataclass(frozen=True)
class Finding:
    model: str
    severity: str  # block | warn | info
    message: str


def review(config: AiConfig, today: date, model: str | None = None) -> list[Finding]:
    findings: list[Finding] = []
    names = [model] if model else sorted(config.models)
    for name in names:
        price = config.models.get(name)
        if price is None:
            findings.append(Finding(name, "block", "not on the allowed list: runs fail safe to arm B's result"))
            continue
        if price.deprecated:
            findings.append(Finding(name, "block", "deprecated by the provider: choose a successor and run the gate"))
        if price.retires_on:
            retires = date.fromisoformat(price.retires_on)
            if retires <= today:
                findings.append(Finding(name, "block", f"retired on {price.retires_on}"))
            elif retires - today <= timedelta(days=WARN_DAYS):
                days = (retires - today).days
                findings.append(
                    Finding(name, "block", f"retires on {price.retires_on}, in {days} days: plan the upgrade")
                )
            else:
                findings.append(Finding(name, "info", f"retires on {price.retires_on}"))
        else:
            findings.append(Finding(name, "info", f"no retirement date published as of {price.checked_on}"))
        checked = date.fromisoformat(price.checked_on)
        if today - checked > timedelta(days=RECHECK_DAYS):
            findings.append(
                Finding(name, "warn", f"price and status last checked {price.checked_on}: re-read the provider's pages")
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ai.lifecycle")
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "").strip() or None)
    parser.add_argument("--customer", default=os.environ.get("APP_CUSTOMER_ID", "hg-demo"))
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = parser.parse_args(argv)
    findings = review(ai_config(args.customer), args.today, args.model)
    for f in findings:
        print(f"{f.severity:5}  {f.model}: {f.message}")
    return 1 if any(f.severity == "block" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
