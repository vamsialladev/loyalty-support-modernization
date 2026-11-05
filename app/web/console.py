"""The server-rendered console (Jinja2 + HTMX + CSS, spec 0.6 and B.13) for arm A's legacy workflow.

Every page shows the banner: SYNTHETIC DATA, profile, AI mode, customer, simulated time. Every state change is a
POST with the session's CSRF token, followed by a redirect. Every check (role, separation of duties, case state,
evidence) runs in `app.services`; the templates only hide buttons that the server would refuse anyway.
HTMX only swaps search results in place; each page also works as a plain form without JavaScript.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, Form, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.local_demo_identity import LocalDemoIdentity
from app.adapters.mock_customer_api import MockCustomerApiAdapter
from app.arms.legacy import intake, screens
from app.arms.legacy.keyword_index import KeywordIndex
from app.arms.legacy.rules import LegacyRules
from app.domain.case_states import CaseState, InvalidTransition
from app.domain.roles import NotPermitted, Role, approval_refusal, require_administrator, require_case_worker
from app.persistence.models import Case
from app.ports.customer_systems import CustomerSystemError, CustomerSystems
from app.services import cases as svc
from app.services import policies, policy_publishing, sessions
from app.services.customer_config import CustomerConfig
from app.services.instrumentation import events, system_events
from app.services.write_path import SharedWritePath, approval_of, attempts_of, load_request, pending_approvals
from app.settings import AppSettings
from customer_shapes import CustomerShape

SystemsFactory = Callable[[str | None], CustomerSystems]

WEB_DIR = Path(__file__).resolve().parent
SESSION_COOKIE = "lsm_session"
LOGIN_CSRF_COOKIE = "lsm_login_csrf"
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; form-action 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
)
DONE_MESSAGES = {
    "created": "Case created.",
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
    "rejected": "Adjustment rejected.",
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


def mock_systems_factory(settings: AppSettings) -> SystemsFactory:
    """One shared HTTP client; each case's reads use its received time when the simulated clock is on (ADR-0037)."""
    shape = CustomerShape.load(settings.customer_id)
    client = httpx.Client(base_url=settings.mock_api_url, timeout=2.0)

    def make(sim_time: str | None) -> CustomerSystems:
        return MockCustomerApiAdapter(
            settings.mock_api_url,
            settings.mock_api_token,
            shape,
            client=client,
            sim_time=sim_time if settings.sim_clock else None,
        )

    return make


def install_console(
    app: FastAPI, settings: AppSettings, factory: sessionmaker[Session], systems_for: SystemsFactory
) -> None:
    templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
    identity = LocalDemoIdentity(factory)
    app.state.sessions, app.state.identity = factory, identity
    rules = LegacyRules.load(settings.customer_id)
    index = KeywordIndex.load()
    write_path = SharedWritePath(settings.customer_id)
    customer = CustomerConfig.load(settings.customer_id)

    # ---------- plumbing ----------

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Any]) -> Response:
        response: Response = await call_next(request)
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
        if case is not None:
            sim = case.received_at_utc if settings.sim_clock else "off (live mock clock)"
        return {
            "profile": settings.profile,
            "ai_mode": "none (arm A, legacy)",
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
        request: Request, s: DB, active: User, queue: str = intake.POINTS_QUEUE, status: str = "", mine: bool = False
    ) -> Response:
        if active.identity.role is Role.ADMINISTRATOR:
            return RedirectResponse("/admin", status_code=303)
        if queue not in (intake.POINTS_QUEUE, intake.BILLING_QUEUE):
            queue = intake.POINTS_QUEUE
        rows = svc.list_cases(s, active.identity, queue=queue, status=status or None, mine=mine)
        return render(
            request,
            "queue.html",
            active,
            rows=rows,
            queue=queue,
            status=status,
            mine=mine,
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
        case = svc.create_case(s, active.identity, request_, customer_id=settings.customer_id)
        return back_to(case, "created")

    # ---------- case detail and decisions ----------

    @app.get("/cases/{case_id}", response_class=HTMLResponse)
    def case_page(request: Request, s: DB, active: User, case_id: int, done: str = "") -> HTMLResponse:
        case = svc.get_case(s, active.identity, case_id)
        adjustments = []
        for row in svc.adjustment_requests_of(s, case):
            adjustments.append(
                {
                    "row": row,
                    "approval": approval_of(s, row),
                    "attempts": attempts_of(s, row),
                    "refusal": approval_refusal(active.identity, row.requested_by),
                }
            )
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
        )

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
        svc.request_adjustment(s, active.identity, case, rules)
        return back_to(case, "requested")

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

    def screen_case(s: Session, active: sessions.ActiveSession, case_id: int) -> Case:
        require_case_worker(active.identity)  # the screens read customer records and log each search
        return svc.get_case(s, active.identity, case_id)

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
        write_path.decide(s, active.identity, request_id, approve=decision == "approve", reason=reason)
        return back_to(case, "approved" if decision == "approve" else "rejected")

    @app.post("/adjustments/{request_id}/execute", response_model=None)
    def execute(s: DB, active: User, request_id: int, csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = request_case(s, active, request_id)
        result = write_path.execute(s, active.identity, request_id, systems_for(case.received_at_utc))
        return back_to(case, result.status)

    @app.post("/adjustments/{request_id}/check-status", response_model=None)
    def check_status(s: DB, active: User, request_id: int, csrf: Csrf = "") -> Response:
        check_csrf(active, csrf)
        case = request_case(s, active, request_id)
        result = write_path.check_status(s, active.identity, request_id, systems_for(case.received_at_utc))
        return back_to(case, result.status)

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
        )

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
