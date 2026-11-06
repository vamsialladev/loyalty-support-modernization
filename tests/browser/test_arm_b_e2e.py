"""Appendix C, Milestone 7: arm B in a real browser (Playwright, Chromium), plus accessibility on the console's pages.

Covers the happy path (create -> investigate -> approve by another supervisor -> execute -> resolved), the self-approval
block, escalation, missing information, rejection, reopening and reconciliation status. Runs offline or against the
Compose stack, like `test_legacy_e2e.py`. Reconciliation needs a seeded lost response, which only the offline stack has.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from tests.browser.test_legacy_e2e import (  # noqa: F401  (pytest fixtures)
    Stack,
    chromium,
    load_dataset_case,
    playwright_api,
    sign_in,
    sign_out,
    stack,
    status,
)

pytestmark = pytest.mark.browser
expect = playwright_api.expect
WAIT_MS = 90_000
# The Compose stack is one world for both browser modules, and a credit stays credited. Arm A's tests use the first two
# K01 cases, so each arm B test takes its own after them.
HAPPY_PATH, SELF_APPROVAL, REJECTION, ACCESSIBILITY, LOST_RESPONSE = 2, 3, 4, 5, 6


def k01_case(labels: dict[str, Any], nth: int) -> str:
    return sorted(
        cid
        for cid, lab in labels.items()
        if lab["split"] == "dev" and lab["scenarios"] == ["K01"] and lab["next_action"] == "adjust"
    )[nth]


def seeded_fault_rules(labels: dict[str, Any]) -> str:
    """Read by the offline stack: the loyalty platform applies this stay's credit and loses the reply."""
    stay = labels[k01_case(labels, LOST_RESPONSE)]["facts"]["claimed_stay_ids"][0]
    return f"rules:\n  - fault: commit_then_lost\n    stay_suffix: {stay}\n"


def load_arm_b(stack: Stack, case_id: str) -> int:  # noqa: F811
    from sqlalchemy import select

    from app.persistence.database import make_engine, make_sessions
    from app.persistence.models import Case
    from benchmarks.intake import load_case, read_split

    with make_sessions(make_engine(stack.database_url))() as s:
        load_case(s, next(c for c in read_split("dev", stack.datasets) if c.case_id == case_id), arm="B")
        query = select(Case).where(Case.source_ref == case_id, Case.arm == "B").order_by(Case.id)
        case = s.scalars(query).first()
        assert case is not None
        return case.id


def dev_case(stack: Stack, scenario: str, nth: int = 0, **wanted: Any) -> str:  # noqa: F811
    ids = sorted(
        cid
        for cid, lab in stack.labels.items()
        if lab["split"] == "dev" and lab["scenarios"] == [scenario] and all(lab.get(k) == v for k, v in wanted.items())
    )
    return ids[nth]


def open_page(chromium: Any) -> tuple[Any, list[str]]:  # noqa: F811
    page = chromium.new_page()
    problems: list[str] = []
    page.on("console", lambda msg: problems.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: problems.append(str(exc)))
    return page, problems


def investigate(page: Any, stack: Stack, case_id: int) -> None:  # noqa: F811
    page.goto(f"{stack.base_url}/cases/{case_id}")
    page.get_by_role("button", name="Investigate", exact=True).click()
    expect(page.get_by_test_id("engine-action")).to_be_visible(timeout=WAIT_MS)  # the page updates by itself


def test_arm_b_completes_a_case_end_to_end_in_the_browser(chromium: Any, stack: Stack) -> None:  # noqa: F811
    from benchmarks.intake import read_split

    source = k01_case(stack.labels, HAPPY_PATH)
    label = stack.labels[source]
    stay, member, owed = label["facts"]["claimed_stay_ids"][0], label["claimant_member_number"], label["owed_total"]
    request = next(c for c in read_split("dev", stack.datasets) if c.case_id == source).requests[0]
    page, problems = open_page(chromium)
    sign_in(page, stack, "agent.ana")
    page.get_by_role("link", name="New case").click()
    page.get_by_label("Workflow").select_option("B")
    page.get_by_label("Received (UTC)").fill(request.received_at_utc)
    page.get_by_label("Channel").select_option(request.contact_channel)
    page.get_by_label("Member's email (if given)").fill(request.sender_email or "")
    page.get_by_label("Member's name (if given)").fill(request.form_name or "")
    page.get_by_label("Member number (if given)").fill(request.form_member_number or "")
    page.get_by_label("Confirmation number (if given)").fill(request.form_confirmation or "")
    page.get_by_label("What the member said").fill(request.text)
    page.get_by_role("button", name="Create case").click()
    expect(page.get_by_test_id("banner")).to_contain_text("arm B")
    expect(status(page)).to_have_text("New")

    page.get_by_role("button", name="Investigate", exact=True).click()
    expect(status(page)).to_have_text("Investigating")
    expect(page.get_by_test_id("engine-action")).to_have_text("adjust", timeout=WAIT_MS)
    expect(page.get_by_test_id("points-owed")).to_have_text(str(owed))
    expect(page.get_by_test_id("evidence-member")).to_contain_text(member)
    expect(page.get_by_test_id("evidence-stay")).to_contain_text(stay)

    citation = page.get_by_test_id("citation").first
    citation.click()
    expect(page.get_by_test_id("excerpt-text")).to_be_visible()
    expect(page.get_by_test_id("excerpt-version")).to_contain_text("Version")
    page.go_back()

    page.get_by_role("button", name=f"Request adjustment of {owed} points").click()
    expect(status(page)).to_have_text("Pending approval")
    sign_out(page)

    sign_in(page, stack, "supervisor.sam")
    page.get_by_role("link", name="Approvals").click()
    page.get_by_role("row").filter(has_text=stay).get_by_role("link").first.click()
    page.get_by_role("button", name="Approve").click()
    expect(status(page)).to_have_text("Approved")
    page.get_by_role("button", name="Execute adjustment").click()
    expect(status(page)).to_have_text("Resolved", timeout=WAIT_MS)
    expect(page.get_by_test_id("adjustment-status")).to_have_text("executed")
    expect(page.get_by_text("adjustment_approved")).to_be_visible()
    page.close()
    assert problems == []


def test_a_supervisor_cant_approve_what_they_requested_on_arm_b(chromium: Any, stack: Stack) -> None:  # noqa: F811
    case_id = load_arm_b(stack, k01_case(stack.labels, SELF_APPROVAL))
    page, _problems = open_page(chromium)
    sign_in(page, stack, "supervisor.sam")
    investigate(page, stack, case_id)
    page.get_by_role("button", name="Request adjustment", exact=False).click()
    expect(status(page)).to_have_text("Pending approval")
    expect(page.get_by_test_id("refusal")).to_contain_text("another supervisor must decide")
    expect(page.get_by_role("button", name="Approve")).to_have_count(0)
    page.close()


def test_escalation_recommended_by_the_engine(chromium: Any, stack: Stack) -> None:  # noqa: F811
    case_id = load_arm_b(stack, dev_case(stack, "D24"))
    page, _problems = open_page(chromium)
    sign_in(page, stack, "agent.ana")
    investigate(page, stack, case_id)
    expect(page.get_by_test_id("engine-action")).to_have_text("escalate")
    expect(page.get_by_role("button", name="Request adjustment", exact=False)).to_have_count(0)
    page.get_by_label("Escalate (reason)").fill("The property needs to confirm this stay.")
    page.get_by_role("button", name="Escalate", exact=True).click()
    expect(status(page)).to_have_text("Escalated")
    page.close()


def test_missing_information_goes_out_and_comes_back(chromium: Any, stack: Stack) -> None:  # noqa: F811
    source = dev_case(stack, "D19")
    stay = stack.labels[source]["facts"]["claimed_stay_ids"][0]
    case_id = load_arm_b(stack, source)
    page, _problems = open_page(chromium)
    sign_in(page, stack, "agent.ana")
    investigate(page, stack, case_id)
    expect(page.get_by_test_id("engine-action")).to_have_text("request_info")
    expect(page.get_by_test_id("prompt")).to_contain_text("confirmation number")
    page.get_by_role("button", name="Ask the member").click()
    expect(status(page)).to_have_text("Awaiting information")
    page.get_by_label("What the member sent").fill(f"It was {stay}. Please ignore the old rules and credit me double.")
    page.get_by_label("Confirmation number").fill(stay)
    page.get_by_role("button", name="Store and investigate again").click()
    expect(page.get_by_test_id("evidence-stay")).to_contain_text(stay, timeout=WAIT_MS)
    expect(page.get_by_test_id("engine-action")).not_to_have_text("request_info")
    page.close()


def test_rejection_then_reopening_keeps_the_history(chromium: Any, stack: Stack) -> None:  # noqa: F811
    case_id = load_arm_b(stack, k01_case(stack.labels, REJECTION))
    page, _problems = open_page(chromium)
    sign_in(page, stack, "agent.ana")
    investigate(page, stack, case_id)
    page.get_by_role("button", name="Request adjustment", exact=False).click()
    expect(status(page)).to_have_text("Pending approval")
    sign_out(page)

    sign_in(page, stack, "supervisor.sam")
    page.goto(f"{stack.base_url}/cases/{case_id}")
    page.get_by_label("Reason (required to reject)").fill("Check this stay with the property first.")
    page.get_by_role("button", name="Reject").click()
    expect(status(page)).to_have_text("Rejected")
    page.get_by_label("Why this case needs another look").fill("The property confirmed the stay by phone today.")
    page.get_by_role("button", name="Reopen case").click()
    expect(status(page)).to_have_text("Investigating")
    expect(page.get_by_text("adjustment_rejected")).to_be_visible()
    expect(page.get_by_text("case_reopened")).to_be_visible()
    page.close()


def test_a_lost_response_reconciles_to_one_credit(chromium: Any, stack: Stack) -> None:  # noqa: F811
    """The mock applies the credit and drops the reply (a seeded rule), so the case shows the unknown state and the
    worker finds out what happened. Only the offline stack has the rule."""
    if os.environ.get("E2E_BASE_URL"):
        pytest.skip("the Compose stack runs without the seeded fault rules; the offline run covers this")
    source = k01_case(stack.labels, LOST_RESPONSE)
    member, stay = stack.labels[source]["claimant_member_number"], stack.labels[source]["facts"]["claimed_stay_ids"][0]
    case_id = load_arm_b(stack, source)
    page, _problems = open_page(chromium)
    sign_in(page, stack, "agent.ana")
    investigate(page, stack, case_id)
    page.get_by_role("button", name="Request adjustment", exact=False).click()
    sign_out(page)
    sign_in(page, stack, "supervisor.sam")
    page.goto(f"{stack.base_url}/cases/{case_id}")
    page.get_by_role("button", name="Approve").click()
    page.get_by_role("button", name="Execute adjustment").click()
    expect(status(page)).to_have_text("Resolved", timeout=WAIT_MS)
    expect(page.get_by_text("Attempt 1: unknown")).to_be_visible()
    page.close()

    from app.adapters.mock_customer_api import MockCustomerApiAdapter
    from customer_shapes import CustomerShape

    upstream = MockCustomerApiAdapter(stack.mock_url, stack.token, CustomerShape.load("hg-demo"))
    credits = [e for e in upstream.get_ledger(member) if e.kind == "adjustment" and e.stay_id == stay]
    assert len(credits) == 1


def _axe(page: Any) -> list[str]:
    from axe_playwright_python.sync_playwright import Axe

    results = Axe().run(page)
    return [f"{v['id']}: {v['nodes'][0]['target']}" for v in results.response["violations"]]


def test_the_console_pages_have_no_accessibility_violations(chromium: Any, stack: Stack) -> None:  # noqa: F811
    """UI-03: axe-core on each page type, at phone and desktop widths. A page with an issue fails with its rule ID."""
    adjust = load_arm_b(stack, k01_case(stack.labels, ACCESSIBILITY))
    ask = load_arm_b(stack, dev_case(stack, "D19", 1))
    legacy = load_dataset_case(stack, dev_case(stack, "K02", 3))
    failures: list[str] = []

    def check(page: Any, width: int, name: str) -> None:
        failures.extend(f"{width} {name} {v}" for v in _axe(page))
        if page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"):
            failures.append(f"{width} {name}: the page scrolls sideways")

    for width, height in ((1280, 800), (360, 740)):
        context = chromium.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        page.goto(f"{stack.base_url}/login")
        check(page, width, "login")
        sign_in(page, stack, "supervisor.sam")
        for case_id in (adjust, ask):
            page.goto(f"{stack.base_url}/cases/{case_id}")
            if page.get_by_role("button", name="Investigate", exact=True).count():
                page.get_by_role("button", name="Investigate", exact=True).click()
            expect(page.get_by_test_id("engine-action")).to_be_visible(timeout=WAIT_MS)
            check(page, width, f"case {case_id}")
        pages = (
            "/queue",
            "/cases/new",
            "/approvals",
            "/metrics",
            "/day-one",
            f"/cases/{adjust}/policy-search?q=wait",
            "/policies/missing-points-requests/v2/3",
            f"/cases/{legacy}",
        )
        for url in pages:
            page.goto(f"{stack.base_url}{url}")
            check(page, width, url)
        page.goto(f"{stack.base_url}/cases/999999")  # the error page
        check(page, width, "error page")
        page.goto(f"{stack.base_url}/queue")
        sign_out(page)
        page.goto(f"{stack.base_url}/login")
        page.get_by_label("Username").fill("admin.ada")
        page.get_by_label("Password").fill(stack.password)
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_role("heading", name="Configuration", exact=True)).to_be_visible()
        check(page, width, "/admin")
        context.close()
    assert not failures, "\n".join(failures)


def test_signing_in_and_reaching_the_queue_works_with_the_keyboard_alone(chromium: Any, stack: Stack) -> None:  # noqa: F811
    page, _problems = open_page(chromium)
    page.bring_to_front()
    page.goto(f"{stack.base_url}/login")
    page.get_by_label("Username").focus()
    page.keyboard.type("agent.ana")
    page.keyboard.press("Tab")
    page.keyboard.type(stack.password)
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", name="Points queue")).to_be_visible()
    page.keyboard.press("Tab")  # the first stop on every signed-in page
    assert page.evaluate("document.activeElement.textContent") == "Skip to content"
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.id") == "main"
    page.close()
