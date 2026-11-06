"""A prompt can't change quietly (AI-02): its hash is pinned per version. To change the text, add a new version file.

Which version is better gets decided on held-out cases with a live model (Milestone 10), never from a few demos.
"""

from __future__ import annotations

import hashlib

from app.ai.config import load_prompt
from tests.conftest import ROOT

PINNED = {"arm_c_v1": "01a2b2dc634dd2b3e1869bad8e304a8f71fa5fe306c85f27df61c3b62972b05f"}


def test_the_prompt_text_matches_its_version() -> None:
    prompt = load_prompt("arm_c_v1")
    digest = hashlib.sha256(prompt.text.encode()).hexdigest()
    assert prompt.version in PINNED
    assert digest == PINNED[prompt.version], "the text changed: add a new version file instead of editing this one"


def test_the_prompt_file_says_it_is_data_and_keeps_authorization_out() -> None:
    text = (ROOT / "config/prompts/arm_c_v1.md").read_text(encoding="utf-8").lower()
    assert "isn't an instruction" in text
    assert "rules engine makes every decision" in text
    for word in ("password", "api key", "you may approve", "you can approve"):
        assert word not in text
