"""Load benchmark requests into the app as new cases: the browser demo's queue and the benchmark's intake (ADR-0048).

    uv run python -m benchmarks.intake --split dev --limit 20
    uv run python -m benchmarks.intake --split dev --cases DV-001,DV-002
    powershell -ExecutionPolicy Bypass -File scripts\\stack.ps1 -Action demo-cases

It lives in the benchmark tooling, not in `app/`: the app never refers to the benchmark folders at all
(`tests/test_generator.py`). Runs on the host (the images carry no `benchmarks/` folder, ADR-0040) against
DATABASE_URL, taken from the environment or else from `--env-file` (default `.env`; never printed). Reads ONLY the
request file `benchmarks/datasets/v1/<split>.jsonl`: never `labels/`, never generator metadata. Only the fields a
support tool would receive are kept (received time, channel, sender, web-form fields, text, attachment names); the
dataset's language tag and scenario IDs are not. A request already loaded (same request ID) is skipped.

Arm A's intake has no cross-contact linking: every contact opens its own case, so a member who writes and then phones
about the same stay produces two cases (defect D10). Each case keeps the dataset case ID as `source_ref`.
Prints counts only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.roles import Identity, Role
from app.persistence.models import Case, CaseRequest
from app.services.cases import IntakeRequest, create_case
from app.services.conventional import add_attachment

ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT / "benchmarks" / "datasets" / "v1"
SPLITS = ("dev", "validation", "heldout", "stress", "fairness")
INTAKE = Identity(0, "intake", "Web and email intake", Role.AGENT)


@dataclass(frozen=True)
class DatasetCase:
    case_id: str
    requests: tuple[IntakeRequest, ...]
    attachments: tuple[Path, ...] = ()


def read_split(split: str, dataset_dir: Path = DATASET_DIR) -> list[DatasetCase]:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    path = dataset_dir / f"{split}.jsonl"  # the request file; labels live in labels/ and are never opened here
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        requests = tuple(
            IntakeRequest(
                received_at_utc=r["received_at_utc"],
                contact_channel=r["contact_channel"],
                text=r["text"],
                sender_email=r.get("sender_email"),
                form_member_number=r.get("form_member_number"),
                form_confirmation=r.get("form_confirmation"),
                form_name=r.get("form_name"),
                form_property=r.get("form_property"),
                attachment_names=[Path(a["filename"]).name for a in r.get("attachments", [])],
                request_ref=r.get("request_id"),
            )
            for r in sorted(row["requests"], key=lambda r: r["received_at_utc"])
        )
        seed = dataset_dir.parents[2] / "seed_data" / "v1"
        files = tuple(seed / a["filename"] for r in row["requests"] for a in r.get("attachments", []))
        out.append(DatasetCase(row["case_id"], requests, files))
    return out


def load_case(s: Session, item: DatasetCase, customer_id: str = "hg-demo", arm: str = "A") -> list[Case]:
    """One new case per contact in a dataset case (D10). Returns the cases created; requests already loaded into this
    arm are skipped, so one request can be loaded once per arm."""
    created = []
    for request in item.requests:
        if (
            request.request_ref
            and s.scalars(
                select(CaseRequest)
                .join(Case, Case.id == CaseRequest.case_id)
                .where(CaseRequest.request_ref == request.request_ref, Case.arm == arm)
            ).first()
        ):
            continue
        created.append(create_case(s, INTAKE, request, customer_id=customer_id, source_ref=item.case_id, arm=arm))
    if arm != "A" and created:  # arm A's tool can't open attachments (D22)
        for path in item.attachments:
            add_attachment(s, INTAKE, created[0], path.name, path.read_bytes())
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m benchmarks.intake")
    parser.add_argument("--split", choices=SPLITS, default="dev")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--cases", default="", help="comma-separated case IDs, e.g. DV-001,DV-002")
    parser.add_argument("--arm", choices=("A", "B", "C"), default="A", help="which workflow the new cases use")
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    args = parser.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv(args.env_file)  # never overrides a variable that is already set

    from app.persistence.database import make_engine, make_sessions

    wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
    items = [c for c in read_split(args.split) if not wanted or c.case_id in wanted][: args.limit]
    created = 0
    with make_sessions(make_engine(os.environ["DATABASE_URL"]))() as s:
        for item in items:
            created += len(load_case(s, item, arm=args.arm))
    print(f"demo cases from {args.split}: {created} created from {len(items)} dataset cases (existing ones skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
