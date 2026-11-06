"""The live spending ledger: the owner's hard cap, enforced by this code (RFC-0003).

`benchmarks/results/live/spend-ledger.jsonl` is append-only, committed and never reset, so the cap holds across runs and
sessions. Each live call adds what it measured. Before a call, the caller asks whether the most that call could cost
still fits. The cost uses list prices from `config/ai/`, so it's an estimate of the bill: the provider's console is the
record of what was actually charged, and its own spending limit is the stop that holds even if this code is wrong.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "benchmarks" / "results" / "live" / "spend-ledger.jsonl"
KINDS = ("smoke", "evaluation", "ablation")


class CapReached(Exception):
    """This call could pass the cap, so it doesn't happen."""


@dataclass(frozen=True)
class SpendEntry:
    kind: str
    run: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    at_utc: str


def spent_usd(ledger: Path = LEDGER) -> float:
    if not ledger.exists():
        return 0.0
    lines = ledger.read_text(encoding="utf-8").splitlines()
    return sum(float(json.loads(line)["cost_usd"]) for line in lines if line.strip())


def require_room(worst_case_usd: float, cap_usd: float, reserve_usd: float = 0.0, ledger: Path = LEDGER) -> None:
    """Raises CapReached unless the most this call could cost fits under the cap, leaving any reserve untouched."""
    if worst_case_usd < 0:
        raise ValueError("a cost can't be negative")
    spent = spent_usd(ledger)
    if spent + worst_case_usd + reserve_usd > cap_usd:
        raise CapReached(
            f"spent ${spent:.4f}; this call could add ${worst_case_usd:.4f}; "
            f"reserved ${reserve_usd:.2f}; the cap is ${cap_usd:.2f}"
        )


def record(
    kind: str, run: str, model: str, input_tokens: int, output_tokens: int, cost_usd: float, ledger: Path = LEDGER
) -> SpendEntry:
    if kind not in KINDS:
        raise ValueError(f"unknown kind of spending: {kind}")
    if cost_usd < 0:
        raise ValueError("a cost can't be negative")
    entry = SpendEntry(
        kind, run, model, input_tokens, output_tokens, cost_usd, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8", newline="\n") as out:
        out.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
    return entry
