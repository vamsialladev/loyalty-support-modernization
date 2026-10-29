"""Live checks against a running stack (used by scripts/compose_check.ps1). Prints results, never secret values.

    uv run python scripts/live_smoke.py --env-file <file> [--mock-url http://127.0.0.1:8020]

Needs MOCK_API_FAULTS=true and MOCK_API_SIM_CLOCK=true in that stack (the check stack sets them; your own .env
keeps them false).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.adapters.mock_customer_api import MockCustomerApiAdapter  # noqa: E402
from app.domain.customer_records import AdjustmentRequest  # noqa: E402
from app.ports.customer_systems import UncertainOutcome, UpstreamTimeout  # noqa: E402
from customer_shapes import CustomerShape  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--mock-url", default="http://127.0.0.1:8020")
    args = parser.parse_args()
    token = dotenv_values(args.env_file).get("MOCK_API_TOKEN") or ""
    shape = CustomerShape.load("hg-demo")

    def adapter(**kw: object) -> MockCustomerApiAdapter:
        return MockCustomerApiAdapter(args.mock_url, token, shape, **kw)  # type: ignore[arg-type]

    labels = [json.loads(x) for x in (ROOT / "benchmarks/datasets/v1/labels/heldout.jsonl").read_text().splitlines()]
    pending = next(x for x in labels if x["scenarios"] == ["D06"])
    k01 = next(x for x in labels if x["scenarios"] == ["K01"])
    results: list[tuple[str, bool]] = []

    member, stay = k01["facts"]["claimant"], k01["stays"][0]["stay_id"]
    results.append(("member lookup maps to canonical", adapter().get_member(member).member_number == member))
    results.append(("stay lookup returns the record", adapter().get_stay_records(stay)[0].stay_id == stay))

    stay6 = pending["stays"][0]["stay_id"]
    at_claim = adapter(sim_time=pending["facts"]["received_at_utc"]).get_pending_postings(stay6)
    later = adapter(sim_time="2027-06-01T00:00:00Z").get_pending_postings(stay6)
    results.append(("sim clock: posting pending at the claim, gone later", len(at_claim) == 1 and later == []))

    key = f"live-{uuid.uuid4().hex}"
    req = AdjustmentRequest(member, stay, 100, "live_smoke", "compose-check")
    first, second = adapter().submit_adjustment(req, key), adapter().submit_adjustment(req, key)
    results.append(("same idempotency key replays one adjustment", first.adjustment_id == second.adjustment_id))

    try:
        adapter(fault="timeout", timeout_seconds=1.0, max_retries=0).get_member(member)
        results.append(("real network timeout raises UpstreamTimeout", False))
    except UpstreamTimeout:
        results.append(("real network timeout raises UpstreamTimeout", True))

    lost_key = f"live-lost-{uuid.uuid4().hex}"
    try:
        adapter(fault="commit_then_lost").submit_adjustment(req, lost_key)
        uncertain = False
    except UncertainOutcome:
        uncertain = True
    found = adapter().find_adjustment(lost_key)
    results.append(("commit-then-lost: uncertain, then found by key", uncertain and found is not None))

    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
