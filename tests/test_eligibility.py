"""The deterministic eligibility engine, rule by rule, on hand-written facts (spec B.7, Part D; ELIG-01, POL-06)."""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import date

import pytest

from app.domain.business_time import add_months, business_date
from app.domain.customer_records import LedgerEntry, PendingPosting, StayRecord
from app.domain.eligibility import (
    CustomerRules,
    Eligibility,
    EligibilityResult,
    ExistingCredit,
    NextAction,
    StayClaim,
    combine,
    evaluate_stay,
)
from app.domain.policy import PolicyFormatError, parse_document, versions_in_force
from app.services.customer_config import CustomerConfig
from tests.conftest import ROOT

POLICIES = tuple(
    parse_document(p.read_text(encoding="utf-8")).version for p in (ROOT / "policies/hg-demo").glob("*.md")
)
CUSTOMER = CustomerConfig.load("hg-demo").rules
MEMBER = "GR-00001"
# Checks out 2026-08-01 at noon Eastern: policy v2, 14-day wait, claimable from 2026-08-15, last day 2027-08-01.
CHECKOUT = "2026-08-01T16:00:00Z"
ON_TIME = "2026-09-01T12:00:00Z"
STAY = StayRecord(
    record_id="R1",
    stay_id="BR-1000",
    property="beach-resort",
    member_on_booking=True,
    arrival_date="2026-07-30",
    nights=2,
    checkout_at_utc=CHECKOUT,
    status="checked_out",
    source_code="WEB",
    rate_code="BAR",
    room_revenue_cents=45_099,
    member_number=MEMBER,
    channel="direct",
)
EARNED = 4_509  # floor(450.99 x 10)


def claim(record: StayRecord = STAY, **changes: object) -> StayClaim:
    base = StayClaim("BR-1000", MEMBER, (record,), (), (), ON_TIME, ON_TIME)
    return replace(base, **changes)  # type: ignore[arg-type]


def evaluate(record: StayRecord = STAY, **changes: object) -> EligibilityResult:
    return evaluate_stay(claim(record, **changes), POLICIES, CUSTOMER)


def posting(points: int, at: str = "2026-08-03T00:00:00Z", member: str = MEMBER, kind: str = "posting") -> LedgerEntry:
    return LedgerEntry(f"L-{points}-{at}", member, kind, points, at, "BR-1000")


def test_missing_points_are_owed_with_their_policy_references() -> None:
    result = evaluate()
    assert (result.status, result.action, result.points_owed) == (Eligibility.ELIGIBLE, NextAction.ADJUST, EARNED)
    assert [str(r) for r in result.policy_refs] == ["missing-points-requests@v2", "guest-rewards-earning@v2#2"]
    assert result.reasons[0].code == "points_missing" and str(result.reasons[0].policy_ref) == (
        "guest-rewards-earning@v2#2"
    )
    assert result.supervisor_limit_points == 20_000


def test_points_are_rounded_down_and_room_revenue_only() -> None:
    assert evaluate(replace(STAY, room_revenue_cents=1_999, taxes_cents=500, fees_cents=500)).points_owed == 199


def test_partly_credited_owes_the_difference() -> None:
    result = evaluate(ledger=(posting(1_000),))
    assert result.action is NextAction.ADJUST and result.points_owed == EARNED - 1_000


def test_a_reversal_and_repost_is_netted() -> None:
    entries = (
        posting(EARNED, "2026-08-02T00:00:00Z"),
        posting(-EARNED, "2026-08-03T00:00:00Z", kind="reversal"),
        posting(EARNED, "2026-08-04T00:00:00Z", kind="repost"),
    )
    result = evaluate(ledger=entries)
    assert result.action is NextAction.NO_ADJUSTMENT_CREDITED and result.existing_credit is ExistingCredit.CREDITED


def test_already_credited_needs_no_adjustment() -> None:
    result = evaluate(ledger=(posting(EARNED),))
    assert (result.status, result.action) == (Eligibility.ELIGIBLE, NextAction.NO_ADJUSTMENT_CREDITED)
    assert result.points_owed == 0 and str(result.reasons[0].policy_ref) == "missing-points-requests@v2#5"


def test_a_stay_not_checked_out_is_ineligible() -> None:
    result = evaluate(replace(STAY, status="in_house"))
    assert (result.status, result.action) == (Eligibility.INELIGIBLE, NextAction.NOT_CHECKED_OUT)


def test_nobody_confirmed_as_the_member_is_denied() -> None:
    result = evaluate(replace(STAY, member_number=None), claimant=None)
    assert (result.action, result.detail) == (NextAction.DENY, "not_a_member")


# ---------- dates: the exact boundary day and time-zone edges (Appendix B) ----------


def test_business_date_reads_utc_as_the_propertys_local_date() -> None:
    assert business_date("2026-07-01T03:30:00Z", "America/New_York") == date(2026, 6, 30)
    assert business_date("2026-07-01T04:30:00Z", "America/New_York") == date(2026, 7, 1)


@pytest.mark.parametrize(
    ("day", "months", "expected"),
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2025, 11, 30), 12, date(2026, 11, 30)),
    ],
)
def test_add_months_keeps_to_the_shorter_month(day: date, months: int, expected: date) -> None:
    assert add_months(day, months) == expected


@pytest.mark.parametrize(
    ("received", "action"),
    [
        ("2026-08-15T03:59:00Z", NextAction.WAIT_UNTIL),  # 23:59 Eastern on the 14th, the day before
        ("2026-08-15T04:00:00Z", NextAction.ADJUST),  # 00:00 Eastern on the 15th, the exact boundary
    ],
)
def test_the_waiting_period_boundary_is_the_local_date(received: str, action: NextAction) -> None:
    result = evaluate(received_at_utc=received, as_of_utc=received)
    assert result.action is action
    if action is NextAction.WAIT_UNTIL:
        assert result.detail == "2026-08-15" and result.status is Eligibility.INELIGIBLE


@pytest.mark.parametrize(
    ("received", "action"),
    [("2027-08-02T03:59:00Z", NextAction.ADJUST), ("2027-08-02T04:00:00Z", NextAction.DENY)],
)
def test_the_claim_window_boundary_is_the_local_date(received: str, action: NextAction) -> None:
    result = evaluate(received_at_utc=received, as_of_utc=received)
    assert result.action is action


def test_the_policy_is_chosen_by_local_checkout_date_not_the_utc_date() -> None:
    # 23:30 Eastern on 30 June is already 1 July in UTC: this stay follows v1 (30-day wait).
    late_june = replace(STAY, checkout_at_utc="2026-07-01T03:30:00Z")
    result = evaluate(late_june, received_at_utc="2026-07-20T12:00:00Z", as_of_utc="2026-07-20T12:00:00Z")
    assert result.policy_refs[0].version == 1
    assert (result.action, result.detail) == (NextAction.WAIT_UNTIL, "2026-07-30")
    july = replace(STAY, checkout_at_utc="2026-07-01T04:30:00Z")
    assert evaluate(july, received_at_utc="2026-07-20T12:00:00Z", as_of_utc="2026-07-20T12:00:00Z").action is (
        NextAction.ADJUST
    )


# ---------- channels ----------


def test_blank_channel_is_derived_from_the_source_code() -> None:
    assert evaluate(replace(STAY, channel=None, source_code="WEB")).action is NextAction.ADJUST
    assert evaluate(replace(STAY, channel=None, source_code="OTA-FEED", member_on_booking=False)).detail == (
        "channel_ineligible"
    )


def test_an_underivable_channel_asks_the_member_then_uses_the_answer() -> None:
    record = replace(STAY, channel=None, source_code="LEGACY-IMPORT")
    result = evaluate(record)
    assert (result.status, result.action, result.detail) == (
        Eligibility.INSUFFICIENT_EVIDENCE,
        NextAction.REQUEST_INFO,
        "booking_channel",
    )
    assert evaluate(record, member_stated_channel="direct").action is NextAction.ADJUST


def test_an_ota_booking_earns_only_with_the_member_number_on_the_booking() -> None:
    ota = replace(STAY, channel="ota", source_code="OTA-FEED")
    assert evaluate(ota).action is NextAction.ADJUST
    denied = evaluate(replace(ota, member_on_booking=False))
    assert (
        denied.detail == "channel_ineligible" and str(denied.reasons[0].policy_ref) == "missing-points-requests@v2#4.2"
    )


def test_ota_rule_does_not_reach_back_to_policy_v1() -> None:
    ota = replace(STAY, channel="ota", checkout_at_utc="2026-06-01T16:00:00Z")
    result = evaluate(ota, received_at_utc="2026-08-01T12:00:00Z", as_of_utc="2026-08-01T12:00:00Z")
    assert (
        result.detail == "channel_ineligible" and str(result.reasons[0].policy_ref) == "missing-points-requests@v1#4.1"
    )


def test_a_corporate_rate_code_earns_on_a_travel_agent_booking() -> None:
    agent = replace(STAY, channel="travel_agent", source_code="GDS-TA", rate_code="BAR")
    assert evaluate(agent).detail == "channel_ineligible"
    assert evaluate(replace(agent, rate_code="CORP-22")).action is NextAction.ADJUST


# ---------- other profiles ----------


def test_points_on_the_members_other_profile_mean_no_adjustment() -> None:
    other = posting(EARNED, member="GR-00002")
    result = evaluate(ledger=(other,), duplicate_profiles=("GR-00002",))
    assert (result.action, result.detail) == (NextAction.NO_ADJUSTMENT_CREDITED, "credited_other_profile")
    assert result.existing_credit is ExistingCredit.CREDITED_OTHER_PROFILE


def test_points_on_a_merged_number_count_as_credited() -> None:
    merged = posting(EARNED, member="GR-00009")
    assert evaluate(ledger=(merged,)).action is NextAction.ADJUST
    assert evaluate(ledger=(merged,), merged_profiles=("GR-00009",)).action is NextAction.NO_ADJUSTMENT_CREDITED


# ---------- the two clocks ----------

QUEUED = PendingPosting("Q1", MEMBER, "BR-1000", EARNED, "2026-08-20T00:00:00Z", "2026-09-05T12:00:00Z", "L-9")


def test_a_pending_posting_blocks_the_adjustment_under_v2() -> None:
    result = evaluate(postings=(QUEUED,))
    assert (result.status, result.action, result.detail) == (
        Eligibility.ELIGIBLE,
        NextAction.NO_ADJUSTMENT_PENDING,
        "2026-09-05",
    )
    assert result.existing_credit is ExistingCredit.PENDING_POSTING


def test_a_pending_posting_does_not_block_under_v1_which_has_no_such_rule() -> None:
    old = replace(STAY, checkout_at_utc="2026-06-01T16:00:00Z")
    assert evaluate(old, received_at_utc=ON_TIME, as_of_utc=ON_TIME, postings=(QUEUED,)).action is NextAction.ADJUST


def test_a_queue_item_outside_the_as_of_time_does_not_block() -> None:
    assert evaluate(postings=(QUEUED,), as_of_utc="2026-08-19T00:00:00Z", received_at_utc=ON_TIME).action is (
        NextAction.ADJUST
    )


def test_a_later_as_of_time_sees_a_posting_that_landed_after_approval() -> None:
    landed = posting(EARNED, "2026-09-10T00:00:00Z")
    assert evaluate(ledger=(landed,)).action is NextAction.ADJUST
    recheck = evaluate(ledger=(landed,), as_of_utc="2026-09-11T00:00:00Z")
    assert recheck.action is NextAction.NO_ADJUSTMENT_CREDITED


def test_a_later_as_of_time_does_not_change_whether_the_claim_was_on_time() -> None:
    received = "2026-09-01T12:00:00Z"
    recheck = evaluate(received_at_utc=received, as_of_utc="2028-01-01T00:00:00Z")
    assert recheck.action is NextAction.ADJUST


def test_stale_evidence_must_be_read_again() -> None:
    fresh = evaluate(evidence_read_at_utc="2026-09-01T11:00:00Z")
    assert fresh.action is NextAction.ADJUST
    stale = evaluate(evidence_read_at_utc="2026-09-01T10:59:59Z")
    assert (stale.status, stale.action, stale.detail) == (
        Eligibility.INSUFFICIENT_EVIDENCE,
        NextAction.REFRESH_EVIDENCE,
        "stale_evidence",
    )


# ---------- what the engine refuses to decide ----------


def test_a_missing_stay_record_escalates() -> None:
    result = evaluate_stay(StayClaim("BR-1", MEMBER, (), (), (), ON_TIME, ON_TIME), POLICIES, CUSTOMER)
    assert (result.status, result.action, result.detail) == (
        Eligibility.NEEDS_ESCALATION,
        NextAction.ESCALATE,
        "missing_stay_record",
    )
    assert result.existing_credit is ExistingCredit.UNKNOWN and result.points_owed == 0


@pytest.mark.parametrize(
    "other",
    [
        {"room_revenue_cents": 1},
        {"checkout_at_utc": "2026-08-02T16:00:00Z"},
        {"arrival_date": "2026-07-29"},
        {"member_number": "GR-00002"},
        {"channel": "ota"},
    ],
)
def test_conflicting_records_escalate(other: dict[str, object]) -> None:
    result = evaluate(records=(STAY, replace(STAY, record_id="R2", **other)))  # type: ignore[arg-type]
    assert (result.action, result.detail) == (NextAction.ESCALATE, "conflicting_records")


def test_identical_duplicate_records_do_not_escalate() -> None:
    assert evaluate(records=(STAY, replace(STAY, record_id="R2"))).action is NextAction.ADJUST


def test_no_policy_in_force_escalates_rather_than_inventing_one() -> None:
    before_any = replace(STAY, checkout_at_utc="2024-06-01T16:00:00Z")
    result = evaluate(before_any)
    assert (result.action, result.detail) == (NextAction.ESCALATE, "no_policy")
    assert evaluate_stay(claim(), (), CUSTOMER).detail == "no_policy"


def test_a_draft_policy_is_never_applied() -> None:
    drafts = tuple(replace(v, status="draft") for v in POLICIES)
    assert evaluate_stay(claim(), drafts, CUSTOMER).detail == "no_policy"


def test_two_policies_in_force_escalate_with_both_cited() -> None:
    v2 = next(v for v in POLICIES if v.policy_id == "missing-points-requests" and v.version == 2)
    overlapping = (*POLICIES, replace(v2, version=3))
    result = evaluate_stay(claim(), overlapping, CUSTOMER)
    assert (result.action, result.detail) == (NextAction.ESCALATE, "conflicting_policies")
    assert {str(r) for r in result.policy_refs} >= {"missing-points-requests@v2", "missing-points-requests@v3"}


def test_an_unconfigured_property_escalates() -> None:
    assert evaluate(replace(STAY, property="nowhere")).detail == "unknown_property"


# ---------- the case-level verdict ----------


def test_case_verdict_prefers_escalation_and_adds_up_the_points() -> None:
    adjust = evaluate()
    missing = evaluate_stay(StayClaim("BR-1", MEMBER, (), (), (), ON_TIME, ON_TIME), POLICIES, CUSTOMER)
    assert combine((adjust, missing)).action is NextAction.ESCALATE
    both = combine((adjust, replace(adjust, stay_id="BR-2")))
    assert (both.action, both.points_owed) == (NextAction.ADJUST, 2 * EARNED)


def test_over_the_supervisor_limit_escalates_per_case() -> None:
    within = evaluate(replace(STAY, room_revenue_cents=200_000))
    assert combine((within,)).action is NextAction.ADJUST
    over = evaluate(replace(STAY, room_revenue_cents=200_010))
    assert (combine((over,)).action, combine((over,)).detail) == (NextAction.ESCALATE, "over_supervisor_limit")
    assert combine((within, replace(within, stay_id="BR-2"))).detail == "over_supervisor_limit"


def test_case_verdict_needs_a_stay() -> None:
    with pytest.raises(ValueError, match="at least one"):
        combine(())


# ---------- policy documents ----------


def test_every_policy_file_parses_and_lists_its_real_sections() -> None:
    assert {(v.policy_id, v.version) for v in POLICIES} == {
        ("missing-points-requests", 1),
        ("missing-points-requests", 2),
        ("guest-rewards-earning", 1),
        ("guest-rewards-earning", 2),
    }
    doc = parse_document((ROOT / "policies/hg-demo/missing-points-requests-v2.md").read_text(encoding="utf-8"))
    by_id = {s.section_id: s for s in doc.sections}
    assert by_id["7.3"].heading == "Corporate travel program" and "CORP" in by_id["7.3"].text
    assert by_id["5.1"].heading == "Pending postings"
    assert len(doc.checksum) == 64


def test_versions_in_force_on_the_change_over_days() -> None:
    def on(day: date) -> list[int]:
        return [v.version for v in versions_in_force(POLICIES, "missing-points-requests", day)]

    assert on(date(2024, 12, 31)) == [] and on(date(2025, 1, 1)) == [1]
    assert on(date(2026, 6, 30)) == [1] and on(date(2026, 7, 1)) == [2]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("no front matter here", "no front matter"),
        ("---\n- a list\n---\nbody", "not a mapping"),
        ("---\npolicy_id: x\n---\nbody", "missing"),
        (
            "---\npolicy_id: x\ntitle: t\ncustomer: c\nversion: 1\neffective_from: 2026-01-01\nstatus: draft\n"
            'sections: ["1", "2"]\n---\n## 1. One\ntext\n',
            "lists sections",
        ),
        (
            "---\npolicy_id: x\ntitle: t\ncustomer: c\nversion: 1\neffective_from: soon\nstatus: draft\n"
            'sections: ["1"]\n---\n## 1. One\ntext\n',
            "not a date",
        ),
    ],
)
def test_a_malformed_policy_is_refused(text: str, message: str) -> None:
    with pytest.raises(PolicyFormatError, match=message):
        parse_document(text)


# ---------- boundaries ----------


def _imports(path: str) -> set[str]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    return names | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}


@pytest.mark.parametrize("path", ["app/domain/eligibility.py", "app/domain/policy.py", "app/domain/business_time.py"])
def test_the_engine_is_pure_and_apart_from_the_labeler(path: str) -> None:
    top = {name.split(".")[0] for name in _imports(path)}
    assert not top & {"fastapi", "sqlalchemy", "httpx", "anthropic", "openai", "evaluations", "seed_data", "benchmarks"}


def test_the_labeler_imports_nothing_from_the_app() -> None:
    assert not [n for n in _imports("evaluations/labeler.py") if n.split(".")[0] in {"app", "seed_data"}]


def test_customer_config_has_the_windows_the_write_path_needs() -> None:
    config = CustomerConfig.load("hg-demo")
    assert config.approval_ttl_hours == 24 and config.policy_set == "policies/hg-demo"
    assert CustomerRules(CUSTOMER.property_timezones, CUSTOMER.source_code_channels, 60) == CUSTOMER
