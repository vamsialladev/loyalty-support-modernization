"""Count the Part 0.5 completion scores from docs/requirements-matrix.md.

    python scripts/matrix_scores.py           # table for docs/implementation-status.md
    python scripts/matrix_scores.py --json

A row counts as done only when its status is "Implemented and verified" or "Not applicable" (ADR-0017).
"Implemented and verified: with limitations" counts as done too, but its row must say what the limits are, and the
table names every such row so the score never hides them (ADR-0072).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

MATRIX = Path(__file__).resolve().parent.parent / "docs" / "requirements-matrix.md"

SCORES = {
    "core": "Core product functionality",
    "bench": "Benchmarks and evaluation",
    "tools": "Actual-tool exercises",
    "proto": "Protocol labs",
    "sec": "Security controls",
    "personal": "Owner's demonstrated understanding",
    "other": "Other tracked work (not a Part 0.5 score)",
}
LABELS = (
    "Implemented and verified",
    "Implemented but unverified",
    "Configured but untested",
    "Simulated",
    "Documentation-only",
    "Manual step required",
    "Blocked",
    "Deferred",
    "Not applicable",
)
DONE = ("Implemented and verified", "Not applicable")
WITH_LIMITATIONS = "Implemented and verified: with limitations"
LIMITATIONS_MARK = "**Limitations:**"  # what the row's Implementation cell must contain


def with_limitations(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if r["Status"] == WITH_LIMITATIONS]


PLANNED = re.compile(r"Planned \(M\d+\)")


def parse(text: str) -> list[dict[str, str]]:
    """Rows of every table whose header starts with `| ID |` and has Tier, Score and Status columns."""
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in text.splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "ID":
            header = cells
            continue
        if header is None or set(line.replace("|", "").strip()) <= {"-", " "}:
            continue
        if len(cells) != len(header):
            raise ValueError(f"row has {len(cells)} cells, header has {len(header)}: {line[:80]}")
        rows.append(dict(zip(header, cells, strict=True)))
    return rows


def status_kind(status: str) -> str:
    """The Part 0.4 label a status starts with, or 'Planned'. Raises on anything else."""
    if PLANNED.fullmatch(status):
        return "Planned"
    for label in LABELS:
        if status == label or status.startswith(label + ":"):
            return label
    raise ValueError(f"unknown status: {status!r}")


def scores(rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for key in SCORES:
        group = [r for r in rows if r["Score"] == key]
        kinds = Counter(status_kind(r["Status"]) for r in group)
        result[key] = {"total": len(group), "done": sum(kinds[d] for d in DONE), **{k: v for k, v in kinds.items()}}
    unknown = {r["Score"] for r in rows} - set(SCORES)
    if unknown:
        raise ValueError(f"unknown score categories: {sorted(unknown)}")
    return result


def render(result: dict[str, dict[str, int]], rows: list[dict[str, str]]) -> str:
    lines = [
        "| Score | Done (verified) | Total | % | In progress (unverified / configured / docs) |",
        "|---|---|---|---|---|",
    ]
    for key, label in SCORES.items():
        r = result[key]
        pct = f"{100 * r['done'] / r['total']:.0f}%" if r["total"] else "n/a"
        partial = sum(
            r.get(k, 0) for k in ("Implemented but unverified", "Configured but untested", "Documentation-only")
        )
        lines.append(f"| {label} | {r['done']} | {r['total']} | {pct} | {partial} |")
    limited = with_limitations(rows)
    if limited:
        lines.append("")
        lines.append(
            "Verified with limitations (counted as done; the limits are in each row): "
            + ", ".join(r["ID"] for r in limited)
        )
    tiers = Counter(r["Tier"] for r in rows)
    lines.append("")
    lines.append(f"{len(rows)} requirements: " + ", ".join(f"Tier {t}: {n}" for t, n in sorted(tiers.items())))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Completion scores from the requirements matrix")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--matrix", type=Path, default=MATRIX)
    args = parser.parse_args(argv)
    rows = parse(args.matrix.read_text(encoding="utf-8"))
    result = scores(rows)
    print(json.dumps(result, indent=2) if args.json else render(result, rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
