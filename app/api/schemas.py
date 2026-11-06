"""Request and response shapes. Requests refuse unknown fields, so `points` in a body is an error, never ignored."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

UTC_TIME = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseCreate(Strict):
    received_at_utc: str = Field(pattern=UTC_TIME)
    contact_channel: Literal["phone_note", "email", "web_form"]
    text: str = Field(min_length=1, max_length=20000)
    arm: Literal["A", "B", "C"] = "B"
    sender_email: str | None = Field(default=None, max_length=255)
    form_member_number: str | None = Field(default=None, max_length=32)
    form_confirmation: str | None = Field(default=None, max_length=32)
    form_name: str | None = Field(default=None, max_length=120)


class InformationSupplied(Strict):
    reply_text: str = Field(default="", max_length=20000)
    booking_channel: Literal["", "direct", "phone", "ota", "travel_agent"] = ""
    member_number: str = Field(default="", max_length=32)
    confirmation: str = Field(default="", max_length=32)
    scope_cleared: bool = False


class Decision(Strict):
    decision: Literal["approve", "reject"]
    reason: str = Field(default="", max_length=2000)


class CloseCase(Strict):
    code: str = Field(max_length=48)
    reason: str = Field(default="", max_length=2000)


class FeedbackGiven(Strict):
    rating: Literal["helpful", "not_helpful"]
    comment: str = Field(default="", max_length=2000)


class WhoAmI(BaseModel):
    username: str
    display_name: str
    role: str
    csrf_token: str


class CaseOut(BaseModel):
    id: int
    reference: str
    arm: str
    queue: str
    status: str
    assigned_to: str | None
    received_at_utc: str
    resolution_code: str | None
    resolution_note: str | None
    group_ref: str | None
    version: int


class CasePage(BaseModel):
    items: list[CaseOut]
    next_cursor: str | None


class RequestOut(BaseModel):
    contact_channel: str
    received_at_utc: str
    sender_email: str | None
    form_member_number: str | None
    form_confirmation: str | None
    form_name: str | None
    text: str
    attachment_names: list[str]


class AdjustmentOut(BaseModel):
    id: int
    case_id: int
    member_number: str
    stay_id: str
    points: int
    status: str
    requested_by: str
    invalidated_reason: str | None
    approved_by: str | None
    decision: str | None
    upstream_adjustment_id: str | None
    attempts: list[str]


class CitationOut(BaseModel):
    policy_id: str
    version: int
    section_id: str
    title: str
    heading: str
    url: str


class RecommendationOut(BaseModel):
    id: int
    author: str
    member_number: str | None
    stay_id: str | None
    status: str
    action: str
    detail: str | None
    points_owed: int
    earned_points: int
    credited_points: int
    reasons: list[dict[str, Any]]
    citations: list[CitationOut]
    flags: list[str]
    created_at_utc: str
    ai: dict[str, Any] | None = None  # text a model wrote, on arm C. Everything above is the engine's


class CaseDetail(CaseOut):
    requests: list[RequestOut]
    evidence: dict[str, Any] | None
    recommendation: RecommendationOut | None
    adjustments: list[AdjustmentOut]
    investigation: Literal["none", "queued", "running", "failed"]
    missing_information: str | None


class InvestigationOut(BaseModel):
    job_id: int
    status: str


class ExecutionOut(BaseModel):
    status: str
    message: str


class DecisionOut(BaseModel):
    status: str
    message: str


class RequestedOut(BaseModel):
    status: str
    adjustment: AdjustmentOut | None


class ClosedOut(BaseModel):
    status: str
    override: bool


class AuditEvent(BaseModel):
    step: int
    actor: str
    actor_kind: str
    action: str
    detail: dict[str, Any]
    at_utc: str


class ExcerptOut(BaseModel):
    policy_id: str
    version: int
    section_id: str | None
    title: str
    heading: str
    text: str
    effective_from: str
    effective_to: str | None
    status: str
    source_checksum: str


class FeedbackOut(BaseModel):
    id: int
    kind: str
    rating: str | None


class ArmMetricsOut(BaseModel):
    arm: str
    kind: str
    cases: int
    by_status: dict[str, int]
    median_steps: float | None
    median_minutes_to_close: float | None
    adjustments_requested: int
    adjustments_executed: int
    points_executed: int
    approvals_invalidated: int
    overrides: int
    information_requests: int
    escalated: int
    investigations: int
    feedback_helpful: int
    feedback_not_helpful: int
    engine_results: dict[str, int]


class MetricsOut(BaseModel):
    rows: list[ArmMetricsOut]
    jobs_queued: int
    jobs_dead: int
    note: str
