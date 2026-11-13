"""The AG-UI live-run panel in a real browser (Playwright, Chromium; spec G.5, PROTO-05).

The offline stack starts the app with `FEATURE_AG_UI=true` (via `app_env_extra`), and a real worker runs arm C on the
mock model. The panel reads the SSE stream with fetch under the console's strict CSP; a CSP violation would show as a
console error and fail the test. Skipped against the Compose stack, where the flag is off.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from tests.browser.test_legacy_e2e import (  # noqa: F401  (pytest fixtures)
    Stack,
    chromium,
    playwright_api,
    sign_in,
    stack,
)

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(bool(os.environ.get("E2E_BASE_URL")), reason="the Compose stack runs with FEATURE_AG_UI off"),
]
app_env_extra = {"FEATURE_AG_UI": "true"}
expect = playwright_api.expect
WAIT_MS = 90_000


def load_arm_c(stack: Stack) -> int:  # noqa: F811
    from sqlalchemy import select

    from app.persistence.database import make_engine, make_sessions
    from app.persistence.models import Case
    from benchmarks.intake import load_case, read_split

    k01 = sorted(c for c, lab in stack.labels.items() if lab["split"] == "dev" and lab["scenarios"] == ["K01"])[0]
    with make_sessions(make_engine(stack.database_url))() as s:
        load_case(s, next(c for c in read_split("dev", stack.datasets) if c.case_id == k01), arm="C")
        case = s.scalars(select(Case).where(Case.source_ref == k01, Case.arm == "C").order_by(Case.id)).first()
        assert case is not None
        return case.id


def test_the_panel_follows_an_investigation_without_starting_one(chromium: Any, stack: Stack) -> None:  # noqa: F811
    case_id = load_arm_c(stack)
    page = chromium.new_page()
    problems: list[str] = []  # console errors include Content-Security-Policy violations
    page.on("console", lambda msg: problems.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: problems.append(str(exc)))
    sign_in(page, stack, "agent.ana")
    page.goto(f"{stack.base_url}/cases/{case_id}")
    page.get_by_role("button", name="Investigate", exact=True).click()
    expect(page.get_by_test_id("engine-action")).to_be_visible(timeout=WAIT_MS)
    expect(page.get_by_test_id("ai-panel")).to_be_visible(timeout=WAIT_MS)

    page.get_by_role("button", name="Watch the investigation").click()
    events = page.get_by_test_id("live-run-events")
    expect(events).to_contain_text("Watching run", timeout=WAIT_MS)
    expect(events).to_contain_text("Tool: ", timeout=WAIT_MS)
    expect(events).to_contain_text("approval happens on this page", timeout=WAIT_MS)
    text = events.inner_text()
    assert "<" not in text  # rendered as text, never as HTML
    assert problems == []

    # Watching again is a new AG-UI run that only watches: still one investigation on the case.
    page.get_by_role("button", name="Watch the investigation").click()
    expect(events).to_contain_text("approval happens on this page", timeout=WAIT_MS)
    from sqlalchemy import func, select

    from app.persistence.database import make_engine, make_sessions
    from app.persistence.models import AiRun

    with make_sessions(make_engine(stack.database_url))() as s:
        assert s.scalar(select(func.count()).select_from(AiRun).where(AiRun.case_id == case_id)) == 1
