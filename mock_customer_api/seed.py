"""Load the synthetic world (`seed_data/v1/`) into the mock customer API's database (spec B.3 control commands).

    python -m mock_customer_api.seed --dataset v1            # refuses if data is already there
    python -m mock_customer_api.seed --dataset v1 --reset    # wipe, then load
    python -m mock_customer_api.seed --cleanup               # wipe only

Reads `MOCK_API_DATABASE_URL` and `MOCK_API_SEED_DIR` (default `seed_data/v1`). The seed folder holds operational data
only (members, stays, ledger, posting queue); labels never reach this service (ADR-0040).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session, sessionmaker

from mock_customer_api import db
from mock_customer_api.service import Problem, counts, wipe

FILES = {
    db.Member: "members.jsonl",
    db.Stay: "stays.jsonl",
    db.LedgerEntry: "ledger.jsonl",
    db.PostingQueueItem: "posting_queue.jsonl",
}
DATASETS = {"v1": "v1", "demo": "v1"}
CHUNK = 1000


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def seed(factory: sessionmaker[Session], seed_dir: Path, *, reset: bool = False) -> dict[str, int]:
    missing = [name for name in FILES.values() if not (seed_dir / name).is_file()]
    if missing:
        raise Problem(
            409,
            "seed_data_missing",
            f"{seed_dir} lacks {', '.join(missing)}; run `python -m seed_data.generator generate` first",
        )
    with factory() as s:
        if counts(s)["members"] and not reset:
            raise Problem(409, "already_seeded", "Data is already loaded; use reset to reload")
        wipe(s)
        for table, name in FILES.items():
            rows = _rows(seed_dir / name)
            columns = {c.key for c in table.__mapper__.column_attrs}
            rows = [{k: v for k, v in row.items() if k in columns} for row in rows]
            for start in range(0, len(rows), CHUNK):
                s.execute(insert(table), rows[start : start + CHUNK])
        s.commit()
        return counts(s)


def cleanup(factory: sessionmaker[Session]) -> dict[str, int]:
    with factory() as s:
        wipe(s)
        s.commit()
        return counts(s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mock_customer_api.seed")
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="v1")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args(argv)
    factory = db.make_sessions(db.make_engine(os.environ["MOCK_API_DATABASE_URL"]))
    seed_dir = Path(os.environ.get("MOCK_API_SEED_DIR", f"seed_data/{DATASETS[args.dataset]}"))
    try:
        result = cleanup(factory) if args.cleanup else seed(factory, seed_dir, reset=args.reset)
    except Problem as exc:
        print(f"{exc.code}: {exc.title}. {exc.detail}".strip(), file=sys.stderr)
        return 1
    for table, n in result.items():
        print(f"{table:>22}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
