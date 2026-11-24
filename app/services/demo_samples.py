"""Sample cases for the public demo (owner, 2026-11-23; SEC-18, LIVE-02).

After each daily reset (`app/demo_launch.py`), `python -m app.seed --sample-cases` puts a few synthetic cases in the
queue, so a visitor never lands on an empty one. They go through the normal intake, one per workflow, under a system
name (`system-demo-samples`), so the timeline shows the reset made them. Each carries a note saying what to try.

The messages are copies of three synthetic requests from the dataset's development split (the text only; no label,
expected outcome or generator detail comes with them). Their members and stays exist in the generated world the demo
image carries. The not-found sample names nobody in that
world. Every address is under `example.com`. `tests/test_demo_samples.py` checks, on the demo's live clock, that the
posting sample ends in a posting of 14,840 points, that the not-found sample asks for the membership number, and that
the arm A sample can be started; the arm C sample is checked only for being created.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.roles import Identity, Role
from app.persistence.models import Case, CaseNote
from app.services import cases as svc

SAMPLES_BY = "system-demo-samples"
SOURCE_PREFIX = "demo-sample:"
POSTING_SAMPLE, NOT_FOUND_SAMPLE, LEGACY_SAMPLE, AI_SAMPLE = "posting", "not-found", "legacy", "ai-reading"


@dataclass(frozen=True)
class Sample:
    key: str
    arm: str
    request: svc.IntakeRequest
    what_to_try: str


SAMPLES: tuple[Sample, ...] = (
    Sample(  # DV-001
        POSTING_SAMPLE,
        "B",
        svc.IntakeRequest(
            received_at_utc="2026-06-18T13:44:00Z",
            contact_channel="email",
            sender_email="clara.kowalski4@example.com",
            text=(
                "Hello, I stayed at Beach Resort from November 25-29, 2025 but the points are not on my account.\n"
                "Confirmation BR-6638.\nThanks, Clara Kowalski"
            ),
        ),
        "Live demo sample: this one goes all the way. As the agent, press Investigate, then Request adjustment. "
        "Then sign out, sign in as the supervisor, and Approve, then Execute adjustment.",
    ),
    Sample(
        NOT_FOUND_SAMPLE,
        "B",
        svc.IntakeRequest(
            received_at_utc="2026-07-20T14:00:00Z",
            contact_channel="phone_note",
            form_name="Jamie Rivera",
            text="Caller says the points for a June stay at Beach Resort never arrived. No member number given.",
        ),
        "Live demo sample: nobody by this name is in the synthetic world. Press Investigate to see the engine ask "
        "for the membership number instead of guessing.",
    ),
    Sample(  # DV-012
        LEGACY_SAMPLE,
        "A",
        svc.IntakeRequest(
            received_at_utc="2026-03-09T12:29:00Z",
            contact_channel="email",
            sender_email="michael.adeyemi3@example.com",
            text=(
                "Hello, I stayed at Mountain Lodge from May 30-31, 2025 but the points are not on my account.\n"
                "Confirmation ML-4462.\nThank you!\nMichael Adeyemi"
            ),
        ),
        "Live demo sample: the legacy workflow, worked by hand. Press Start work, then look up the member, the stay "
        "and the ledger on the old screens, the way agents did before.",
    ),
    Sample(  # DV-003
        AI_SAMPLE,
        "C",
        svc.IntakeRequest(
            received_at_utc="2026-08-26T21:44:00Z",
            contact_channel="web_form",
            sender_email="michael.ortega3@example.com",
            form_name="Michael Ortega",
            form_member_number="GR-43227",
            form_confirmation="7185",
            form_property="beach-resort",
            text=(
                "Hello, I stayed at Beach Resort from December 15-17, 2025 but the points are not on my account.\n"
                "Thanks, Michael Ortega"
            ),
        ),
        "Live demo sample: arm B plus an AI reading. Press Investigate to see the notes and draft reply. The AI is "
        "a mock here: no real model runs, and the rules decide the amount.",
    ),
)


def seed_samples(s: Session, customer_id: str = "hg-demo") -> int:
    """Add the sample cases when the customer has no cases at all (just after a reset). Returns how many were added;
    0 when the queue already has cases, so running it again never duplicates them."""
    if s.scalar(select(func.count(Case.id)).where(Case.customer_id == customer_id)):
        return 0
    who = Identity(0, SAMPLES_BY, "Demo samples", Role.AGENT, customer_id)  # never signs in
    for sample in SAMPLES:
        case = svc.create_case(
            s,
            who,
            sample.request,
            customer_id=customer_id,
            source_ref=SOURCE_PREFIX + sample.key,
            arm=sample.arm,
            commit=False,
        )
        s.add(CaseNote(case_id=case.id, author=SAMPLES_BY, body=sample.what_to_try, created_at_utc=utc_now()))
    s.commit()
    return len(SAMPLES)
