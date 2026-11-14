"""The server-rendered console (Jinja2 + HTMX + CSS, spec 0.6 and B.13) for arm A's legacy workflow and arm B.

Every page shows the banner: SYNTHETIC DATA, profile, AI mode, customer, simulated time. Every state change is a
POST with the session's CSRF token, followed by a redirect. Every check (role, separation of duties, case state,
evidence) runs in `app.services`; the templates only hide buttons that the server would refuse anyway.
HTMX only swaps search results in place; each page also works as a plain form without JavaScript.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import secrets
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import correlation
from app.adapters.local_demo_identity import LocalDemoIdentity
from app.adapters.oidc_identity import OidcClient, OidcError, OidcSettings, provision
from app.ai.harness import latest_run, request_cancel
from app.arms.conventional.extraction import MAX_BYTES
from app.arms.conventional.investigation import OTHER_MEMBER_TEXT
from app.arms.legacy import intake, screens
from app.arms.legacy.keyword_index import KeywordIndex
from app.arms.legacy.rules import LegacyRules
from app.domain.business_time import local_datetime
from app.domain.case_states import CaseState, InvalidTransition
from app.domain.roles import NotPermitted, Role, approval_refusal, require_administrator, require_case_worker
from app.persistence.models import Case
from app.ports.customer_systems import CustomerSystemError
from app.services import (
    accounts,
    assisted,
    conventional,
    jobs,
    kill_switch,
    metrics,
    policies,
    policy_publishing,
    rate_limit,
    retention,
    sessions,
)
from app.services import cases as svc
from app.services.customer_config import CustomerConfig
from app.services.instrumentation import events, record_system, system_events
from app.services.systems import SystemsFactory
from app.services.write_path import SharedWritePath, approval_of, attempts_of, load_request, pending_approvals
from app.settings import AppSettings

log = logging.getLogger("app.console")
WEB_DIR = Path(__file__).resolve().parent
DAY_ONE_DIR = WEB_DIR / "day_one"
SESSION_COOKIE = "lsm_session"
OIDC_COOKIE = "lsm_oidc"
MAX_UPLOAD_BYTES = MAX_BYTES
LOGIN_CSRF_COOKIE = "lsm_login_csrf"
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; form-action 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
)
DONE_MESSAGES = {
    "created": "Case created.",
    "investigating": "Investigation queued. This page updates by itself when the result is in.",
    "asked": "Question sent to the member. The case is waiting for their reply.",
    "more_stays": "Question about the other stays sent. The case keeps moving.",
    "supplied": "Answer stored. Investigating again.",
    "attached_document": "Document added. Investigate again to read it.",
    "cancelling": "Asked the AI run to stop. The rules result stands.",
    "nothing_running": "No AI run is going on.",
    "feedback": "Thanks: feedback recorded.",
    "group_escalated": "The linked cases together are over the supervisor limit, so all of them were escalated.",
    "overridden": "Case closed against the engine's result. The override and your reason are logged.",
    "started": "Work started. Use the four screens to find and attach the evidence.",
    "attached": "Evidence attached to the case.",
    "note": "Note added.",
    "requested": "Adjustment sent for a supervisor's approval.",
    "closed": "Case closed.",
    "info": "Message sent to the member. The case is waiting for their reply.",
    "resumed": "Investigation resumed.",
    "escalated": "Case escalated.",
    "reopened": "Case reopened.",
    "approved": "Adjustment approved. It can now be executed.",
    "invalidated": "The evidence or policy changed, or the approval expired, so it can't stand. The case is back under "
    "investigation: check the evidence and request again.",
    "rejected": "Adjustment rejected.",
    "queued": "Queued for the worker. This page updates by itself when the result is in.",
    "applied": "Adjustment applied in the loyalty platform.",
    "unknown": "The outcome is still unknown; check the status again shortly.",
    "not_applied": "Reconciled: nothing was applied. It can be executed again with the same key.",
    "refused_duplicate": "Not executed: this stay was already credited by another case. The case was escalated.",
    "rejected_upstream": "The loyalty platform refused the adjustment. Nothing was applied.",
}


class LoginRequired(Exception):
    pass


class CsrfFailed(Exception):
    pass


def _db(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as s:
        yield s


DB = Annotated[Session, Depends(_db)]


def _signed_in(request: Request, s: DB) -> sessions.ActiveSession:
    active = sessions.resolve(s, request.app.state.identity, request.cookies.get(SESSION_COOKIE))
    if active is None:
        raise LoginRequired
    rate_limit.hit(s, f"user:{active.identity.user_id}", request.app.state.rate_limit_per_minute, 60)
    return active


def _address(request: Request) -> str:
    return request.client.host if request.client else "unknown"


User = Annotated[sessions.ActiveSession, Depends(_signed_in)]
Csrf = Annotated[str, Form()]


def install_console(
    app: FastAPI, settings: AppSettings, factory: sessionmaker[Session], systems_for: SystemsFactory
) -> None:
    customer = CustomerConfig.load(settings.customer_id)
    ai_mode_label = assisted.mode_label(settings)
    oidc = (
        OidcClient(
            OidcSettings(
                settings.oidc_issuer_url,
                settings.oidc_client_id,
                settings.oidc_client_secret,
                f"{settings.app_base_url}/auth/oidc/callback",
                customer.oidc_group_roles,
                settings.customer_id,
                fetch_url=settings.oidc_fetch_url,
            ),
            app.state.oidc_http,
        )
        if settings.auth_mode == "oidc"
        else None
    )
    templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

    def property_time(utc: str | None, property_name: str | None = None) -> str:
        """A UTC time on the property's clock, with the zone named (spec B.13). UTC when the zone is unknown."""
        if not utc:
            return ""
        timezone = customer.rules.property_timezones.get(property_name or "")
        return local_datetime(utc, timezone) if timezone else utc

    templates.env.filters["property_time"] = property_time
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
    identity = LocalDemoIdentity(factory)
    app.state.sessions, app.state.identity = factory, identity
    app.state.rate_limit_per_minute = settings.rate_limit_per_minute
    rules = LegacyRules.load(settings.customer_id)
    index = KeywordIndex.load()
    write_path = SharedWritePath(settings.customer_id, secret_key=settings.secret_key or None)

    # ---------- plumbing ----------

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Any]) -> Response:
        correlation_id = correlation.new_id()  # made here, never taken from the request
        with correlation.correlated(correlation_id):
            response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if not request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def check_csrf(active: sessions.ActiveSession, token: str) -> None:
        if not sessions.csrf_ok(active, token):
            raise CsrfFailed

    def banner(case: Case | None) -> dict[str, str]:
        sim = "per case"
        ai_mode = "none (arms A and B)"
        if case is not None:
            sim = case.received_at_utc if settings.sim_clock else "off (live mock clock)"
            ai_mode = {
                svc.ARM_A: "none (arm A, legacy)",
                svc.ARM_B: "none (arm B, rules and search)",
                svc.ARM_C: f"{ai_mode_label} (arm C)",
            }[case.arm]
        return {
            "profile": settings.profile,
            "ai_mode": ai_mode,
            "customer": settings.customer_id,
            "sim_time": sim,
        }

    def render(
        request: Request,
        name: str,
        active: sessions.ActiveSession | None,
        status_code: int = 200,
        case: Case | None = None,
        **context: Any,
    ) -> HTMLResponse:
        context |= {
            "user": active.identity if active else None,
            "can_work": active is not None and active.identity.role in (Role.AGENT, Role.SUPERVISOR),
            "can_see_metrics": active is not None and active.identity.role is not Role.AGENT,
            "csrf": active.csrf_token if active else "",
            "banner": banner(case),
            "case": case,
            "Role": Role,
        }
        return templates.TemplateResponse(request, name, context, status_code=status_code)

    def back_to(case: Case, done: str) -> RedirectResponse:
        return RedirectResponse(f"/cases/{case.id}?done={done}", status_code=303)

    @app.exception_handler(LoginRequired)
    def _login(request: Request, exc: LoginRequired) -> Response:
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(CsrfFailed)
    def _csrf(request: Request, exc: CsrfFailed) -> Response:
        _audit_denial(request, "csrf_failed")  # a security event (SEC-20): a forged or stale form
        return render(request, "error.html", None, 403, title="Request refused", message="The form expired. Reload.")

    def _audit_denial(request: Request, action: str) -> None:
        """Security events (C.10): what was refused, and where. Never the request's content."""
        with factory() as s:
            record_system(s, jobs.SYSTEM, action, path=request.url.path[:120], method=request.method)
            s.commit()

    @app.exception_handler(NotPermitted)
    def _forbidden(request: Request, exc: NotPermitted) -> Response:
        _audit_denial(request, "authorization_denied")
        return render(request, "error.html", None, 403, title="Not permitted", message=str(exc))

    @app.exception_handler(rate_limit.RateLimited)
    def _too_many(request: Request, exc: rate_limit.RateLimited) -> Response:
        _audit_denial(request, "rate_limited")
        message = "Too many requests. Wait a little and try again."
        response = render(request, "error.html", None, 429, title="Slow down", message=message)
        response.headers["Retry-After"] = str(exc.retry_after_seconds)
        return response

    @app.exception_handler(accounts.AccountError)
    def _account(request: Request, exc: accounts.AccountError) -> Response:
        return render(request, "error.html", None, 409, title="Not possible", message=str(exc))

    @app.exception_handler(Exception)
    def _unexpected(request: Request, exc: Exception) -> Response:
        """No stack trace reaches a person (C.7). The reference finds the details in the log."""
        reference = correlation.current() or correlation.new_id()
        log.exception("unexpected error %s on %s", reference, request.url.path)
        if request.url.path.startswith("/api/"):
            body = {"title": "Something went wrong", "status": 500, "code": "internal", "reference": reference}
            return JSONResponse(body, status_code=500, media_type="application/problem+json")
        message = f"Something went wrong on our side. The reference is {reference}."
        return render(request, "error.html", None, 500, title="Something went wrong", message=message)

    @app.exception_handler(svc.WorkflowError)
    def _workflow(request: Request, exc: svc.WorkflowError) -> Response:
        return render(request, "error.html", None, 409, title="Not possible right now", message=str(exc))

    @app.exception_handler(InvalidTransition)
    def _transition(request: Request, exc: InvalidTransition) -> Response:
        return render(request, "error.html", None, 409, title="Not possible right now", message=str(exc))

    @app.exception_handler(policy_publishing.PublishRefused)
    def _publish_refused(request: Request, exc: policy_publishing.PublishRefused) -> Response:
        message = "; ".join(exc.problems)
        return render(request, "error.html", None, 409, title="Not published", message=message)

    @app.exception_handler(svc.CaseNotFound)
    def _missing(request: Request, exc: svc.CaseNotFound) -> Response:
        return render(request, "error.html", None, 404, title="Not found", message="There is no such case.")

    @app.exception_handler(RequestValidationError)
    def _incomplete(request: Request, exc: RequestValidationError) -> Response:
        fields = sorted({str(err["loc"][-1]) for err in exc.errors()})
        message = "Some fields are missing or not valid: " + ", ".join(fields) + "."
        return render(request, "error.html", None, 400, title="Incomplete form", message=message)

    @app.exception_handler(CustomerSystemError)
    def _upstream(request: Request, exc: CustomerSystemError) -> Response:
        message = f"The customer system did not answer as expected ({exc.code or type(exc).__name__}). Try again."
        return render(request, "error.html", None, 502, title="Customer system error", message=message)

    # ---------- sign in ----------

    @app.get("/", response_model=None)
    def home() -> RedirectResponse:
        return RedirectResponse("/queue", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, failed: bool = False) -> HTMLResponse:
        token = secrets.token_urlsafe(24)
        status = 401 if failed else 200
        response = render(request, "login.html", None, status, failed=failed, login_csrf=token, oidc=oidc is not None)
        response.set_cookie(
            LOGIN_CSRF_COOKIE, token, httponly=True, samesite="strict", secure=settings.cookie_secure, max_age=900
        )
        return response

    @app.post("/login", response_model=None)
    def login(
        request: Request,
        s: DB,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
        login_csrf: Annotated[str, Form()] = "",
    ) -> Response:
        cookie = request.cookies.get(LOGIN_CSRF_COOKIE, "")
        if not cookie or not secrets.compare_digest(cookie, login_csrf):
            raise CsrfFailed
        if oidc is not None:
            raise svc.WorkflowError("this deployment signs in through the identity provider")
        address = _address(request)
        rate_limit.check_login(s, username, address)
        who = identity.authenticate(username, password)
        if who is None:
            rate_limit.record_login_failure(s, username, address)
            record_system(s, jobs.SYSTEM, "sign_in_failed", method="password")
            s.commit()
            return RedirectResponse("/login?failed=true", status_code=303)
        rate_limit.clear_login_failures(s, username)
        token, _csrf = sessions.start(s, who)
        response = RedirectResponse("/admin" if who.role is Role.ADMINISTRATOR else "/queue", status_code=303)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            samesite="strict",
            secure=settings.cookie_secure,
            max_age=sessions.SESSION_HOURS * 3600,
        )
        response.delete_cookie(LOGIN_CSRF_COOKIE)
        return response

    @app.get("/auth/oidc/start", response_model=None)
    def oidc_start() -> Response:
        if oidc is None:
            return RedirectResponse("/login", status_code=303)
        begun = oidc.start()
        response = RedirectResponse(begun.url, status_code=303)
        value = f"{begun.state}|{begun.nonce}|{begun.verifier}"
        # Lax, not Strict: the provider sends the browser back from another site, and this cookie must come along.
        response.set_cookie(
            OIDC_COOKIE, value, httponly=True, samesite="lax", secure=settings.cookie_secure, max_age=600
        )
        return response

    @app.get("/auth/oidc/callback", response_model=None)
    def oidc_callback(request: Request, s: DB, code: str = "", state: str = "") -> Response:
        failed = render(
            request, "error.html", None, 401, title="Sign-in failed", message="Sign-in didn't work. Try again."
        )
        parts = request.cookies.get(OIDC_COOKIE, "").split("|")
        if oidc is None or len(parts) != 3 or not state or not secrets.compare_digest(parts[0], state) or not code:
            record_system(s, jobs.SYSTEM, "sign_in_failed", method="oidc", reason="state")
            s.commit()
            return failed
        try:
            claims = oidc.verify(oidc.exchange(code, parts[2]), parts[1])
            who = provision(s, claims, oidc.settings)
        except OidcError as exc:
            record_system(s, jobs.SYSTEM, "sign_in_failed", method="oidc", reason=str(exc)[:48])
            s.commit()
            return failed
        token, _csrf = sessions.start(s, who)
        target = "/admin" if who.role is Role.ADMINISTRATOR else "/queue"
        # A plain page, not a redirect: a Strict cookie isn't sent on a chain that began on another site.
        html = f'<!doctype html><meta http-equiv="refresh" content="0;url={target}"><a href="{target}">Continue</a>'
        response = HTMLResponse(html)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            samesite="strict",
            secure=settings.cookie_secure,
            max_age=sessions.SESSION_HOURS * 3600,
        )
        response.delete_cookie(OIDC_COOKIE)
        return response

    @app.get("/recover", response_class=HTMLResponse)
    def recover_page(request: Request, token: str = "") -> HTMLResponse:
        login_token = secrets.token_urlsafe(24)
        response = render(request, "recover.html", None, token=token, login_csrf=login_token)
        response.set_cookie(
            LOGIN_CSRF_COOKIE, login_token, httponly=True, samesite="strict", secure=settings.cookie_secure, max_age=900
        )
        return response

    @app.post("/recover", response_model=None)
    def recover(
        request: Request,
        s: DB,
        token: Annotated[str, Form()],
        password: Annotated[str, Form()],
        login_csrf: Annotated[str, Form()] = "",
    ) -> Response:
        cookie = request.cookies.get(LOGIN_CSRF_COOKIE, "")
        if not cookie or not secrets.compare_digest(cookie, login_csrf):
            raise CsrfFailed
        address = _address(request)
        rate_limit.check_login(s, "recovery", address)
        try:
            accounts.redeem_recovery(s, token, password)
        except accounts.AccountError:
            rate_limit.record_login_failure(s, "recovery", address)
            raise
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(LOGIN_CSRF_COOKIE)
        return response

    @app.post("/logout", response_model=None)
    def logout(request: Request, s: DB, active: User, csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        sessions.revoke(s, request.cookies.get(SESSION_COOKIE))
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(SESSION_COOKIE)
        return response

    # ---------- queue and intake ----------

    @app.get("/queue", response_model=None)
    def queue(
        request: Request,
        s: DB,
        active: User,
        queue: str = intake.POINTS_QUEUE,
        status: str = "",
        mine: bool = False,
        arm: str = "",
    ) -> Response:
        if active.identity.role is Role.ADMINISTRATOR:
            return RedirectResponse("/admin", status_code=303)
        if queue not in (intake.POINTS_QUEUE, intake.BILLING_QUEUE):
            queue = intake.POINTS_QUEUE
        arm = arm if arm in svc.ARMS else ""
        rows = svc.list_cases(s, active.identity, queue=queue, status=status or None, mine=mine, arm=arm or None)
        return render(
            request,
            "queue.html",
            active,
            rows=rows,
            queue=queue,
            status=status,
            mine=mine,
            arm=arm,
            arms=svc.ARMS,
            states=[st.value for st in CaseState],
        )

    @app.get("/cases/new", response_class=HTMLResponse)
    def new_case_page(request: Request, active: User) -> HTMLResponse:
        require_case_worker(active.identity)
        return render(request, "case_new.html", active)

    @app.post("/cases", response_model=None)
    def create_case(
        s: DB,
        active: User,
        received_at_utc: Annotated[str, Form()],
        contact_channel: Annotated[str, Form()],
        text: Annotated[str, Form()],
        sender_email: Annotated[str, Form()] = "",
        form_member_number: Annotated[str, Form()] = "",
        form_confirmation: Annotated[str, Form()] = "",
        form_name: Annotated[str, Form()] = "",
        arm: Annotated[str, Form()] = svc.ARM_A,
        csrf: Csrf = "",
    ) -> Response:
        check_csrf(active, csrf)
        received = received_at_utc.strip()
        if len(received) == 16:  # <input type="datetime-local"> sends YYYY-MM-DDTHH:MM
            received += ":00Z"
        if len(received) != 20 or not received.endswith("Z"):
            raise svc.WorkflowError("give the received time in UTC, for example 2026-07-20T14:00:00Z")
        request_ = svc.IntakeRequest(
            received_at_utc=received,
            contact_channel=contact_channel if contact_channel in ("phone_note", "email", "web_form") else "phone_note",
            text=text,
            sender_email=sender_email.strip() or None,
            form_member_number=form_member_number.strip() or None,
            form_confirmation=form_confirmation.strip() or None,
            form_name=form_name.strip() or None,
        )
        case = svc.create_case(s, active.identity, request_, customer_id=settings.customer_id, arm=arm)
        return back_to(case, "created")

    # ---------- case detail and decisions ----------

    @app.get("/cases/{case_id}", response_class=HTMLResponse)
    def case_page(request: Request, s: DB, active: User, case_id: int, done: str = "") -> HTMLResponse:
        case = svc.get_case(s, active.identity, case_id)
        if case.arm in (svc.ARM_B, svc.ARM_C):
            return arm_b_page(request, s, active, case, done)
        adjustments = adjustment_view(s, active, case)
        checklist = svc.checklist_for(s, case, rules)
        return render(
            request,
            "case.html",
            active,
            case=case,
            requests=svc.requests_of(s, case),
            evidence=svc.current_evidence(s, case),
            checklist=checklist,
            notes=svc.notes_of(s, case),
            adjustments=adjustments,
            events=events(s, case),
            close_codes=svc.close_codes_for(checklist.outcome),
            message=DONE_MESSAGES.get(done, ""),
            policy_sections={ref: index.get(ref) for ref in svc.current_evidence(s, case).policy_refs},
            can_search=can_search(case),
            job_active=jobs.active_case_job(s, case.id),
            polling=_polling(s, case),
            switch_engaged=kill_switch.is_engaged(s),
        )

    def adjustment_view(s: Session, active: sessions.ActiveSession, case: Case) -> list[dict[str, Any]]:
        return [
            {
                "row": row,
                "approval": approval_of(s, row),
                "attempts": attempts_of(s, row),
                "refusal": approval_refusal(active.identity, row.requested_by),
            }
            for row in svc.adjustment_requests_of(s, case)
        ]

    def arm_b_page(request: Request, s: Session, active: sessions.ActiveSession, case: Case, done: str) -> HTMLResponse:
        rec = conventional.latest_recommendation(s, case)
        group = [c for c in conventional.group_cases(s, case) if c.id != case.id]
        evidence = conventional.latest_evidence(s, case)
        return render(
            request,
            "case_b.html",
            active,
            case=case,
            requests=svc.requests_of(s, case),
            rec=rec,
            evidence=evidence,
            stay_property=(evidence["records"][0]["property"] if evidence and evidence["records"] else None),
            close_code=conventional.recommended_close_code(rec) if rec else None,
            close_codes=conventional.CLOSE_CODES,
            prompt=conventional.prompt_for(rec),
            channels=conventional.CHANNELS,
            answers=conventional.member_answers(s, case),
            group=group,
            notes=svc.notes_of(s, case),
            adjustments=adjustment_view(s, active, case),
            events=events(s, case),
            feedback=conventional.feedback_of(s, case),
            message=DONE_MESSAGES.get(done, ""),
            job_active=jobs.active_case_job(s, case.id),
            job_failed=conventional.failed_investigation(s, case),
            polling=_polling(s, case),
            switch_engaged=kill_switch.is_engaged(s),
            other_member_text=OTHER_MEMBER_TEXT,
            attachments=conventional.attachments_of(s, case),
            ai_run=latest_run(s, case) if case.arm == svc.ARM_C else None,
            live_run=getattr(request.app.state, "ag_ui", False),  # set only when FEATURE_AG_UI mounts the endpoint
        )

    def _polling(s: Session, case: Case) -> bool:
        """While a result is on its way, the page refreshes itself."""
        waiting = CaseState(case.status) in (CaseState.EXECUTING, CaseState.EXECUTION_UNKNOWN)
        return waiting or jobs.active_case_job(s, case.id) is not None

    @app.post("/cases/{case_id}/start", response_model=None)
    def start(
        s: DB,
        active: User,
        case_id: int,
        csrf: Csrf = "",
    ) -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        svc.start_work(s, active.identity, case)
        return back_to(case, "started")

    @app.post("/cases/{case_id}/notes", response_model=None)
    def note(s: DB, active: User, case_id: int, body: Annotated[str, Form()], csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        svc.add_note(s, active.identity, case, body)
        return back_to(case, "note")

    @app.post("/cases/{case_id}/request-adjustment", response_model=None)
    def request_adjustment(s: DB, active: User, case_id: int, csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        if case.arm in (svc.ARM_B, svc.ARM_C):
            outcome = conventional.request_adjustment(s, active.identity, case)
            return back_to(case, "requested" if outcome.row is not None else "group_escalated")
        svc.request_adjustment(s, active.identity, case, rules)
        return back_to(case, "requested")

    # ---------- arm B: the investigation and what follows from it ----------

    @app.post("/cases/{case_id}/investigate", response_model=None)
    def investigate(s: DB, active: User, case_id: int, csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        conventional.start_investigation(s, active.identity, case)
        return back_to(case, "investigating")

    @app.post("/cases/{case_id}/cancel-investigation", response_model=None)
    def cancel_investigation(s: DB, active: User, case_id: int, csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        require_case_worker(active.identity)
        case = svc.get_case(s, active.identity, case_id)
        return back_to(case, "cancelling" if request_cancel(s, case) else "nothing_running")

    @app.post("/cases/{case_id}/ask", response_model=None)
    def ask(s: DB, active: User, case_id: int, message: Annotated[str, Form()] = "", csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        conventional.ask_member(s, active.identity, case, systems_for(svc.read_time(case)), message)
        return back_to(case, "asked")

    @app.post("/cases/{case_id}/more-stays", response_model=None)
    def more_stays(s: DB, active: User, case_id: int, csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        conventional.mention_more_stays(s, active.identity, case, systems_for(svc.read_time(case)))
        return back_to(case, "more_stays")

    @app.post("/cases/{case_id}/supply-info", response_model=None)
    def supply_info(
        s: DB,
        active: User,
        case_id: int,
        reply_text: Annotated[str, Form()] = "",
        booking_channel: Annotated[str, Form()] = "",
        member_number: Annotated[str, Form()] = "",
        confirmation: Annotated[str, Form()] = "",
        scope_cleared: Annotated[bool, Form()] = False,
        csrf: Csrf = "",
    ) -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        conventional.supply_information(
            s,
            active.identity,
            case,
            reply_text=reply_text,
            booking_channel=booking_channel,
            member_number=member_number,
            confirmation=confirmation,
            scope_cleared=scope_cleared,
        )
        return back_to(case, "supplied")

    @app.post("/cases/{case_id}/attachments", response_model=None)
    async def add_attachment(
        s: DB,
        active: User,
        case_id: int,
        file: Annotated[UploadFile, File()],
        csrf: Csrf = "",
    ) -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        conventional.add_attachment(s, active.identity, case, file.filename or "upload", content)
        return back_to(case, "attached_document")

    @app.post("/cases/{case_id}/feedback", response_model=None)
    def feedback(
        s: DB,
        active: User,
        case_id: int,
        rating: Annotated[str, Form()],
        comment: Annotated[str, Form()] = "",
        csrf: Csrf = "",
    ) -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        conventional.give_feedback(s, active.identity, case, rating, comment)
        return back_to(case, "feedback")

    @app.get("/cases/{case_id}/policy-search", response_class=HTMLResponse)
    def policy_search(request: Request, s: DB, active: User, case_id: int, q: str = "") -> HTMLResponse:
        """D12 and D15: synonyms and full-text search, only over the versions in force on this stay's checkout date."""
        arm = svc.ARM_C if svc.get_case(s, active.identity, case_id).arm == svc.ARM_C else svc.ARM_B
        case = screen_case(s, active, case_id, arm)
        rec = conventional.latest_recommendation(s, case)
        day = date.fromisoformat(rec.checkout_day) if rec and rec.checkout_day else None
        hits = conventional.search_policy(s, case.customer_id, q, day) if day and q.strip() else []
        if day and q.strip():
            svc.log_search(s, case, active.identity, "policy", "full text", len(hits))
        return render(
            request,
            "case_b_policy.html",
            active,
            case=case,
            q=q,
            hits=hits,
            day=day,
            searched=bool(day and q.strip()),
        )

    @app.post("/cases/{case_id}/close", response_model=None)
    def close(
        s: DB,
        active: User,
        case_id: int,
        code: Annotated[str, Form()],
        note: Annotated[str, Form()] = "",
        csrf: Csrf = "",
    ) -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        if case.arm in (svc.ARM_B, svc.ARM_C):
            overridden = conventional.close_case(s, active.identity, case, code, note)
            return back_to(case, "overridden" if overridden else "closed")
        svc.close_case(s, active.identity, case, code, note, rules)
        return back_to(case, "closed")

    @app.post("/cases/{case_id}/request-info", response_model=None)
    def request_info(s: DB, active: User, case_id: int, message: Annotated[str, Form()], csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        svc.request_information(s, active.identity, case, systems_for(case.received_at_utc), message)
        return back_to(case, "info")

    @app.post("/cases/{case_id}/resume", response_model=None)
    def resume(s: DB, active: User, case_id: int, csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        svc.resume(s, active.identity, case)
        return back_to(case, "resumed")

    @app.post("/cases/{case_id}/escalate", response_model=None)
    def escalate(s: DB, active: User, case_id: int, reason: Annotated[str, Form()], csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        svc.escalate(s, active.identity, case, reason)
        return back_to(case, "escalated")

    @app.post("/cases/{case_id}/reopen", response_model=None)
    def reopen(s: DB, active: User, case_id: int, reason: Annotated[str, Form()], csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = svc.get_case(s, active.identity, case_id)
        svc.reopen(s, active.identity, case, reason)
        return back_to(case, "reopened")

    # ---------- the four evidence screens (D14) ----------

    def screen_case(s: Session, active: sessions.ActiveSession, case_id: int, arm: str = svc.ARM_A) -> Case:
        require_case_worker(active.identity)  # the screens read customer records and log each search
        case = svc.get_case(s, active.identity, case_id)
        if case.arm != arm:
            raise svc.WorkflowError(f"this screen belongs to arm {arm}; this case is on arm {case.arm}")
        return case

    def can_search(case: Case) -> bool:
        return CaseState(case.status) is CaseState.INVESTIGATING

    @app.get("/cases/{case_id}/member", response_class=HTMLResponse)
    def member_screen(
        request: Request,
        s: DB,
        active: User,
        case_id: int,
        member_number: str = "",
        first_name: str = "",
        last_name: str = "",
        email: str = "",
    ) -> HTMLResponse:
        case = screen_case(s, active, case_id)
        results, error, searched = [], "", False
        if can_search(case) and (member_number or first_name or last_name or email):
            searched = True
            try:
                results = screens.search_member(
                    systems_for(case.received_at_utc),
                    member_number=member_number,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                )
                by = "member number" if member_number.strip() else "name + email"
                svc.log_search(s, case, active.identity, "member", by, len(results))
            except screens.SearchInputError as exc:
                error = str(exc)
        return render(
            request,
            "screen_member.html",
            active,
            case=case,
            results=results,
            error=error,
            searched=searched,
            can_search=can_search(case),
            form={"member_number": member_number, "first_name": first_name, "last_name": last_name, "email": email},
        )

    @app.post("/cases/{case_id}/member/attach", response_model=None)
    def attach_member(
        s: DB,
        active: User,
        case_id: int,
        member_number: Annotated[str, Form()],
        csrf: Csrf = "",
    ) -> Response:
        check_csrf(active, csrf)
        case = screen_case(s, active, case_id)
        svc.attach_member(s, active.identity, case, systems_for(case.received_at_utc), member_number)
        return back_to(case, "attached")

    def attached_member(s: Session, case: Case) -> str:
        member = svc.current_evidence(s, case).member
        return member.member_number if member else ""

    @app.get("/cases/{case_id}/stay", response_class=HTMLResponse)
    def stay_screen(
        request: Request, s: DB, active: User, case_id: int, member_number: str = "", confirmation: str = ""
    ) -> HTMLResponse:
        case = screen_case(s, active, case_id)
        member_number = member_number or attached_member(s, case)
        result, error, searched = None, "", False
        if can_search(case) and confirmation:
            searched = True
            try:
                result = screens.search_stay(
                    systems_for(case.received_at_utc), member_number=member_number, confirmation=confirmation
                )
                svc.log_search(s, case, active.identity, "stay", "confirmation number", 1 if result else 0)
            except screens.SearchInputError as exc:
                error = str(exc)
        return render(
            request,
            "screen_stay.html",
            active,
            case=case,
            result=result,
            error=error,
            searched=searched,
            can_search=can_search(case),
            form={"member_number": member_number, "confirmation": confirmation},
        )

    @app.post("/cases/{case_id}/stay/attach", response_model=None)
    def attach_stay(
        s: DB,
        active: User,
        case_id: int,
        member_number: Annotated[str, Form()],
        confirmation: Annotated[str, Form()],
        csrf: Csrf = "",
    ) -> Response:
        check_csrf(active, csrf)
        case = screen_case(s, active, case_id)
        svc.attach_stay(s, active.identity, case, systems_for(case.received_at_utc), member_number, confirmation)
        return back_to(case, "attached")

    @app.get("/cases/{case_id}/ledger", response_class=HTMLResponse)
    def ledger_screen(
        request: Request, s: DB, active: User, case_id: int, member_number: str = "", show_older: bool = False
    ) -> HTMLResponse:
        case = screen_case(s, active, case_id)
        member_number = member_number or attached_member(s, case)
        view, groups = None, []
        if can_search(case) and member_number:
            view = screens.ledger_view(
                systems_for(case.received_at_utc),
                member_number=member_number,
                as_of_utc=case.received_at_utc,
                show_older=show_older,
            )
            svc.log_search(s, case, active.identity, "ledger", "all" if show_older else "90 days", len(view.entries))
            by_day: dict[str, list[Any]] = {}
            for entry in view.entries:
                by_day.setdefault(entry.posted_at_utc[:10], []).append(entry)
            groups = list(by_day.items())
        return render(
            request,
            "screen_ledger.html",
            active,
            case=case,
            view=view,
            groups=groups,
            can_search=can_search(case),
            form={"member_number": member_number, "show_older": show_older},
            default_days=screens.LEDGER_DEFAULT_DAYS,
        )

    @app.post("/cases/{case_id}/ledger/attach", response_model=None)
    def attach_ledger(
        s: DB,
        active: User,
        case_id: int,
        member_number: Annotated[str, Form()],
        show_older: Annotated[bool, Form()] = False,
        csrf: Csrf = "",
    ) -> Response:
        check_csrf(active, csrf)
        case = screen_case(s, active, case_id)
        svc.attach_ledger(s, active.identity, case, systems_for(case.received_at_utc), member_number, show_older)
        return back_to(case, "attached")

    @app.get("/cases/{case_id}/policy", response_class=HTMLResponse)
    def policy_screen(request: Request, s: DB, active: User, case_id: int, q: str = "") -> HTMLResponse:
        case = screen_case(s, active, case_id)
        hits = []
        if can_search(case) and q.strip():
            hits = index.search(q)
            svc.log_search(s, case, active.identity, "policy", "keywords", len(hits))
        return render(
            request,
            "screen_policy.html",
            active,
            case=case,
            hits=hits,
            q=q,
            searched=bool(q.strip()),
            can_search=can_search(case),
            built_as_of=index.built_as_of,
        )

    @app.post("/cases/{case_id}/policy/attach", response_model=None)
    def attach_policy(
        s: DB,
        active: User,
        case_id: int,
        ref: Annotated[str, Form()],
        csrf: Csrf = "",
    ) -> Response:
        check_csrf(active, csrf)
        case = screen_case(s, active, case_id)
        svc.attach_policy(s, active.identity, case, index, ref)
        return back_to(case, "attached")

    # ---------- supervisor approval and execution (the shared write path) ----------

    @app.get("/approvals", response_class=HTMLResponse)
    def approvals(request: Request, s: DB, active: User) -> HTMLResponse:
        rows = [
            {"row": row, "case": case, "refusal": approval_refusal(active.identity, row.requested_by)}
            for row, case in pending_approvals(s, active.identity)
        ]
        return render(request, "approvals.html", active, rows=rows)

    def request_case(s: Session, active: sessions.ActiveSession, request_id: int) -> Case:
        _row, case = load_request(s, request_id)
        return svc.get_case(s, active.identity, case.id)

    @app.post("/adjustments/{request_id}/decide", response_model=None)
    def decide(
        s: DB,
        active: User,
        request_id: int,
        decision: Annotated[str, Form()],
        reason: Annotated[str, Form()] = "",
        csrf: Csrf = "",
    ) -> Response:
        check_csrf(active, csrf)
        case = request_case(s, active, request_id)
        if decision not in ("approve", "reject"):
            raise svc.WorkflowError("choose approve or reject")
        systems = systems_for(svc.read_time(case))
        result = write_path.decide(
            s, active.identity, request_id, systems, approve=decision == "approve", reason=reason
        )
        return back_to(case, result.status)

    @app.post("/adjustments/{request_id}/execute", response_model=None)
    def execute(s: DB, active: User, request_id: int, csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = request_case(s, active, request_id)
        return back_to(case, write_path.request_execution(s, active.identity, request_id).status)

    @app.post("/adjustments/{request_id}/check-status", response_model=None)
    def check_status(s: DB, active: User, request_id: int, csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = request_case(s, active, request_id)
        result = write_path.check_status(s, active.identity, request_id, systems_for(svc.read_time(case)))
        return back_to(case, result.status)

    # ---------- operational metrics and the day-one page ----------

    @app.get("/metrics", response_class=HTMLResponse)
    def metrics_page(request: Request, s: DB, active: User) -> HTMLResponse:
        return render(request, "metrics.html", active, metrics=metrics.collect(s, active.identity))

    def day_one_summary() -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads((DAY_ONE_DIR / "summary.json").read_text(encoding="utf-8"))
        return loaded

    @app.get("/day-one", response_class=HTMLResponse)
    def day_one(request: Request, active: User) -> HTMLResponse:
        """Aggregates exported from the discovery analysis (ADR-0062). The same roles as the metrics."""
        metrics.require_metrics_reader(active.identity)
        summary = day_one_summary()
        return render(request, "day_one.html", active, summary=summary, charts=summary["charts"])

    @app.get("/day-one/charts/{name}", response_model=None)
    def day_one_chart(request: Request, active: User, name: str) -> Response:
        """Behind sign-in, unlike `/static`. Only the charts the export lists, so a name can't reach any other file."""
        metrics.require_metrics_reader(active.identity)
        if name not in {chart["file"] for chart in day_one_summary()["charts"]}:
            return render(request, "error.html", active, 404, title="Not found", message="There is no such chart.")
        return FileResponse(DAY_ONE_DIR / name, media_type="image/png")

    # ---------- configuration: policy versions (administrators) and exact excerpts ----------

    @app.get("/admin/protocols", response_class=HTMLResponse)
    def protocol_lab(request: Request, active: User) -> HTMLResponse:
        """Spec G.13: developer-only, and only when a protocol is switched on. Plain data, no protocol SDK."""
        require_administrator(active.identity)
        from protocols import lab

        if not lab.any_enabled(settings):
            raise HTTPException(status_code=404)  # off: as if the page didn't exist
        return render(request, "protocol_lab.html", active, protocols=lab.entries(settings))

    @app.get("/admin", response_class=HTMLResponse)
    def admin_page(request: Request, s: DB, active: User) -> HTMLResponse:
        require_administrator(active.identity)
        return render(
            request,
            "admin.html",
            active,
            versions=policies.version_rows(s, settings.customer_id),
            system_events=system_events(s),
            switch=kill_switch.state(s),
            switch_engaged=kill_switch.is_engaged(s),
        )

    @app.get("/admin/users", response_class=HTMLResponse)
    def admin_users(request: Request, s: DB, active: User, issued: str = "") -> HTMLResponse:
        require_administrator(active.identity)
        return render(
            request,
            "admin_users.html",
            active,
            users=accounts.users_of(s, active.identity),
            tokens=accounts.api_tokens_of(s, active.identity),
            message=issued,
        )

    @app.post("/admin/users/{user_id}/active", response_model=None)
    def admin_set_active(s: DB, active: User, user_id: int, value: Annotated[str, Form()], csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        accounts.set_active(s, active.identity, user_id, value == "on")
        return RedirectResponse("/admin/users", status_code=303)

    @app.post("/admin/users/{user_id}/recovery", response_class=HTMLResponse)
    def admin_recovery(request: Request, s: DB, active: User, user_id: int, csrf: Csrf = "") -> HTMLResponse:
        check_csrf(active, csrf)
        token = accounts.issue_recovery(s, active.identity, user_id)
        link = f"{settings.app_base_url}/recover?token={token}"
        return render(request, "admin_shown_once.html", active, heading="Recovery link", value=link)

    @app.post("/admin/api-tokens", response_class=HTMLResponse)
    def admin_api_token(
        request: Request, s: DB, active: User, name: Annotated[str, Form()], csrf: Csrf = ""
    ) -> HTMLResponse:
        check_csrf(active, csrf)
        issued = accounts.issue_api_token(s, active.identity, name)
        return render(request, "admin_shown_once.html", active, heading="API token", value=issued.token)

    @app.post("/admin/api-tokens/revoke", response_model=None)
    def admin_api_token_revoke(s: DB, active: User, name: Annotated[str, Form()], csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        accounts.revoke_api_token(s, active.identity, name)
        return RedirectResponse("/admin/users", status_code=303)

    @app.get("/admin/access-review.csv", response_model=None)
    def access_review(s: DB, active: User) -> Response:
        rows = accounts.access_review_rows(s, active.identity)
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=["username", "role", "active", "source", "last_sign_in_utc"])
        writer.writeheader()
        writer.writerows(rows)
        headers = {"Content-Disposition": 'attachment; filename="access-review.csv"'}
        return Response(out.getvalue(), media_type="text/csv", headers=headers)

    def _admin_case(s: Session, active: sessions.ActiveSession, reference: str) -> Case:
        require_administrator(active.identity)
        case = s.scalars(select(Case).where(Case.reference == reference.strip())).first()
        if case is None or case.customer_id != active.identity.customer_id:
            raise svc.CaseNotFound(reference)
        return case

    @app.post("/admin/legal-hold", response_model=None)
    def legal_hold(
        s: DB,
        active: User,
        reference: Annotated[str, Form()],
        hold: Annotated[str, Form()],
        reason: Annotated[str, Form()],
        csrf: Csrf = "",
    ) -> Response:
        check_csrf(active, csrf)
        if not reason.strip():
            raise svc.WorkflowError("give the reason")
        retention.set_legal_hold(s, active.identity, _admin_case(s, active, reference), hold == "on", reason)
        return RedirectResponse("/admin/users", status_code=303)

    @app.post("/admin/data-subject/export", response_model=None)
    def data_subject_export(s: DB, active: User, member_number: Annotated[str, Form()], csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        data = retention.export_member(s, active.identity, member_number.strip())
        headers = {"Content-Disposition": 'attachment; filename="member-export.json"'}
        return JSONResponse(data, headers=headers)

    @app.post("/admin/data-subject/erase", response_class=HTMLResponse)
    def data_subject_erase(
        request: Request,
        s: DB,
        active: User,
        member_number: Annotated[str, Form()],
        confirm: Annotated[str, Form()] = "",
        csrf: Csrf = "",
    ) -> HTMLResponse:
        check_csrf(active, csrf)
        if confirm.strip() != member_number.strip():
            raise svc.WorkflowError("type the member number again to confirm")
        report = retention.erase_member(s, active.identity, member_number.strip())
        return render(request, "admin_shown_once.html", active, heading="Erasure done", value=str(report))

    @app.post("/admin/kill-switch", response_model=None)
    def set_kill_switch(
        s: DB, active: User, engage: Annotated[str, Form()], reason: Annotated[str, Form()] = "", csrf: Csrf = ""
    ) -> Response:
        check_csrf(active, csrf)
        kill_switch.set_engaged(s, active.identity, engage == "on", reason)
        return RedirectResponse("/admin", status_code=303)

    @app.post("/admin/policies/draft", response_model=None)
    def policy_draft(s: DB, active: User, source: Annotated[str, Form()], csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        policy_publishing.create_draft(s, active.identity, source, settings.customer_id)
        return RedirectResponse("/admin", status_code=303)

    @app.post("/admin/policies/{row_id}/publish", response_model=None)
    def policy_publish(s: DB, active: User, row_id: int, csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        policy_publishing.publish(s, active.identity, row_id, customer)
        return RedirectResponse("/admin", status_code=303)

    @app.get("/policies/{policy_id}/v{version}/{section_id}", response_class=HTMLResponse)
    def policy_excerpt(
        request: Request, s: DB, active: User, policy_id: str, version: int, section_id: str
    ) -> HTMLResponse:
        cited = policies.excerpt(s, settings.customer_id, policy_id, version, section_id)
        if cited is None:
            return render(request, "error.html", active, 404, title="Not found", message="There is no such excerpt.")
        return render(request, "policy_excerpt.html", active, cited=cited)
