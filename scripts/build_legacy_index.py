"""Build arm A's frozen keyword index from the policies in force on one date (ADR-0047; defect D09).

    uv run python scripts/build_legacy_index.py                 # rebuild the committed 2026-03-15 index
    uv run python scripts/build_legacy_index.py --check         # exit 1 if the committed file is out of date

The legacy index was built on 2026-03-15 and never rebuilt, so it holds Missing Points Requests v1 and Earning v2.
Rebuilding it with a later date would fix D09 for arm A; only `--as-of 2026-03-15` reproduces the legacy system.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
LEGACY_AS_OF = "2026-03-15"
_HEADING = re.compile(r"^## (\d+(?:\.\d+)*)\.?\s+(.+)$")


def _front_matter(text: str) -> tuple[dict[str, Any], str]:
    _, head, body = text.split("---", 2)
    return yaml.safe_load(head), body


def _in_force(meta: dict[str, Any], day: date) -> bool:
    start = date.fromisoformat(str(meta["effective_from"]))
    end = meta.get("effective_to")
    return meta["status"] != "draft" and start <= day and (end is None or day <= date.fromisoformat(str(end)))


def build(policy_dir: Path, as_of: str) -> dict[str, Any]:
    day = date.fromisoformat(as_of)
    sources, sections = [], []
    for path in sorted(policy_dir.glob("*.md")):
        raw = path.read_bytes()
        meta, body = _front_matter(raw.decode("utf-8"))
        if not _in_force(meta, day):
            continue
        sources.append(
            {
                "policy_id": meta["policy_id"],
                "version": meta["version"],
                "file": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        current: dict[str, Any] | None = None
        for line in body.splitlines():
            match = _HEADING.match(line)
            if match:
                current = {
                    "policy_id": meta["policy_id"],
                    "title": meta["title"],
                    "section_id": match.group(1),
                    "heading": match.group(2).strip(),
                    "lines": [],
                }
                sections.append(current)
            elif current is not None and line.strip():
                current["lines"].append(line.strip())
    for section in sections:
        section["text"] = " ".join(section.pop("lines"))
    return {
        "built_as_of": as_of,
        "synthetic": True,
        "note": "Arm A legacy keyword index, frozen on its build date (defect D09). Never rebuilt in the simulation.",
        "sources": sources,
        "sections": sections,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_legacy_index")
    parser.add_argument("--customer", default="hg-demo")
    parser.add_argument("--as-of", default=LEGACY_AS_OF)
    parser.add_argument("--check", action="store_true", help="fail if the committed index differs from a rebuild")
    args = parser.parse_args(argv)

    out = ROOT / "app/arms/legacy/data" / f"keyword-index-{args.customer}-{args.as_of}.json"
    text = json.dumps(build(ROOT / "policies" / args.customer, args.as_of), indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not out.is_file() or out.read_text(encoding="utf-8") != text:
            print(f"{out.relative_to(ROOT)} is missing or out of date; rebuild it", file=sys.stderr)
            return 1
        print(f"{out.relative_to(ROOT)} matches the policies in force on {args.as_of}")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
