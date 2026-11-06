"""The AI documents exist and say what they must, including what hasn't been run (AI-01, ENT-01, ENT-02; honesty
rules)."""

from __future__ import annotations

from tests.conftest import ROOT


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_the_engineering_matrix_covers_every_discipline() -> None:
    text = read("docs/ai-engineering-matrix.md").lower()
    for word in (
        "prompt",
        "context",
        "tool",
        "agent",
        "loop",
        "workflow",
        "retrieval",
        "memory",
        "harness",
        "evaluation",
    ):
        assert f"| {word}" in text, word
    assert "reliability" in text and "human oversight" in text
    assert "no result in this table comes from a real model" in text


def test_the_system_card_says_what_hasnt_run_and_what_it_cant_do() -> None:
    text = read("docs/ai-system-card.md")
    assert "NOT RUN" in text and "Decide." in text and "Draft" in text
    assert "claude-haiku-5-5" in text and "Use-case register entry" in text


def test_the_model_card_doesnt_oversell_a_perfect_score() -> None:
    text = read("docs/model-card-routing.md")
    assert "Don't read 1.0" in text and "**NOT RUN" in text and "Blocked" in text


def test_the_arm_differences_cover_arm_c() -> None:
    text = read("docs/arm-differences.md")
    assert "## What arm C adds" in text and "can't decide" in text
