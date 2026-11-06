"""Export or check the committed API contract (`app/api/contracts/openapi-v1.json`).

python -m app.api.contract --write   # after an intended change to the API
python -m app.api.contract --check   # exit 1 if the service no longer matches
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.api.router import build_router, contract
from app.settings import AppSettings

CONTRACT = Path(__file__).resolve().parent / "contracts" / "openapi-v1.json"


def current() -> str:
    """Built from the router alone: exporting the contract needs no database and no customer system."""

    def no_systems(_sim: str | None) -> None:
        raise NotImplementedError

    router = build_router(AppSettings(database_url="sqlite://"), no_systems)  # type: ignore[arg-type]
    return json.dumps(contract(router), indent=1, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.api.contract")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = current()
    if args.write:
        CONTRACT.parent.mkdir(parents=True, exist_ok=True)
        CONTRACT.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {CONTRACT}")
        return 0
    same = CONTRACT.is_file() and CONTRACT.read_text(encoding="utf-8") == text
    print("contract: matches" if same else "contract: DIFFERS from the committed openapi-v1.json")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
