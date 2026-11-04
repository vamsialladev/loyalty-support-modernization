"""The scripted legacy agent: arm A worked step by step, the way the legacy screens allow (Appendix B; ADR-0048).

Labelled **scripted, not human timing**. Its step counts and elapsed times measure the software path, never an
employee's handling time (spec E.7). It drives the same services the browser uses, with ordinary agent and
supervisor accounts and the same permissions (`scripted-agent`, `scripted-supervisor`), so nothing is bypassed.

Its policy, fixed before any benchmark run (Milestone 10 scores it; nothing here scores anything):
1. A case in the billing queue is not worked (D20): the points claim waits there.
2. A message that isn't in English gets a reply asking for English (D23).
3. Member: the web form's member number, or a `GR-#####` number in the text, searched exactly; otherwise the web
   form's name (or the sign-off line) with the sender's email, searched exactly (D13, D18). A search that found
   nothing: deny as "not found". Nothing to search with, or several candidates: ask the member (ADR-0054).
4. Stay: the web form's confirmation, or the first `BR-####` / `ML-####` in the text, searched exactly within the
   member's stays (D16, D17, D05). None given: ask the member for it. Not found: deny as "not found" (D24).
5. Ledger: the default 90-day view; if it starts after the checkout date, show older entries (ADR-0050).
6. Policy: search "missing points" and attach the first hit.
7. Act on the rules checklist. Adjust -> request approval -> the simulated supervisor reviews -> execute; if the
   outcome is uncertain, check the status once.

It never reads attachments, never guesses between candidates, and never sees labels or generator metadata.

The **simulated supervisor** follows a documented deterministic review policy (spec F7): approve when the stored
checklist passed every line and its outcome is "adjust"; otherwise reject with the reason. Labelled simulated; real
reviewer behaviour comes only from UAT participants. The automation-bias variant is Milestone 10.

    uv run python -m benchmarks.agents.legacy_scripted --split dev --cases DV-001   # mechanics only, no scores
"""

from __future__ import annotations

import argparse
import re
import secrets
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.arms.legacy import intake, screens
from app.arms.legacy.checklist import Outcome
from app.arms.legacy.keyword_index import KeywordIndex
from app.arms.legacy.rules import LegacyRules
from app.clock import utc_now
from app.domain.case_states import CaseState
from app.domain.roles import Identity, Role
from app.persistence.models import Case, CaseEvent, CaseRequest, User
from app.ports.customer_systems import CustomerSystems
from app.services import cases as svc
from app.services.write_path import SharedWritePath, WritePath

LABEL = "scripted, not human timing"
SCRIPTED_AGENT = "scripted-agent"
SCRIPTED_SUPERVISOR = "scripted-supervisor"
POLICY_QUERY = "missing points"
ASK_ENGLISH = "Thank you for your message. Please write to us in English so that we can help with your request."
ASK_CONFIRMATION = "Please send the hotel confirmation number for the stay (for example BR-1234 or ML-1234)."
ASK_MEMBER = "Please send your membership number (for example GR-12345) so that we can find your account."

_MEMBER = re.compile(r"\bGR-\d{5}\b")
_STAY = re.compile(r"\b(?:BR|ML)-\d{4}\b")
_WORD = re.compile(r"[a-zà-ÿ']+")
# Words a reader recognises at a glance as Spanish, French, Portuguese or German (the D23 languages). Checked on the
# dev split only: every non-English request has at least two, no English request has any.
_FOREIGN = frozenset(
    {"hola", "gracias", "puntos", "estancia", "cuenta", "estuve", "aparecen"}
    | {"bonjour", "merci", "j'ai", "séjourné", "compte", "n'apparaissent"}
    | {"olá", "obrigado", "obrigada", "pontos", "minha", "meu", "conta", "não", "estadia", "fiquei", "aparecem"}
    | {"hallo", "danke", "punkte", "mein", "meinem", "konto", "aufenthalt", "nicht", "gutgeschrieben"}
)

SystemsFactory = Callable[[str | None], CustomerSystems]


def is_english(text: str) -> bool:
    """A reader's first glance: fewer than two unmistakably Spanish, French, Portuguese or German words. Terse
    English ("Missing points. Beach Resort, May 10-13.") must count as English."""
    return sum(word in _FOREIGN for word in _WORD.findall(text.lower())) < 2


def signoff_name(text: str) -> str | None:
    """The name on the last line ("Thanks, Clara Kowalski" -> "Clara Kowalski"), or None."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    last = lines[-1].split(", ", 1)[-1].rstrip(".")
    parts = last.split()
    return last if 2 <= len(parts) <= 4 and all(p[:1].isupper() for p in parts) else None


@dataclass
class ScriptedRun:
    case_reference: str
    source_ref: str | None
    final_status: str
    resolution_code: str | None
    steps: int
    elapsed_ms: float
    path: list[str] = field(default_factory=list)
    label: str = LABEL


def ensure_scripted_users(s: Session) -> tuple[Identity, Identity]:
    """Two ordinary accounts with unusable random passwords: they never sign in through the browser."""
    out = []
    for username, display, role in (
        (SCRIPTED_AGENT, "Scripted legacy agent", Role.AGENT),
        (SCRIPTED_SUPERVISOR, "Simulated supervisor", Role.SUPERVISOR),
    ):
        user = s.scalars(select(User).where(User.username == username)).first()
        if user is None:
            user = User(
                username=username,
                display_name=display,
                role=role.value,
                password_hash=PasswordHasher().hash(secrets.token_urlsafe(32)),
                created_at_utc=utc_now(),
            )
            s.add(user)
            s.commit()
        out.append(Identity(user.id, user.username, user.display_name, Role(user.role)))
    return out[0], out[1]


class ScriptedLegacyAgent:
    def __init__(
        self,
        s: Session,
        systems_for: SystemsFactory,
        rules: LegacyRules,
        index: KeywordIndex,
        write_path: WritePath | None = None,
    ) -> None:
        self.s, self.systems_for, self.rules, self.index = s, systems_for, rules, index
        self.write_path = write_path or SharedWritePath(rules.customer_id)
        self.agent, self.supervisor = ensure_scripted_users(s)

    def run(self, case: Case) -> ScriptedRun:
        started = time.perf_counter()
        path: list[str] = []
        try:
            self._work(case, path)
        finally:
            self.s.refresh(case)
        steps = len(list(self.s.scalars(select(CaseEvent.id).where(CaseEvent.case_id == case.id))))
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        return ScriptedRun(case.reference, case.source_ref, case.status, case.resolution_code, steps, elapsed, path)

    # ---------- the script ----------

    def _work(self, case: Case, path: list[str]) -> None:
        s, agent = self.s, self.agent
        if case.queue == intake.BILLING_QUEUE:
            path.append("in_billing_queue")
            return
        svc.start_work(s, agent, case)
        requests = svc.requests_of(s, case)
        text = "\n".join(r.text for r in requests)
        systems = self.systems_for(case.received_at_utc)
        if not is_english(text):
            path.append("asked_for_english")
            svc.request_information(s, agent, case, systems, ASK_ENGLISH)
            return

        member = self._find_member(case, requests, systems, text, path)
        if member is None:
            if not svc.latest_search_found_nothing(s, case, "member"):
                path.append("asked_for_member_number")
                svc.request_information(s, agent, case, systems, ASK_MEMBER)
                return
            path.append("member_not_found")
            svc.close_case(s, agent, case, "deny_not_found", "Member not found by exact search.", self.rules)
            return
        svc.attach_member(s, agent, case, systems, member)

        confirmation = next((r.form_confirmation for r in requests if r.form_confirmation), None)
        if confirmation is None:
            match = _STAY.search(text)
            confirmation = match.group(0) if match else None
        if confirmation is None:
            path.append("asked_for_confirmation")
            svc.request_information(s, agent, case, systems, ASK_CONFIRMATION)
            return
        stay = screens.search_stay(systems, member_number=member, confirmation=confirmation)
        svc.log_search(s, case, agent, "stay", "confirmation number", 1 if stay else 0)
        if stay is None:
            path.append("stay_not_found")
            svc.close_case(s, agent, case, "deny_not_found", "Stay not found on the member's profile.", self.rules)
            return
        svc.attach_stay(s, agent, case, systems, member, confirmation)

        view = screens.ledger_view(systems, member_number=member, as_of_utc=case.received_at_utc)
        svc.log_search(s, case, agent, "ledger", "90 days", len(view.entries))
        older = view.window_start_utc is not None and view.window_start_utc[:10] > stay.checkout_at_utc[:10]
        if older:
            view = screens.ledger_view(systems, member_number=member, as_of_utc=case.received_at_utc, show_older=True)
            svc.log_search(s, case, agent, "ledger", "all", len(view.entries))
        svc.attach_ledger(s, agent, case, systems, member, older)

        hits = self.index.search(POLICY_QUERY)
        svc.log_search(s, case, agent, "policy", "keywords", len(hits))
        if hits:
            svc.attach_policy(s, agent, case, self.index, hits[0].ref)

        self._act(case, systems, path)

    def _find_member(
        self, case: Case, requests: list[CaseRequest], systems: CustomerSystems, text: str, path: list[str]
    ) -> str | None:
        s, agent = self.s, self.agent
        number = next((r.form_member_number for r in requests if r.form_member_number), None)
        if number is None:
            match = _MEMBER.search(text)
            number = match.group(0) if match else None
        if number is not None:
            found = screens.search_member(systems, member_number=number)
            svc.log_search(s, case, agent, "member", "member number", len(found))
            if len(found) == 1:
                return found[0].member_number
        name = next((r.form_name for r in requests if r.form_name), None) or signoff_name(requests[0].text)
        email = next((r.sender_email for r in requests if r.sender_email), None)
        if not name or not email or len(name.split()) < 2:
            return None
        first, last = name.split()[0], " ".join(name.split()[1:])
        found = screens.search_member(systems, first_name=first, last_name=last, email=email)
        svc.log_search(s, case, agent, "member", "name + email", len(found))
        return found[0].member_number if len(found) == 1 else None

    def _act(self, case: Case, systems: CustomerSystems, path: list[str]) -> None:
        s, agent = self.s, self.agent
        checklist = svc.checklist_for(s, case, self.rules)
        path.append(f"checklist:{checklist.outcome.value}")
        closes = {
            Outcome.ALREADY_CREDITED: "no_adjustment_credited",
            Outcome.WAIT: "wait_until",
            Outcome.NOT_CHECKED_OUT: "not_checked_out",
            Outcome.DENY_CHANNEL: "deny_channel_ineligible",
            Outcome.DENY_CLAIM_WINDOW: "deny_claim_window",
        }
        if checklist.outcome in closes:
            svc.close_case(s, agent, case, closes[checklist.outcome], "", self.rules)
            return
        if checklist.outcome is not Outcome.ADJUST:
            svc.escalate(s, agent, case, f"Rules checklist: {checklist.outcome.value}.")
            return
        request = svc.request_adjustment(s, agent, case, self.rules)
        approve, reason = simulated_review(request.checklist)
        path.append("supervisor:" + ("approved" if approve else "rejected"))
        self.write_path.decide(s, self.supervisor, request.id, approve=approve, reason=reason)
        if not approve:
            return
        result = self.write_path.execute(s, self.supervisor, request.id, systems)
        path.append(f"execute:{result.status}")
        self.s.refresh(case)
        if CaseState(case.status) is CaseState.EXECUTION_UNKNOWN:
            result = self.write_path.check_status(s, self.supervisor, request.id, systems)
            path.append(f"reconcile:{result.status}")


def simulated_review(checklist: dict[str, object]) -> tuple[bool, str]:
    """The simulated supervisor's deterministic review policy (labelled simulated)."""
    lines = checklist.get("lines")
    passed = isinstance(lines, list) and all(isinstance(line, dict) and line.get("passed") for line in lines)
    if checklist.get("outcome") == Outcome.ADJUST.value and passed:
        return True, ""
    return False, "The stored checklist does not support this adjustment."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m benchmarks.agents.legacy_scripted")
    parser.add_argument("--split", default="dev", choices=("dev", "validation"))
    parser.add_argument("--cases", required=True, help="comma-separated case IDs (mechanics check only)")
    args = parser.parse_args(argv)

    from app.persistence.database import make_engine, make_sessions
    from app.settings import AppSettings
    from app.web.console import mock_systems_factory
    from benchmarks.intake import load_case, read_split

    settings = AppSettings.from_env()
    wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
    with make_sessions(make_engine(settings.database_url))() as s:
        agent = ScriptedLegacyAgent(
            s, mock_systems_factory(settings), LegacyRules.load(settings.customer_id), KeywordIndex.load()
        )
        for item in (c for c in read_split(args.split) if c.case_id in wanted):
            load_case(s, item)
            for case in s.scalars(select(Case).where(Case.source_ref == item.case_id).order_by(Case.id)):
                if case.status != CaseState.NEW.value:
                    print(f"{item.case_id} {case.reference}: already worked ({case.status}); skipped")
                    continue
                run = agent.run(case)
                print(f"{item.case_id} {run.case_reference}: {run.steps} steps, {run.elapsed_ms} ms ({run.label})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
