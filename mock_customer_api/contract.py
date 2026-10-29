"""Export or check the committed OpenAPI contract (`mock_customer_api/contracts/openapi-v1.json`).

python -m mock_customer_api.contract --write   # after an intended contract change (bump CONTRACT_VERSION)
python -m mock_customer_api.contract --check   # exit 1 if the service no longer matches the committed contract
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mock_customer_api.api import export_contract

CONTRACT = Path(__file__).resolve().parent / "contracts" / "openapi-v1.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mock_customer_api.contract")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    current = export_contract()
    if args.write:
        CONTRACT.parent.mkdir(parents=True, exist_ok=True)
        CONTRACT.write_text(current, encoding="utf-8", newline="\n")
        print(f"wrote {CONTRACT}")
        return 0
    same = CONTRACT.is_file() and CONTRACT.read_text(encoding="utf-8") == current
    print("contract: matches" if same else "contract: DIFFERS from the committed openapi-v1.json")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
