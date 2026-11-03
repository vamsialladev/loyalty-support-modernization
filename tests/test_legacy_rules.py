"""Arm A's legacy rules checklist, keyword index and intake routing: one test per pre-registered behaviour.

Each test names the defect (docs/legacy-defect-catalog.md) or control case it pins down. Arm A must be wrong in
exactly these ways and right everywhere else (spec B.8: realistic, never incompetent).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from app.arms.legacy import intake
from app.arms.legacy.checklist import Evidence, LedgerView, Outcome, add_months, evaluate
from app.arms.legacy.keyword_index import KeywordIndex
from app.arms.legacy.rules import LegacyRules
from app.domain.customer_records import LedgerEntry, Member, StayRecord
from scripts import build_legacy_index
from tests.conftest import ROOT

RULES = LegacyRules.load("hg-demo")
MEMBER = Member("GR-10001", "Clara", "Kowalski", "clara@example.com", "+15550100", "Silver", "active")
STAY = StayRecord(
    record_id="R-1",
    stay_id="BR-1001",
    property="beach-resort",
    member_on_booking=True,
    arrival_date="2026-03-01",
    nights=4,
    checkout_at_utc="2026-03-05T15:00:00Z",
    status="checked_out",
    source_code="WEB",
    rate_code="BAR",
    room_revenue_cents=148_400,
    member_number="GR-10001",
    channel="direct",
)
CLAIM = "2026-04-20T12:00:00Z"


def entry(points: int, stay_id: str | None = "BR-1001", kind: str = "posting") -> LedgerEntry:
    return LedgerEntry(f"L-{kind}-{points}", "GR-10001", kind, points, "2026-03-08T10:00:00Z", stay_id)


def ledger(*entries: LedgerEntry, start: str | None = None, as_of: str = CLAIM) -> LedgerView:
    return LedgerView("GR-10001", as_of, start, tuple(entries))


def full(stay: StayRecord = STAY, view: LedgerView | None = None) -> Evidence:
    return Evidence(MEMBER, stay, view or ledger(), ("missing-points-requests#3",))


def outcome(evidence: Evidence, claim: str = CLAIM) -> Outcome:
    return evaluate(evidence, claim, RULES).outcome


# ---------- controls: legacy is already right (K01-K06) ----------


def test_k01_eligible_missing_points_are_computed_from_room_revenue_only() -> None:
    result = evaluate(full(), CLAIM, RULES)
    assert result.outcome is Outcome.ADJUST
    assert result.earned_points == 14_840 and result.points_owed == 14_840  # floor($1,484.00 x 10)


def test_partial_credit_owes_only_the_difference() -> None:
    result = evaluate(full(view=ledger(entry(10_000))), CLAIM, RULES)
    assert result.outcome is Outcome.ADJUST and result.points_owed == 4_840


def test_k02_already_credited() -> None:
    assert outcome(full(view=ledger(entry(14_840)))) is Outcome.ALREADY_CREDITED


def test_k03_ota_without_member_number_is_denied() -> None:
    assert outcome(full(replace(STAY, channel="ota", member_on_booking=False))) is Outcome.DENY_CHANNEL


def test_k04_within_the_waiting_period_gives_the_date() -> None:
    result = evaluate(full(), "2026-03-20T12:00:00Z", RULES)  # the March configuration: 30 days
    assert result.outcome is Outcome.WAIT and result.wait_until == "2026-04-04"


def test_k05_not_checked_out() -> None:
    assert outcome(full(replace(STAY, status="in_house"))) is Outcome.NOT_CHECKED_OUT


def test_k06_claim_after_twelve_months_is_denied() -> None:
    assert outcome(full(), "2027-03-06T12:00:00Z") is Outcome.DENY_CLAIM_WINDOW
    assert outcome(full(), "2027-03-05T12:00:00Z") is not Outcome.DENY_CLAIM_WINDOW
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_over_the_supervisor_limit_must_escalate() -> None:
    result = evaluate(full(replace(STAY, room_revenue_cents=250_000)), CLAIM, RULES)
    assert result.outcome is Outcome.ESCALATE_OVER_LIMIT and result.points_owed == 25_000


@pytest.mark.parametrize("missing", ["member", "stay", "ledger", "policy_refs"])
def test_every_kind_of_evidence_must_be_attached_by_hand(missing: str) -> None:
    evidence = replace(full(), **{missing: () if missing == "policy_refs" else None})
    result = evaluate(evidence, CLAIM, RULES)
    assert result.outcome is Outcome.INCOMPLETE and result.points_owed is None


def test_a_stay_from_another_profile_is_not_accepted() -> None:
    assert outcome(full(replace(STAY, member_number="GR-99999"))) is Outcome.INCOMPLETE


def test_ledger_view_must_cover_the_checkout_date_adr_0050() -> None:
    """The 90-day window costs steps, never accuracy: a view that starts after checkout blocks the checklist."""
    assert outcome(full(view=ledger(start="2026-03-10T00:00:00Z"))) is Outcome.INCOMPLETE
    assert outcome(full(view=ledger(start="2026-01-20T00:00:00Z"))) is Outcome.ADJUST


# ---------- the configuration defects ----------


def test_d03_blank_booking_channel_is_treated_as_ineligible() -> None:
    result = evaluate(full(replace(STAY, channel=None, source_code="WEB")), CLAIM, RULES)  # WEB implies direct
    assert result.outcome is Outcome.DENY_CHANNEL and "blank" in result.lines[-1].detail


def test_d04_dates_are_compared_in_utc_not_eastern() -> None:
    # Checkout 2026-08-01 21:30 Eastern = 2026-08-02 01:30 UTC. 14-day wait: Eastern says claimable 2026-08-15.
    late = replace(STAY, checkout_at_utc="2026-08-02T01:30:00Z", arrival_date="2026-07-28")
    result = evaluate(full(late, ledger(as_of="2026-08-15T14:00:00Z")), "2026-08-15T14:00:00Z", RULES)
    assert result.outcome is Outcome.WAIT and result.wait_until == "2026-08-16"


def test_d08_mountain_lodge_still_waits_thirty_days_after_july() -> None:
    view = ledger(as_of="2026-08-20T12:00:00Z")
    lodge = replace(STAY, stay_id="ML-1001", property="mountain-lodge", checkout_at_utc="2026-08-01T15:00:00Z")
    lodge_result = evaluate(full(lodge, view), "2026-08-20T12:00:00Z", RULES)
    assert lodge_result.outcome is Outcome.WAIT and lodge_result.wait_until == "2026-08-31"
    beach = replace(STAY, checkout_at_utc="2026-08-01T15:00:00Z")
    assert outcome(full(beach, view), "2026-08-20T12:00:00Z") is Outcome.ADJUST


def test_d09_ota_with_member_number_is_still_denied_after_july() -> None:
    ota = replace(STAY, channel="ota", member_on_booking=True, checkout_at_utc="2026-08-01T15:00:00Z")
    assert outcome(full(ota, ledger(as_of="2026-09-01T12:00:00Z")), "2026-09-01T12:00:00Z") is Outcome.DENY_CHANNEL


def test_d21_corporate_travel_agent_rate_is_denied() -> None:
    corp = replace(STAY, channel="travel_agent", rate_code="CORP-ACME", checkout_at_utc="2026-08-01T15:00:00Z")
    assert outcome(full(corp, ledger(as_of="2026-09-01T12:00:00Z")), "2026-09-01T12:00:00Z") is Outcome.DENY_CHANNEL


def test_d15_current_rules_apply_whatever_the_stay_date() -> None:
    # Checkout 2026-06-26: policy v1 applies (30 days, claimable 2026-07-26). Claimed 2026-07-12, legacy uses the
    # July configuration (14 days at Beach Resort) and credits early.
    june = replace(STAY, checkout_at_utc="2026-06-26T15:00:00Z", arrival_date="2026-06-22")
    result = evaluate(full(june, ledger(as_of="2026-07-12T12:00:00Z")), "2026-07-12T12:00:00Z", RULES)
    assert result.outcome is Outcome.ADJUST and "2026-07-01" in (result.rules_revision or "")


def test_d07_a_repost_shown_without_its_stay_looks_missing() -> None:
    """The legacy ledger screen lists a re-post without its confirmation number (screens.ledger_view), so the
    checklist nets posting - reversal = 0 for the stay and offers an adjustment: the pre-registered over-credit."""
    entries = (entry(14_840), entry(-14_840, kind="reversal"), entry(15_000, stay_id=None, kind="repost"))
    result = evaluate(full(view=ledger(*entries)), CLAIM, RULES)
    assert result.outcome is Outcome.ADJUST and result.credited_points == 0


# ---------- keyword index and routing ----------


def test_index_holds_only_the_policies_in_force_on_2026_03_15_d09() -> None:
    index = KeywordIndex.load()
    assert index.built_as_of == "2026-03-15"
    refs = {s.ref for s in index.sections}
    assert "missing-points-requests#4.1" in refs
    assert not any(ref.endswith(("#4.2", "#5.1", "#7.3")) for ref in refs), "v2-only sections leaked into the index"


def test_committed_index_matches_a_rebuild() -> None:
    assert build_legacy_index.main(["--check"]) == 0


def test_keyword_search_is_exact_term_d12() -> None:
    index = KeywordIndex.load()
    assert [s.ref for s in index.search("missing points")][:1] == ["missing-points-requests#1"]
    for paraphrase in ("didn't get my points", "retro credit", "stay not counted"):
        assert index.search(paraphrase) == [], paraphrase
    assert index.search("") == []


def test_d20_any_mention_of_a_refund_goes_to_billing() -> None:
    assert intake.route("My points are missing. Also I want a REFUND for the noise.") == intake.BILLING_QUEUE
    assert intake.route("My points from the Beach Resort stay are missing.") == intake.POINTS_QUEUE


def test_rules_file_documents_every_deliberate_deviation() -> None:
    text = (ROOT / "config/legacy/hg-demo-legacy-rules.yaml").read_text(encoding="utf-8")
    for defect in ("D03", "D04", "D08", "D09", "D15", "D21"):
        assert defect in text, defect
    assert RULES.revision_on(date(2026, 7, 1)).waiting_period_days == {"beach-resort": 14, "mountain-lodge": 30}
    assert RULES.revision_on(date(2026, 6, 30)).waiting_period_days == {"beach-resort": 30, "mountain-lodge": 30}
