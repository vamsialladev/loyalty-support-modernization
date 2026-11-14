"""`/api/v1`: the JSON API (spec B.11; API-01, API-02; ADR-0065).

Authentication is the console's server-side session. Every change needs the session's CSRF token in `X-CSRF-Token`.
Bearer tokens for other systems come with Milestone 9. Every check is in `app.services`, the ones the browser reaches.
Errors are `application/problem+json` (RFC 9457). Lists use an opaque cursor.
"""

from __future__ import annotations

import base64
import binascii
import logging
from collections.abc import Callable, Iterator
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas as api
from app.domain.case_states import InvalidTransition
from app.domain.roles import NotPermitted, require_case_reader
from app.persistence.models import AdjustmentRequestRow, Case, Recommendation
from app.ports.customer_systems import CustomerSystemError
from app.services import (
    accounts,
    conventional,
    jobs,
    metrics,
    policies,
    qa_sampling,
    rate_limit,
    security_events,
    sessions,
)
from app.services import cases as svc
from app.services.instrumentation import events, record_system
from app.services.systems import SystemsFactory
from app.services.write_path import SharedWritePath, approval_of, attempts_of, load_request
from app.settings import AppSettings

log = logging.getLogger(__name__)
PROBLEM = "application/problem+json"
SESSION_COOKIE = "lsm_session"
MAX_PAGE = 100


class Problem(Exception):
    def __init__(self, status_code: int, code: str, title: str, detail: str = "") -> None:
        super().__init__(title)
        self.status_code, self.code, self.title, self.detail = status_code, code, title, detail


def problem_response(status_code: int, code: str, title: str, detail: str = "") -> JSONResponse:
    body = {"type": f"about:blank#{code}", "title": title, "status": status_code, "code": code}
    if detail:
        body["detail"] = detail
    return JSONResponse(body, status_code=status_code, media_type=PROBLEM)


def _to_problem(exc: Exception) -> JSONResponse:
    if isinstance(exc, Problem):
        return problem_response(exc.status_code, exc.code, exc.title, exc.detail)
    if isinstance(exc, NotPermitted):
        return problem_response(403, "not_permitted", "Not permitted", str(exc))
    if isinstance(exc, svc.CaseNotFound):
        return problem_response(404, "not_found", "Not found", "There is no such case.")
    if isinstance(exc, svc.WorkflowError | InvalidTransition):
        return problem_response(409, "not_possible", "Not possible right now", str(exc))
    if isinstance(exc, RequestValidationError):
        fields = sorted({".".join(str(p) for p in err["loc"][1:]) or str(err["loc"][-1]) for err in exc.errors()})
        return problem_response(422, "invalid_request", "The request isn't valid", ", ".join(fields))
    if isinstance(exc, CustomerSystemError):
        return problem_response(502, "upstream", "Customer system error", exc.code or type(exc).__name__)
    if isinstance(exc, rate_limit.RateLimited):
        response = problem_response(429, "rate_limited", "Too many requests")
        response.headers["Retry-After"] = str(exc.retry_after_seconds)
        return response
    raise exc


class ProblemRoute(APIRoute):
    """Every failure in this router, including validation, comes back as a problem document, never as console HTML."""

    def get_route_handler(self) -> Callable[..., Any]:
        handler = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            try:
                return await handler(request)
            except (
                Problem,
                NotPermitted,
                svc.CaseNotFound,
                svc.WorkflowError,
                InvalidTransition,
                RequestValidationError,
                CustomerSystemError,
                rate_limit.RateLimited,
            ) as exc:
                return _to_problem(exc)

        return wrapped


def _encode_cursor(key: tuple[str, int]) -> str:
    return base64.urlsafe_b64encode(f"{key[0]}|{key[1]}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, int]:
    try:
        received, case_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
        return received, int(case_id)
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise Problem(400, "invalid_cursor", "The cursor isn't valid") from exc


def _case(case: Case) -> api.CaseOut:
    return api.CaseOut(
        id=case.id,
        reference=case.reference,
        arm=case.arm,
        queue=case.queue,
        status=case.status,
        assigned_to=case.assigned_to,
        received_at_utc=case.received_at_utc,
        resolution_code=case.resolution_code,
        resolution_note=case.resolution_note,
        group_ref=case.group_ref,
        version=case.version,
    )


def _adjustment(s: Session, row: AdjustmentRequestRow) -> api.AdjustmentOut:
    approval = approval_of(s, row)
    attempts = attempts_of(s, row)
    upstream = next((t.upstream_adjustment_id for t in reversed(attempts) if t.upstream_adjustment_id), None)
    return api.AdjustmentOut(
        id=row.id,
        case_id=row.case_id,
        member_number=row.member_number,
        stay_id=row.stay_id,
        points=row.points,
        status=row.status,
        requested_by=row.requested_by,
        invalidated_reason=row.invalidated_reason,
        approved_by=approval.decided_by if approval else None,
        decision=approval.decision if approval else None,
        upstream_adjustment_id=upstream,
        attempts=[t.outcome for t in attempts],
    )


def _recommendation(rec: Recommendation) -> api.RecommendationOut:
    citations = [
        api.CitationOut(**c, url=f"/api/v1/policies/{c['policy_id']}/v{c['version']}/{c['section_id']}")
        for c in rec.citations
    ]
    return api.RecommendationOut(
        id=rec.id,
        author=rec.author,
        member_number=rec.member_number,
        stay_id=rec.stay_id,
        status=rec.status,
        action=rec.action,
        detail=rec.detail,
        points_owed=rec.points_owed,
        earned_points=rec.earned_points,
        credited_points=rec.credited_points,
        reasons=rec.reasons,
        citations=citations,
        flags=rec.flags,
        created_at_utc=rec.created_at_utc,
        ai=rec.ai,
    )


def db(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as s:
        yield s


DB = Annotated[Session, Depends(db)]


def signed_in(request: Request, s: DB) -> sessions.ActiveSession:
    """A person's session, or a machine's read-only bearer token. A token carries no CSRF value, so it can't change
    anything."""
    active = sessions.resolve(s, request.app.state.identity, request.cookies.get(SESSION_COOKIE))
    if active is None:
        bearer = request.headers.get("authorization", "")
        token = bearer[7:].strip() if bearer.lower().startswith("bearer ") else None
        machine = accounts.identity_for_api_token(s, token)
        if machine is None:
            raise Problem(401, "not_signed_in", "Sign in first")
        active = sessions.ActiveSession(machine, "")
    rate_limit.hit(s, f"user:{active.identity.username}", request.app.state.rate_limit_per_minute, 60)
    return active


Reader = Annotated[sessions.ActiveSession, Depends(signed_in)]


def changing(
    request: Request, s: DB, active: Reader, x_csrf_token: Annotated[str, Header()] = ""
) -> sessions.ActiveSession:
    if not sessions.csrf_ok(active, x_csrf_token):
        # A security event (SEC-20): where, and by whom; never the request's content.
        record_system(s, active.identity, "csrf_failed", path=request.url.path[:120], method=request.method)
        s.commit()
        raise Problem(403, "csrf_failed", "The X-CSRF-Token header is missing or wrong")
    return active


Writer = Annotated[sessions.ActiveSession, Depends(changing)]


def build_router(settings: AppSettings, systems_for: SystemsFactory) -> APIRouter:
    router = APIRouter(prefix="/api/v1", route_class=ProblemRoute)
    write_path = SharedWritePath(settings.customer_id, secret_key=settings.secret_key or None)

    @router.get("/me", response_model=api.WhoAmI)
    def me(active: Reader) -> api.WhoAmI:
        who = active.identity
        return api.WhoAmI(
            username=who.username, display_name=who.display_name, role=who.role.value, csrf_token=active.csrf_token
        )

    @router.get("/cases", response_model=api.CasePage)
    def list_cases(
        s: DB,
        active: Reader,
        queue: Annotated[str | None, Query(max_length=16)] = None,
        case_status: Annotated[str | None, Query(alias="status", max_length=32)] = None,
        arm: Annotated[str | None, Query(pattern="^[ABC]$")] = None,
        cursor: str | None = None,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 50,
    ) -> api.CasePage:
        require_case_reader(active.identity)
        query = select(Case).where(Case.customer_id == active.identity.customer_id)
        if queue:
            query = query.where(Case.queue == queue)
        if case_status:
            query = query.where(Case.status == case_status)
        if arm:
            query = query.where(Case.arm == arm)
        if cursor:
            received, case_id = _decode_cursor(cursor)
            query = query.where(
                (Case.received_at_utc > received) | ((Case.received_at_utc == received) & (Case.id > case_id))
            )
        rows = list(s.scalars(query.order_by(Case.received_at_utc, Case.id).limit(limit + 1)))
        following = _encode_cursor((rows[limit - 1].received_at_utc, rows[limit - 1].id)) if len(rows) > limit else None
        return api.CasePage(items=[_case(c) for c in rows[:limit]], next_cursor=following)

    @router.post("/cases", response_model=api.CaseOut, status_code=status.HTTP_201_CREATED)
    def create_case(s: DB, active: Writer, body: api.CaseCreate) -> api.CaseOut:
        request = svc.IntakeRequest(
            received_at_utc=body.received_at_utc,
            contact_channel=body.contact_channel,
            text=body.text,
            sender_email=body.sender_email,
            form_member_number=body.form_member_number,
            form_confirmation=body.form_confirmation,
            form_name=body.form_name,
        )
        return _case(svc.create_case(s, active.identity, request, customer_id=settings.customer_id, arm=body.arm))

    def _investigation_state(s: Session, case: Case) -> str:
        job = jobs.active_job(s, jobs.dedupe_key(conventional.INVESTIGATE_JOB, case.id))
        if job is not None:
            return "running" if job.status == jobs.RUNNING else "queued"
        return "failed" if conventional.failed_investigation(s, case) else "none"

    @router.get("/cases/{case_id}", response_model=api.CaseDetail)
    def view_case(s: DB, active: Reader, case_id: int) -> api.CaseDetail:
        case = svc.get_case(s, active.identity, case_id)
        rec = conventional.latest_recommendation(s, case)
        requests = [
            api.RequestOut(
                contact_channel=r.contact_channel,
                received_at_utc=r.received_at_utc,
                sender_email=r.sender_email,
                form_member_number=r.form_member_number,
                form_confirmation=r.form_confirmation,
                form_name=r.form_name,
                text=r.text,
                attachment_names=list(r.attachment_names),
            )
            for r in svc.requests_of(s, case)
        ]
        return api.CaseDetail(
            **_case(case).model_dump(),
            requests=requests,
            evidence=conventional.latest_evidence(s, case),
            recommendation=_recommendation(rec) if rec else None,
            adjustments=[_adjustment(s, row) for row in svc.adjustment_requests_of(s, case)],
            investigation=_investigation_state(s, case),  # type: ignore[arg-type]
            missing_information=conventional.prompt_for(rec),
        )

    @router.post("/cases/{case_id}/investigation", response_model=api.InvestigationOut, status_code=202)
    def start_investigation(s: DB, active: Writer, case_id: int) -> api.InvestigationOut:
        """Starting it twice is safe: while one is queued or running, the same job comes back (API-02)."""
        case = svc.get_case(s, active.identity, case_id)
        job = conventional.start_investigation(s, active.identity, case)
        return api.InvestigationOut(job_id=job.id, status=job.status)

    @router.post("/cases/{case_id}/information", response_model=api.InvestigationOut, status_code=202)
    def supply_information(s: DB, active: Writer, case_id: int, body: api.InformationSupplied) -> api.InvestigationOut:
        case = svc.get_case(s, active.identity, case_id)
        job = conventional.supply_information(s, active.identity, case, **body.model_dump())
        return api.InvestigationOut(job_id=job.id, status=job.status)

    @router.get("/cases/{case_id}/recommendations", response_model=list[api.RecommendationOut])
    def recommendations(s: DB, active: Reader, case_id: int) -> list[api.RecommendationOut]:
        case = svc.get_case(s, active.identity, case_id)
        query = select(Recommendation).where(Recommendation.case_id == case.id).order_by(Recommendation.id)
        return [_recommendation(rec) for rec in s.scalars(query)]

    @router.post("/cases/{case_id}/adjustment-request", response_model=api.RequestedOut, status_code=201)
    def request_adjustment(s: DB, active: Writer, case_id: int) -> api.RequestedOut:
        """Takes no amount: it asks for exactly what the engine computed."""
        case = svc.get_case(s, active.identity, case_id)
        outcome = conventional.request_adjustment(s, active.identity, case)
        return api.RequestedOut(
            status=outcome.status, adjustment=_adjustment(s, outcome.row) if outcome.row is not None else None
        )

    @router.post("/cases/{case_id}/closure", response_model=api.ClosedOut)
    def close_case(s: DB, active: Writer, case_id: int, body: api.CloseCase) -> api.ClosedOut:
        case = svc.get_case(s, active.identity, case_id)
        override = conventional.close_case(s, active.identity, case, body.code, body.reason)
        return api.ClosedOut(status=case.status, override=override)

    def _visible_request(
        s: Session, active: sessions.ActiveSession, request_id: int
    ) -> tuple[AdjustmentRequestRow, Case]:
        require_case_reader(active.identity)
        row, case = load_request(s, request_id)
        if case.customer_id != active.identity.customer_id:
            raise svc.CaseNotFound(request_id)
        return row, case

    @router.get("/adjustments/{request_id}", response_model=api.AdjustmentOut)
    def execution_status(s: DB, active: Reader, request_id: int) -> api.AdjustmentOut:
        row, _case_row = _visible_request(s, active, request_id)
        return _adjustment(s, row)

    @router.post("/adjustments/{request_id}/decision", response_model=api.DecisionOut)
    def decide(s: DB, active: Writer, request_id: int, body: api.Decision) -> api.DecisionOut:
        _row, case = _visible_request(s, active, request_id)
        result = write_path.decide(
            s,
            active.identity,
            request_id,
            systems_for(svc.read_time(case)),
            approve=body.decision == "approve",
            reason=body.reason,
        )
        return api.DecisionOut(status=result.status, message=result.message)

    @router.post("/adjustments/{request_id}/execution", response_model=api.ExecutionOut, status_code=202)
    def execute(s: DB, active: Writer, request_id: int) -> api.ExecutionOut:
        _visible_request(s, active, request_id)
        result = write_path.request_execution(s, active.identity, request_id)
        return api.ExecutionOut(status=result.status, message=result.message)

    @router.get("/cases/{case_id}/audit", response_model=list[api.AuditEvent])
    def audit(s: DB, active: Reader, case_id: int) -> list[api.AuditEvent]:
        case = svc.get_case(s, active.identity, case_id)
        return [
            api.AuditEvent(
                step=e.step, actor=e.actor, actor_kind=e.actor_kind, action=e.action, detail=e.detail, at_utc=e.at_utc
            )
            for e in events(s, case)
        ]

    @router.post("/cases/{case_id}/feedback", response_model=api.FeedbackOut, status_code=201)
    def feedback(s: DB, active: Writer, case_id: int, body: api.FeedbackGiven) -> api.FeedbackOut:
        case = svc.get_case(s, active.identity, case_id)
        row = conventional.give_feedback(s, active.identity, case, body.rating, body.comment)
        return api.FeedbackOut(id=row.id, kind=row.kind, rating=row.rating)

    @router.get("/metrics", response_model=api.MetricsOut)
    def aggregate_metrics(s: DB, active: Reader) -> api.MetricsOut:
        return api.MetricsOut(**asdict(metrics.collect(s, active.identity)))

    @router.get("/policies/{policy_id}/v{version}/{section_id}", response_model=api.ExcerptOut)
    def excerpt(s: DB, active: Reader, policy_id: str, version: int, section_id: str) -> api.ExcerptOut:
        cited = policies.excerpt(s, active.identity.customer_id, policy_id, version, section_id)
        if cited is None:
            raise Problem(404, "not_found", "There is no such excerpt")
        return api.ExcerptOut(
            policy_id=cited.ref.policy_id,
            version=cited.ref.version,
            section_id=cited.ref.section,
            title=cited.title,
            heading=cited.heading,
            text=cited.text,
            effective_from=cited.effective_from,
            effective_to=cited.effective_to,
            status=cited.status,
            source_checksum=cited.source_checksum,
        )

    # ---------- online QA sampling (ENT-18): supervisors and auditors ----------

    @router.get("/qa/samples", response_model=list[api.QaSampleOut])
    def qa_samples(s: DB, active: Reader) -> list[api.QaSampleOut]:
        found = qa_sampling.pending(s, active.identity)
        rows = s.execute(select(Case.id, Case.reference).where(Case.id.in_([q.case_id for q in found])))
        references = {case_id: reference for case_id, reference in rows}
        return [
            api.QaSampleOut(
                id=q.id,
                case_reference=references[q.case_id],
                arm=q.arm,
                status=q.status,
                sampled_at_utc=q.sampled_at_utc,
            )
            for q in found
        ]

    @router.post("/qa/samples/{sample_id}/review", response_model=api.QaSampleOut)
    def qa_review(s: DB, active: Writer, sample_id: int, body: api.QaReview) -> api.QaSampleOut:
        try:
            done = qa_sampling.review(s, active.identity, sample_id, body.model_dump())
        except qa_sampling.InvalidReview as exc:
            raise Problem(422, "invalid_review", "The review isn't valid", str(exc)) from exc
        reference = s.scalar(select(Case.reference).where(Case.id == done.case_id)) or ""
        return api.QaSampleOut(
            id=done.id, case_reference=reference, arm=done.arm, status=done.status, sampled_at_utc=done.sampled_at_utc
        )

    @router.get("/qa/summary")
    def qa_summary(s: DB, active: Reader) -> dict[str, Any]:
        return qa_sampling.summary(s, active.identity)

    # ---------- security events (SEC-20, ENT-31): administrators and auditors ----------

    @router.get("/security/events")
    def security_event_list(
        s: DB,
        active: Reader,
        since: Annotated[str, Query(pattern=r"^(\d{4}-\d{2}-\d{2})?$")] = "",
        limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    ) -> list[dict[str, Any]]:
        """The same documents as the SIEM export (Elastic Common Schema names; docs/siem-field-map.md)."""
        return [security_events.to_ecs(e) for e in security_events.events(s, active.identity, since, limit)]

    return router


def contract(router: APIRouter) -> dict[str, Any]:
    """The OpenAPI document for `/api/v1` only. The console's HTML routes aren't part of the contract."""
    return get_openapi(title="Loyalty Support Modernization API (SYNTHETIC)", version="1.0.0", routes=router.routes)


def install_api(app: FastAPI, settings: AppSettings, systems_for: SystemsFactory) -> None:
    router = build_router(settings, systems_for)
    app.include_router(router)

    @app.get("/api/v1/openapi.json", include_in_schema=False)
    def openapi_json() -> dict[str, Any]:
        return contract(router)

    @app.exception_handler(404)
    async def not_found(request: Request, exc: Exception) -> Response:
        if request.url.path.startswith("/api/"):
            return problem_response(404, "not_found", "Not found")
        detail = getattr(exc, "detail", "Not Found")
        return JSONResponse({"detail": detail}, status_code=404)
