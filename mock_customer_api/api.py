"""HTTP layer of the mock customer API (contract version in `mock_customer_api.CONTRACT_VERSION`).

Run: `uvicorn --factory mock_customer_api.api:create_app --port 8020` (reads settings from the environment).
Order on every request: correlation ID -> bearer token -> simulated clock -> fault -> handler -> customer shape.
"""

from __future__ import annotations

import hmac
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, create_model
from sqlalchemy import Boolean, Integer, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from customer_shapes import CustomerShape, ShapeError
from mock_customer_api import CONTRACT_VERSION, db, service
from mock_customer_api.faults import FaultBook
from mock_customer_api.seed import seed as run_seed
from mock_customer_api.service import Problem
from mock_customer_api.settings import Settings

ENTITY_TABLES: dict[str, type[db.Base]] = {
    "member": db.Member,
    "stay": db.Stay,
    "ledger_entry": db.LedgerEntry,
    "posting_queue_item": db.PostingQueueItem,
    "adjustment": db.Adjustment,
    "ticket": db.Ticket,
}
PROBLEM_JSON = "application/problem+json"


def output_model(shape: CustomerShape, entity: str) -> type[BaseModel]:
    """A pydantic model with the customer's upstream field names, for the OpenAPI contract."""
    table = ENTITY_TABLES[entity]
    columns = {c.key: c for c in table.__table__.columns}
    spec: dict[str, Any] = {}
    for canonical, upstream in shape.upstream_names(entity).items():
        column = columns[canonical]
        py: type = str
        if isinstance(column.type, Boolean):
            py = bool
        elif isinstance(column.type, Integer) and shape.conversions.get(upstream) != "usd_to_cents":
            py = int
        spec[upstream] = ((py | None) if column.nullable else py, ...)
    name = "".join(part.title() for part in entity.split("_"))
    return create_model(name, **spec)


def items_model(name: str, item: type[BaseModel], paged: bool = False) -> type[BaseModel]:
    fields: dict[str, Any] = {"items": (list[item], ...)}  # type: ignore[valid-type]
    if paged:
        fields["nextCursor"] = (str | None, None)
    return create_model(name, **fields)


class AdjustmentIn(BaseModel):
    loyaltyId: str = Field(min_length=3, max_length=16)
    confirmationNumber: str = Field(min_length=3, max_length=16)
    points: int = Field(ge=1, le=100_000)
    reasonCode: str = Field(min_length=2, max_length=40)
    requestedBy: str = Field(min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=1000)


class TicketIn(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    loyaltyId: str | None = Field(default=None, max_length=16)


@dataclass
class Ctx:
    correlation_id: str
    at: str
    fault_header: str | None


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    engine = engine or db.make_engine(settings.database_url)
    factory: sessionmaker[Session] = db.make_sessions(engine)
    shape = CustomerShape.load(settings.customer_id)
    faults = FaultBook.load(settings.faults_enabled, settings.fault_rules_file)
    models = {e: output_model(shape, e) for e in ENTITY_TABLES}

    app = FastAPI(
        title="Mock customer API (SYNTHETIC)",
        version=CONTRACT_VERSION,
        description="Synthetic loyalty platform and PMS for the fictional hotel group. Not a real system.",
    )

    @app.exception_handler(Problem)
    def _problem(request: Request, exc: Problem) -> JSONResponse:
        corr = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
        headers = {"X-Correlation-ID": corr}
        if exc.retry_after is not None:
            headers["Retry-After"] = str(exc.retry_after)
        body = {
            "type": f"urn:mock-customer-api:problem:{exc.code}",
            "title": exc.title,
            "status": exc.status,
            "code": exc.code,
            "detail": exc.detail,
            "correlation_id": corr,
        }
        return JSONResponse(body, status_code=exc.status, headers=headers, media_type=PROBLEM_JSON)

    @app.exception_handler(RequestValidationError)
    def _invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(str(p) for p in err["loc"][1:]) for err in exc.errors()})
        return _problem(request, Problem(422, "validation_error", "The request is not valid", ", ".join(fields)))

    @app.exception_handler(Exception)
    def _crash(request: Request, exc: Exception) -> JSONResponse:  # no stack traces to callers (spec C.7)
        return _problem(request, Problem(500, "internal_error", "Internal error"))

    def ctx(
        request: Request,
        authorization: str | None = Header(default=None),
        x_sim_time: str | None = Header(default=None),
        x_mock_fault: str | None = Header(default=None),
    ) -> Ctx:
        corr = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
        supplied = (authorization or "").removeprefix("Bearer ").strip()
        if not supplied or not hmac.compare_digest(supplied.encode(), settings.token.encode()):
            raise Problem(401, "unauthorized", "Missing or invalid bearer token")
        if x_sim_time is not None and not settings.sim_clock_enabled:
            raise Problem(400, "sim_clock_disabled", "X-Sim-Time is only accepted when MOCK_API_SIM_CLOCK=true")
        if x_mock_fault is not None and not settings.faults_enabled:
            raise Problem(400, "faults_disabled", "X-Mock-Fault is only accepted when MOCK_API_FAULTS=true")
        at = service.normalise_ts(x_sim_time) if x_sim_time else service.now_ts()
        return Ctx(corr, at, x_mock_fault)

    def fault_for(c: Ctx, member: str | None = None, stay: str | None = None) -> str | None:
        try:
            fault = faults.pick(c.fault_header, member, stay)
        except ValueError as exc:
            raise Problem(400, "unknown_fault", f"Unknown X-Mock-Fault value {exc}") from exc
        if fault == "auth_failure":
            raise Problem(401, "unauthorized", "Injected authentication failure")
        if fault == "rate_limited":
            raise Problem(429, "rate_limited", "Too many requests (injected)", retry_after=1)
        if fault == "unavailable":
            raise Problem(503, "unavailable", "Temporarily unavailable (injected)", retry_after=1)
        if fault == "timeout":
            time.sleep(settings.timeout_fault_seconds)
        return fault

    def respond(c: Ctx, body: dict[str, Any], fault: str | None, status: int = 200) -> Response:
        headers = {"X-Correlation-ID": c.correlation_id}
        if fault == "malformed":
            return Response(
                b'{"items": [{"loyaltyId": "GR-1', status_code=200, media_type="application/json", headers=headers
            )
        if fault == "schema_v1_1":
            body = _future_shape(body)
        return JSONResponse(body, status_code=status, headers=headers)

    def one(entity: str, record: dict[str, Any]) -> dict[str, Any]:
        return shape.to_upstream(entity, record)

    def many(entity: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        return {"items": [shape.to_upstream(entity, r) for r in records]}

    def session() -> Any:
        with factory() as s:
            yield s

    # ---------- health ----------

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "contract_version": CONTRACT_VERSION}

    @app.get("/readyz", tags=["health"])
    def readyz(s: Session = Depends(session)) -> Response:
        try:
            s.execute(text("SELECT 1"))
            loaded = service.counts(s)
        except Exception:
            return JSONResponse({"status": "not_ready", "database": "unreachable"}, status_code=503)
        ready = loaded["members"] > 0
        return JSONResponse(
            {"status": "ready" if ready else "not_seeded", "database": "ok", "counts": loaded},
            status_code=200 if ready else 503,
        )

    # ---------- members ----------

    member_items = items_model("MemberList", models["member"])

    @app.get("/v1/members/{loyaltyId}", response_model=models["member"], tags=["members"])
    def get_member(loyaltyId: str, c: Ctx = Depends(ctx), s: Session = Depends(session)) -> Response:
        fault = fault_for(c, member=loyaltyId)
        return respond(c, one("member", service.get_member(s, loyaltyId)), fault)

    @app.get("/v1/members", response_model=member_items, tags=["members"])
    def find_members(
        emailAddress: str | None = None,
        phoneNumber: str | None = None,
        c: Ctx = Depends(ctx),
        s: Session = Depends(session),
    ) -> Response:
        fault = fault_for(c)
        return respond(c, many("member", service.find_members(s, emailAddress, phoneNumber)), fault)

    # ---------- stays ----------

    stay_items = items_model("StayList", models["stay"])

    @app.get("/v1/stays/{confirmationNumber}", response_model=stay_items, tags=["stays"])
    def get_stay(confirmationNumber: str, c: Ctx = Depends(ctx), s: Session = Depends(session)) -> Response:
        fault = fault_for(c, stay=confirmationNumber)
        return respond(c, many("stay", service.get_stay_records(s, confirmationNumber)), fault)

    @app.get("/v1/stays", response_model=stay_items, tags=["stays"])
    def find_stays(
        loyaltyId: str | None = None,
        partnerConfirmation: str | None = None,
        c: Ctx = Depends(ctx),
        s: Session = Depends(session),
    ) -> Response:
        fault = fault_for(c, member=loyaltyId)
        return respond(c, many("stay", service.find_stays(s, loyaltyId, partnerConfirmation)), fault)

    # ---------- ledger and posting queue ----------

    ledger_page = items_model("LedgerPage", models["ledger_entry"], paged=True)

    @app.get("/v1/members/{loyaltyId}/ledger", response_model=ledger_page, tags=["ledger"])
    def ledger(
        loyaltyId: str,
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        c: Ctx = Depends(ctx),
        s: Session = Depends(session),
    ) -> Response:
        fault = fault_for(c, member=loyaltyId)
        if fault == "partial" and cursor:
            raise Problem(503, "unavailable", "Temporarily unavailable (injected, later page)", retry_after=1)
        items, nxt = service.ledger_page(s, loyaltyId, c.at, cursor, limit)
        return respond(c, {**many("ledger_entry", items), "nextCursor": nxt}, fault)

    posting_items = items_model("PostingQueueList", models["posting_queue_item"])

    @app.get("/v1/posting-queue", response_model=posting_items, tags=["ledger"])
    def posting_queue(confirmationNumber: str, c: Ctx = Depends(ctx), s: Session = Depends(session)) -> Response:
        fault = fault_for(c, stay=confirmationNumber)
        return respond(c, many("posting_queue_item", service.pending_postings(s, confirmationNumber, c.at)), fault)

    # ---------- tickets ----------

    @app.post("/v1/tickets", response_model=models["ticket"], status_code=201, tags=["tickets"])
    def create_ticket(payload: TicketIn, c: Ctx = Depends(ctx)) -> Response:
        fault = fault_for(c, member=payload.loyaltyId)
        body = shape.to_canonical("ticket", payload.model_dump(), required=("subject", "body"))
        return respond(c, one("ticket", service.create_ticket(factory, body, c.at)), fault, status=201)

    # ---------- adjustments ----------

    adjustment_items = items_model("AdjustmentList", models["adjustment"])

    @app.post(
        "/v1/adjustments",
        response_model=models["adjustment"],
        status_code=201,
        tags=["adjustments"],
        responses={409: {"description": "Idempotency key reused with a different body"}},
    )
    def submit_adjustment(
        payload: AdjustmentIn,
        c: Ctx = Depends(ctx),
        idempotency_key: str | None = Header(default=None),
    ) -> Response:
        fault = fault_for(c, member=payload.loyaltyId, stay=payload.confirmationNumber)
        try:
            body = shape.to_canonical(
                "adjustment",
                payload.model_dump(),
                required=("member_number", "stay_id", "points", "reason_code", "requested_by"),
            )
        except ShapeError as exc:
            raise Problem(422, "validation_error", "The request is not valid", str(exc)) from exc
        submit: Callable[[], tuple[int, dict[str, Any], bool]] = lambda: service.submit_adjustment(  # noqa: E731
            factory, idempotency_key or "", body, c.at, crash_before_commit=fault == "crash_before_commit"
        )
        status, result, _replayed = submit()
        if fault == "duplicate":
            status, result, _replayed = submit()  # a network-level retry: must replay, never apply twice
        if fault == "commit_then_lost":
            raise Problem(504, "gateway_timeout", "The gateway timed out (injected after commit)")
        return respond(c, one("adjustment", result), fault, status=status)

    @app.get("/v1/adjustments/{adjustmentId}", response_model=models["adjustment"], tags=["adjustments"])
    def get_adjustment(adjustmentId: str, c: Ctx = Depends(ctx), s: Session = Depends(session)) -> Response:
        fault = fault_for(c)
        row = s.get(db.Adjustment, adjustmentId)
        if row is None:
            raise Problem(404, "adjustment_not_found", "No adjustment with this ID")
        return respond(c, one("adjustment", service.as_dict(row)), fault)

    @app.get("/v1/adjustments", response_model=adjustment_items, tags=["adjustments"])
    def find_adjustment(idempotencyKey: str, c: Ctx = Depends(ctx), s: Session = Depends(session)) -> Response:
        fault = fault_for(c)
        return respond(c, many("adjustment", service.find_adjustment(s, idempotencyKey)), fault)

    # ---------- control (spec B.3: reset and seed) ----------

    @app.post("/_control/seed", tags=["control"])
    def control_seed(dataset: str = "v1", reset: bool = False, c: Ctx = Depends(ctx)) -> Response:
        if settings.public_demo_mode:
            raise Problem(403, "control_disabled", "Control endpoints are off in public demo mode")
        if dataset not in ("v1", "demo"):
            raise Problem(400, "unknown_dataset", "Datasets: v1 (alias demo)")
        return JSONResponse(
            {"counts": run_seed(factory, settings.seed_dir, reset=reset)},
            headers={"X-Correlation-ID": c.correlation_id},
        )

    @app.post("/_control/reset", tags=["control"])
    def control_reset(c: Ctx = Depends(ctx)) -> Response:
        if settings.public_demo_mode:
            raise Problem(403, "control_disabled", "Control endpoints are off in public demo mode")
        with factory() as s:
            service.wipe(s)
            s.commit()
            return JSONResponse({"counts": service.counts(s)}, headers={"X-Correlation-ID": c.correlation_id})

    return app


def _future_shape(body: dict[str, Any]) -> dict[str, Any]:
    """What a v1.1 contract might look like: `loyaltyId` renamed to `loyalty_id`, plus a new field."""

    def change(record: dict[str, Any]) -> dict[str, Any]:
        out = {("loyalty_id" if k == "loyaltyId" else k): v for k, v in record.items()}
        out["marketingOptIn"] = False
        return out

    if isinstance(body.get("items"), list):
        return {**body, "items": [change(r) for r in body["items"]]}
    return change(body)


def export_contract() -> str:
    """The OpenAPI document as stable JSON (committed as contracts/openapi-v1.json)."""
    settings = Settings(database_url="sqlite://", token="contract-export")  # noqa: S106 - not a real token
    return json.dumps(create_app(settings).openapi(), indent=2, sort_keys=True) + "\n"
