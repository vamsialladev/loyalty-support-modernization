"""Command line: generate, verify, clean, dictionary.

python -m seed_data.generator generate [--seed 20261102] [--scale 1.0]
python -m seed_data.generator verify      # regenerate in a temp folder, compare with the committed manifest
python -m seed_data.generator clean       # delete seed_data/v1 only (benchmark files are committed)
python -m seed_data.generator dictionary  # rewrite docs/data-dictionary.md
"""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from seed_data.generator import DATASET_VERSION, DEFAULT_SEED
from seed_data.generator.dictionary import render_dictionary
from seed_data.generator.generate import SRC_ROOT, generate
from seed_data.generator.review_sheet import write_sheet


def cmd_generate(seed: int, scale: float, root: Path, documents: bool) -> int:
    out = generate(seed, scale, root, documents=documents)
    bench = root / "benchmarks" / "datasets" / DATASET_VERSION
    picks = write_sheet(bench, root / "evaluations" / "label-review" / "review-sheet.csv", seed)
    for key, value in out.counts.items():
        print(f"{key:>22}: {value}")
    print(f"label-review sheet: {len(picks)} cases")
    print(f"manifest: {bench / 'manifest.json'}")
    return 0


def cmd_verify(seed: int, scale: float) -> int:
    committed = json.loads((SRC_ROOT / "benchmarks/datasets" / DATASET_VERSION / "manifest.json").read_text("utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        generate(seed, scale, Path(tmp))
        fresh = json.loads((Path(tmp) / "benchmarks/datasets" / DATASET_VERSION / "manifest.json").read_text("utf-8"))
    diffs = [
        k
        for k in sorted(set(committed["files"]) | set(fresh["files"]))
        if committed["files"].get(k) != fresh["files"].get(k)
    ]
    diffs += [
        f"document {k}"
        for k in sorted(set(committed["documents"]) | set(fresh["documents"]))
        if committed["documents"].get(k) != fresh["documents"].get(k)
    ]
    for d in diffs:
        print(f"DIFFERS: {d}")
    print("verify: identical" if not diffs else f"verify: {len(diffs)} difference(s)")
    return 0 if not diffs else 1


def cmd_clean(root: Path) -> int:
    target = root / "seed_data" / DATASET_VERSION
    if target.exists():
        shutil.rmtree(target)
        print(f"removed {target}")
    else:
        print("nothing to clean")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m seed_data.generator")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("generate", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--seed", type=int, default=DEFAULT_SEED)
        p.add_argument("--scale", type=float, default=1.0)
        if name == "generate":
            p.add_argument("--root", type=Path, default=SRC_ROOT)
            p.add_argument("--no-documents", action="store_true")
    sub.add_parser("clean").add_argument("--root", type=Path, default=SRC_ROOT)
    sub.add_parser("dictionary")
    args = parser.parse_args(argv)
    if args.command == "generate":
        return cmd_generate(args.seed, args.scale, args.root, not args.no_documents)
    if args.command == "verify":
        return cmd_verify(args.seed, args.scale)
    if args.command == "clean":
        return cmd_clean(args.root)
    (SRC_ROOT / "docs" / "data-dictionary.md").write_text(render_dictionary(), encoding="utf-8", newline="\n")
    print("wrote docs/data-dictionary.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
