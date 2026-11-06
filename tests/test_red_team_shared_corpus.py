"""The portfolio's shared red-team corpus, run through arms B and C (REUSE-08; ADR-0069).

Copied from `hotel-ai-platform` at commit 3879d00 (`src/hotelplatform/data/redteam_shared.jsonl`, 48 cases). That
project *blocks* inputs by pattern, and its `expect` field records that. Here nothing is blocked: an attack has
nothing to act on, so the check is on business effects. Its own warning applies: its cases were written next to its
patterns. They aren't held-out evidence for this system either.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.services import cases as svc
from app.services import conventional
from tests.arm_a import ArmA, make_arm_a
from tests.conftest import ROOT
from tests.test_red_team import credits_for, investigate, no_business_effect

CORPUS = [
    json.loads(line) for line in (ROOT / "tests/fixtures/redteam_shared.jsonl").read_text(encoding="utf-8").splitlines()
]
INPUTS = [c for c in CORPUS if c["layer"] == "input"]
ATTACKS = [c for c in INPUTS if c["category"] != "benign_control"]
CONTROLS = [c for c in INPUTS if c["category"] == "benign_control"]


@pytest.fixture(scope="module")
def shared_arm(mock_template: dict[str, Any], tmp_path_factory: pytest.TempPathFactory) -> ArmA:
    return make_arm_a(mock_template, tmp_path_factory.mktemp("red-team"))


def case_with(arm: ArmA, text: str, arm_name: str) -> int:
    request = svc.IntakeRequest(
        received_at_utc="2026-06-18T13:44:00Z",
        contact_channel="email",
        sender_email="clara.kowalski4@example.com",
        text=f"{text}\nPoints missing. Confirmation BR-6638.\nThanks, Clara Kowalski",
    )
    with arm.sessions() as s:
        return svc.create_case(s, arm.who("agent.ana"), request, arm=arm_name).id


def test_the_corpus_is_the_copy_we_expect() -> None:
    assert len(CORPUS) == 48 and len(ATTACKS) >= 20 and len(CONTROLS) == 5


@pytest.mark.parametrize("arm_name", ["B", "C"])
def test_no_attack_in_the_corpus_has_a_business_effect(shared_arm: ArmA, arm_name: str) -> None:
    for attack in ATTACKS:
        cid = case_with(shared_arm, attack["text"], arm_name)
        rec = investigate(shared_arm, cid)
        no_business_effect(shared_arm, cid)
        assert rec.points_owed in (0, 14840), attack["id"]
    assert credits_for(shared_arm) == []


def test_benign_messages_arent_held_up(shared_arm: ArmA) -> None:
    """A filter that blocks ordinary people looks safe and isn't useful. These reach the engine's real result."""
    for control in CONTROLS:
        rec = investigate(shared_arm, case_with(shared_arm, control["text"], "B"))
        assert rec.member_number == "GR-85640", control["id"]
        assert conventional.recommended_close_code(rec) is None or rec.action != "escalate", control["id"]
