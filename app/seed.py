"""Quickstart seed (spec F.2): migrate the app database, create the local demo accounts, load the initial policy set,
then ask the mock customer API to load the dataset.

    docker compose exec app python -m app.seed --dataset demo          # 'demo' is an alias for v1
    docker compose exec app python -m app.seed --dataset demo --reset  # reload the mock systems from scratch

Safe to run again: the migration, the demo accounts and the policy set are repeatable, and data already loaded in the
mock API counts as success (ADR-0052, ADR-0057). Reads DATABASE_URL, MOCK_API_URL, MOCK_API_TOKEN and DEMO_USER_PASSWORD
(the demo accounts are created only when it is set; ADR-0045). Prints counts and usernames only, never a password or
token.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parent.parent


def _load_policies() -> None:
    from app.persistence.database import make_engine, make_sessions
    from app.services.customer_config import CustomerConfig
    from app.services.policies import load_policy_set

    config = CustomerConfig.load(os.environ.get("APP_CUSTOMER_ID", "hg-demo"))
    with make_sessions(make_engine(os.environ["DATABASE_URL"]))() as s:
        added = load_policy_set(s, config.customer_id, ROOT / config.policy_set)
    print("policies: " + (", ".join(added) if added else "already loaded"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed")
    parser.add_argument("--dataset", choices=["demo", "v1"], default="demo")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args(argv)

    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    print("app database: migrated to head")
    password = os.environ.get("DEMO_USER_PASSWORD", "")
    if password:
        from app.adapters.local_demo_identity import ensure_demo_users
        from app.persistence.database import make_engine, make_sessions

        with make_sessions(make_engine(os.environ["DATABASE_URL"]))() as s:
            print("demo accounts: " + ", ".join(ensure_demo_users(s, password)))
    else:
        print("demo accounts: skipped (DEMO_USER_PASSWORD is not set)")
    _load_policies()

    url = os.environ.get("MOCK_API_URL", "http://localhost:8020")
    resp = httpx.post(
        f"{url}/_control/seed",
        params={"dataset": "v1", "reset": str(args.reset).lower()},
        headers={"Authorization": f"Bearer {os.environ['MOCK_API_TOKEN']}"},
        timeout=300,
    )
    problem = resp.json() if resp.headers.get("content-type", "").startswith("application/") else {}
    if resp.status_code == 409 and problem.get("code") == "already_seeded":
        print("mock data already loaded, skipped")  # seeding twice is fine; --reset reloads on purpose
        return 0
    if resp.status_code != 200:
        print(
            f"mock customer API refused the seed: {resp.status_code} {problem.get('code', '')} "
            f"{problem.get('title', '')}".strip(),
            file=sys.stderr,
        )
        return 1
    for table, n in resp.json()["counts"].items():
        print(f"mock {table:>20}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
