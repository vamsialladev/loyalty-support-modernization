"""Public demo mode (spec C.8, L1; SEC-18; ADR-0087). On only with `PUBLIC_DEMO_MODE=true`.

- **Synthetic records only:** the demo image carries the generated synthetic world and nothing else.
- **No shared admin account:** the demo has an agent and a supervisor, signed in by a button; password sign-in is off,
  and no administrator or auditor account exists (`ensure_demo_users(..., public_demo=True)`).
- **Restricted administration and destructive operations:** with no administrator, the admin pages, the kill switch,
  data-subject erasure, legal holds, policy publishing and token issuing can't be reached.
- **Reset only by a controlled mechanism:** `reset()` runs inside the container (once a day, on start, see
  `app/demo_launch.py`) as the database owner. There is no web endpoint for it.
- **Request limits and model budgets:** a daily cap on new cases, the normal rate limits, and mock AI only.
- **All secrets server-side:** the visitor's browser never sees one; the demo's values live in the host's dashboard.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.domain.business_time import format_utc
from app.persistence.models import Case

DEMO_AGENT, DEMO_SUPERVISOR = "agent.ana", "supervisor.sam"
SIGN_IN_AS = {"agent": DEMO_AGENT, "supervisor": DEMO_SUPERVISOR}
DEFAULT_MAX_CASES_PER_DAY = 300
LABEL = "Public demo: mock AI, synthetic data. Resets every day."
# Tables the reset empties: every case and what hangs off it, plus jobs and runs. Accounts, policies, the kill switch
# and the schema version stay. Order doesn't matter with CASCADE.
RESET_TABLES = (
    "case_events",
    "case_attachments",
    "case_evidence",
    "case_notes",
    "case_requests",
    "qa_samples",
    "a2a_tasks",
    "feedback",
    "ai_steps",
    "ai_runs",
    "recommendations",
    "execution_attempts",
    "approvals",
    "adjustment_requests",
    "jobs",
    "cases",
    "sessions",
    "rate_limits",
    "ai_spend",
)


class DemoLimitReached(Exception):
    """The demo's daily cap on new cases is reached. The visitor tries again tomorrow, or after the reset."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"The public demo takes {limit} new cases a day, and today's are used. It resets daily.")
        self.limit = limit
        self.retry_after_seconds = 3600


def max_cases_per_day() -> int:
    raw = os.environ.get("DEMO_MAX_CASES_PER_DAY", "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_MAX_CASES_PER_DAY


def check_daily_case_limit(s: Session, customer_id: str, limit: int | None = None) -> None:
    limit = limit if limit is not None else max_cases_per_day()
    since = format_utc(datetime.now(UTC) - timedelta(days=1))
    made = s.scalar(select(func.count(Case.id)).where(Case.customer_id == customer_id, Case.created_at_utc >= since))
    if (made or 0) >= limit:
        raise DemoLimitReached(limit)


def reset(owner: Session) -> int:
    """Empty every case and what belongs to it. Run as the owner role (audit history is append-only for the app's
    role, ADR-0058). Returns how many cases were removed. The caller re-seeds the mock customer system."""
    removed = int(owner.scalar(select(func.count(Case.id))) or 0)
    dialect = owner.get_bind().dialect.name
    if dialect == "postgresql":
        owner.execute(text("TRUNCATE " + ", ".join(RESET_TABLES) + " RESTART IDENTITY CASCADE"))
    else:  # SQLite in tests: no TRUNCATE; children first
        for table in RESET_TABLES:
            owner.execute(text(f"DELETE FROM {table}"))  # noqa: S608 - fixed table names from this module
    owner.commit()
    return removed
