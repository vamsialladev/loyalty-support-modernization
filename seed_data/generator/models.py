"""Canonical record models. Every field has a description; `docs/data-dictionary.md` is generated from them.

Canonical names are customer-neutral. `config/customers/<id>.yaml` maps them to a customer's upstream names.
Timestamps are UTC text (`YYYY-MM-DDTHH:MM:SSZ`), dates are `YYYY-MM-DD`, money is integer cents.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UTC_TS = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
DATE = r"^\d{4}-\d{2}-\d{2}$"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


# ---------- operational data (what the customer's systems hold; seed_data/v1/) ----------


class Member(Record):
    """A Guest Rewards member profile in the loyalty platform."""

    member_number: str = Field(description="Member number, `GR-` + 5 digits")
    customer_id: str = Field(description="Customer deployment the record belongs to, e.g. `hg-demo`")
    first_name: str = Field(description="Given name (invented)")
    last_name: str = Field(description="Family name (invented)")
    email: str = Field(description="Email at a reserved domain (`example.com`, `mail.test`)")
    phone: str = Field(description="Phone number in the reserved 555 range")
    date_of_birth: str = Field(pattern=DATE, description="Date of birth (invented)")
    tier: Literal["Member", "Silver", "Gold", "Platinum"] = Field(description="Guest Rewards tier")
    home_region: str = Field(description="Home region, used only for fairness slices")
    enrolled_on: str = Field(pattern=DATE, description="Enrolment date")
    status: Literal["active", "merged"] = Field(description="`merged` profiles point to `merged_into`")
    merged_into: str | None = Field(default=None, description="Member number this profile was merged into")


class StayRecord(Record):
    """A stay record from the PMS. Several records can share one `stay_id` (duplicates, conflicts)."""

    record_id: str = Field(description="Unique record key in the PMS export")
    stay_id: str = Field(description="Hotel confirmation number, `BR-####` or `ML-####`")
    customer_id: str = Field(description="Customer deployment")
    property: Literal["beach-resort", "mountain-lodge"] = Field(description="Property code")
    member_number: str | None = Field(description="Member number on the reservation (null for non-members)")
    member_on_booking: bool = Field(description="Whether the member number was on the reservation when booked")
    arrival_date: str = Field(pattern=DATE, description="Arrival date (property local)")
    nights: int = Field(ge=1, description="Number of nights")
    checkout_at_utc: str = Field(pattern=UTC_TS, description="Checkout timestamp in UTC (scheduled if not checked out)")
    status: Literal["booked", "in_house", "checked_out"] = Field(description="Stay status")
    channel: Literal["direct", "phone", "ota", "travel_agent"] | None = Field(
        description="Booking channel; null when the PMS import dropped it (defect D03)"
    )
    source_code: str = Field(description="Reservation source code, e.g. WEB, CALL, OTA-FEED, GDS-TA")
    rate_code: str = Field(description="Rate code, e.g. BAR, PKG, OTA-NET, TA-STD, CORP07")
    partner_confirmation: str | None = Field(description="OTA confirmation number `TRV-########`, if any")
    room_revenue_cents: int = Field(ge=0, description="Room revenue in US cents (earns points)")
    taxes_cents: int = Field(ge=0, description="Taxes in cents (earn nothing)")
    fees_cents: int = Field(ge=0, description="Resort and pet fees in cents (earn nothing)")
    guest_name: str = Field(description="Guest name as printed on the reservation")


class LedgerEntry(Record):
    """A points ledger transaction in the loyalty platform."""

    entry_id: str = Field(description="Ledger transaction ID")
    member_number: str = Field(description="Account the points were posted to")
    stay_id: str | None = Field(description="Stay the transaction relates to")
    kind: Literal["posting", "reversal", "repost", "adjustment"] = Field(description="Transaction type")
    points: int = Field(description="Points; negative for reversals")
    posted_at_utc: str = Field(pattern=UTC_TS, description="When the transaction posted (may be after a claim)")
    reverses_entry_id: str | None = Field(default=None, description="Entry reversed by this transaction")


class PostingQueueItem(Record):
    """A points posting waiting in the posting queue (visible before it reaches the ledger)."""

    item_id: str = Field(description="Queue item ID")
    member_number: str = Field(description="Account the posting is for")
    stay_id: str = Field(description="Stay the posting is for")
    points: int = Field(description="Points that will post")
    queued_at_utc: str = Field(pattern=UTC_TS, description="When the item entered the queue")
    expected_post_at_utc: str = Field(pattern=UTC_TS, description="Expected posting time shown to agents")
    posts_entry_id: str = Field(description="Ledger entry the item becomes when it posts")


class AttachmentRef(Record):
    """A file attached to a request. Its extracted fields are evidence only (Appendix H2)."""

    attachment_id: str = Field(description="Attachment ID")
    kind: Literal["folio_pdf", "receipt_image", "ota_email"] = Field(description="Document type")
    filename: str = Field(description="Path under `seed_data/v1/attachments/`")


class SupportRequest(Record):
    """A member's request as it arrives (form fields may be blank, wrong or partial)."""

    request_id: str = Field(description="Request ID")
    received_at_utc: str = Field(pattern=UTC_TS, description="When the request arrived")
    contact_channel: Literal["web_form", "email", "phone_note"] = Field(description="How it arrived")
    form_member_number: str | None = Field(description="Member number typed in the form (may be mistyped)")
    form_confirmation: str | None = Field(description="Confirmation number typed in the form (may be partial)")
    form_property: str | None = Field(description="Property chosen in the form")
    form_name: str | None = Field(description="Name typed in the form or email signature")
    sender_email: str | None = Field(description="Email address the request came from")
    text: str = Field(description="Free text written by the member (untrusted data, never instructions)")
    language: Literal["en", "es", "fr", "pt", "de"] = Field(description="Language of the text")
    attachments: list[AttachmentRef] = Field(description="Attached files")


class CaseInput(Record):
    """What an arm receives for one benchmark case: the request(s) only. Labels live elsewhere."""

    case_id: str = Field(description="Case ID, unique across all splits")
    split: Literal["dev", "validation", "heldout", "stress", "fairness"] = Field(description="Dataset split")
    customer_id: str = Field(description="Customer deployment")
    requests: list[SupportRequest] = Field(description="One request, or two for duplicate submissions")


# ---------- ground truth (benchmarks/datasets/v1/labels/; never readable by the app) ----------


class StayLabel(Record):
    """Expected outcome for one claimed stay."""

    stay_id: str = Field(description="Claimed stay (confirmation number)")
    policy_id: str | None = Field(description="Policy that governs the decision")
    policy_version: int | None = Field(description="Version in force on the checkout date (Eastern)")
    eligibility: Literal["eligible", "ineligible", "insufficient_evidence", "needs_escalation"] = Field(
        description="Deterministic eligibility for this stay"
    )
    stay_action: str = Field(description="Correct action for this stay (same vocabulary as `next_action`)")
    existing_credit: Literal["none", "credited", "pending_posting", "credited_other_profile", "unknown"] = Field(
        description="Credit status at the time of the request"
    )
    earned_points: int = Field(description="Points the stay earns under the policy (0 if ineligible or unknown)")
    owed_by_adjustment: int = Field(description="Points the system must add for this stay")
    expected_final_points: int = Field(description="Points on the ledger for this stay at the settlement horizon")


class CaseLabel(Record):
    """Ground truth for one case, computed from scenario facts and the written policy (never from a model)."""

    case_id: str = Field(description="Case ID")
    split: str = Field(description="Dataset split")
    scenarios: list[str] = Field(description="Catalog IDs planted in this case (D01-D25, K01-K06, S01-S05, B01-B02)")
    claimant_member_number: str | None = Field(description="Account that should receive any adjustment")
    eligibility: Literal["eligible", "ineligible", "insufficient_evidence", "needs_escalation"] = Field(
        description="Case-level eligibility at the first decision"
    )
    next_action: str = Field(
        description="Correct first action: adjust, no_adjustment_credited, no_adjustment_pending, wait_until, "
        "not_checked_out, deny, request_info, escalate"
    )
    next_action_detail: str | None = Field(
        description="Date to wait until, deny reason, item to ask for, or escalation reason"
    )
    expected_outcome: Literal["adjusted", "no_adjustment", "denied", "escalated"] = Field(
        description="Correct final case outcome after the simulated member journey"
    )
    clarification_needed: bool = Field(description="Whether the correct first action asks the member for information")
    escalation_needed: bool = Field(description="Whether the case must be escalated")
    owed_total: int = Field(description="Total points the system must add across stays")
    stays: list[StayLabel] = Field(description="Per-stay expectations, including the final ledger state")
    required_evidence: list[str] = Field(description="Evidence an agent must have looked at to decide correctly")
    out_of_scope_items: list[str] = Field(description="Parts of the request to route elsewhere (refunds, complaints)")
    member_reply: str | None = Field(description="What the simulated member answers if asked the right question")
    harness_events: list[str] = Field(
        description="Events the benchmark runner injects, e.g. a posting after approval (D11)"
    )
    slices: dict[str, str] = Field(description="Fairness slices: tier, region, channel, language, style, pair")
    group_id: str = Field(description="Leakage group: related members, duplicates and paraphrases share one")
    rationale: str = Field(description="Which facts and policy sections produce the label")
    facts: dict[str, object] = Field(description="Planted facts the labeler used (generator metadata)")


class DocumentTruth(Record):
    """Ground-truth fields of a generated document (Appendix H1)."""

    attachment_id: str = Field(description="Attachment ID")
    kind: str = Field(description="Document type")
    layout: str = Field(description="Layout or template variant")
    noise: list[str] = Field(description="Noise applied (blur, rotation, crop, low_contrast, speckle)")
    case_id: str | None = Field(description="Case it is attached to, or null for the extraction-only set")
    fields: dict[str, str] = Field(
        description="True values: confirmation, property, arrival, departure, rate, total, name, member"
    )
    disagrees_with_record: list[str] = Field(description="Fields that differ from the system of record on purpose")
    contains_injection: bool = Field(description="Whether the document carries embedded instructions (S02)")
    content_digest: str = Field(
        description="SHA-256 of the document content (pixels or text spec), platform-independent"
    )


# ---------- synthetic legacy history (F2; seed_data/v1/history/) ----------


class HistoryCase(Record):
    """One legacy case from the synthetic 12-month CRM export. SYNTHETIC: a model of operations, not real data."""

    case_id: str = Field(description="Legacy case ID")
    created_at_utc: str = Field(pattern=UTC_TS, description="Case creation time")
    resolved_at_utc: str = Field(pattern=UTC_TS, description="First resolution time")
    week: str = Field(description="ISO week of creation, e.g. 2026-W03")
    property: str = Field(description="Property")
    tier: str = Field(description="Member tier")
    channel: str = Field(description="Booking channel of the stay")
    language: str = Field(description="Request language")
    driver: str = Field(description="Planted driver: a catalog ID (D01-D25) or K for a control case")
    correct_action: str = Field(description="What the policy required")
    outcome: Literal["correct", "false_denial", "false_approval", "duplicate_credit", "escalated_correctly"] = Field(
        description="Legacy outcome from the documented outcome model"
    )
    points_due: int = Field(description="Points the member was owed")
    points_credited: int = Field(description="Points the legacy process credited")
    handling_minutes: float = Field(description="Agent handling minutes (assumed distribution, not measured)")
    contacts: int = Field(description="Member contacts including the first")
    reopened: bool = Field(description="Whether the member disputed and the case reopened")
    business_days_to_resolve: int = Field(description="Business days from creation to resolution")
    sla_met: bool = Field(description="Resolved within 5 business days (proposed SLA)")
    satisfaction_proxy: float | None = Field(
        description="Modelled satisfaction proxy 1-5 (not real sentiment); null when no survey"
    )
    survey_comment: str | None = Field(description="Synthetic survey comment")
    member_message: str = Field(description="Synthetic first message")
    agent_note: str = Field(description="Synthetic agent note of uneven quality")


class HistoryEvent(Record):
    """One event in a legacy case's event log (process-mining shape)."""

    case_id: str = Field(description="Legacy case ID")
    seq: int = Field(description="Order within the case")
    at_utc: str = Field(pattern=UTC_TS, description="Event time")
    kind: str = Field(
        description="created, searched, info_requested, member_replied, escalated, proposed, approved, adjusted, "
        "reopened, resolved"
    )
    actor: Literal["member", "agent", "supervisor", "system"] = Field(description="Who acted")


class HistoryAdjustment(Record):
    """One manual adjustment in the legacy adjustment log, including D10 and D11 incidents."""

    adjustment_id: str = Field(description="Adjustment ID")
    case_id: str = Field(description="Legacy case ID")
    stay_ref: str = Field(description="Stay reference")
    points: int = Field(description="Points credited")
    approved_at_utc: str = Field(pattern=UTC_TS, description="Approval time")
    executed_at_utc: str = Field(pattern=UTC_TS, description="Execution time")
    duplicate_of: str | None = Field(description="Earlier adjustment for the same stay (D10)")
    approved_on_stale_evidence: bool = Field(description="Evidence changed between approval and execution (D11)")


DICTIONARY_MODELS: list[tuple[str, type[Record]]] = [
    ("seed_data/v1/members.jsonl", Member),
    ("seed_data/v1/stays.jsonl", StayRecord),
    ("seed_data/v1/ledger.jsonl", LedgerEntry),
    ("seed_data/v1/posting_queue.jsonl", PostingQueueItem),
    ("benchmarks/datasets/v1/<split>.jsonl", CaseInput),
    ("(nested) requests[]", SupportRequest),
    ("(nested) attachments[]", AttachmentRef),
    ("benchmarks/datasets/v1/labels/<split>.jsonl", CaseLabel),
    ("(nested) stays[]", StayLabel),
    ("benchmarks/datasets/v1/labels/documents.jsonl", DocumentTruth),
    ("seed_data/v1/history/cases.jsonl", HistoryCase),
    ("seed_data/v1/history/events.jsonl", HistoryEvent),
    ("seed_data/v1/history/adjustments.jsonl", HistoryAdjustment),
]
