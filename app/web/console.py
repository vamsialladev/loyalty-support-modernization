"""The server-rendered console (Jinja2 + HTMX + CSS, spec 0.6 and B.13) for arm A's legacy workflow and arm B.

Every page shows the banner: SYNTHETIC DATA, profile, AI mode, customer, simulated time. Every state change is a
POST with the session's CSRF token, followed by a redirect. Every check (role, separation of duties, case state,
evidence) runs in `app.services`; the templates only hide buttons that the server would refuse anyway.
HTMX only swaps search results in place; each page also works as a plain form without JavaScript.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, sessionmaker

from app import correlation
from app.adapters.local_demo_identity import LocalDemoIdentity
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
from app.services import assisted, conventional, jobs, kill_switch, metrics, policies, policy_publishing, sessions
from app.services import cases as svc
from app.services.customer_config import CustomerConfig
from app.services.instrumentation import events, system_events
from app.services.systems import SystemsFactory
from app.services.write_path import SharedWritePath, approval_of, attempts_of, load_request, pending_approvals
from app.settings import AppSettings

WEB_DIR = Path(__file__).resolve().parent
DAY_ONE_DIR = WEB_DIR / "day_one"
SESSION_COOKIE = "lsm_session"
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
    return active


User = Annotated[sessions.ActiveSession, Depends(_signed_in)]
Csrf = Annotated[str, Form()]


def install_console(
    app: FastAPI, settings: AppSettings, factory: sessionmaker[Session], systems_for: SystemsFactory
) -> None:
    customer = CustomerConfig.load(settings.customer_id)
    ai_mode_label = assisted.mode_label(settings)
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
        return render(request, "error.html", None, 403, title="Request refused", message="The form expired. Reload.")

    @app.exception_handler(NotPermitted)
    def _forbidden(request: Request, exc: NotPermitted) -> Response:
        return render(request, "error.html", None, 403, title="Not permitted", message=str(exc))

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
        response = render(request, "login.html", None, 401 if failed else 200, failed=failed, login_csrf=token)
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
        who = identity.authenticate(username, password)
        if who is None:
            return RedirectResponse("/login?failed=true", status_code=303)
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
