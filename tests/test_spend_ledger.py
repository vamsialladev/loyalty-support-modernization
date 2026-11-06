"""The $5 cap is a stop in code, and the ledger only ever grows (BENCH-10; RFC-0003). No network here."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluations.spend import CapReached, record, require_room, spent_usd


@pytest.fixture
def ledger(tmp_path: Path) -> Path:
    return tmp_path / "live" / "spend-ledger.jsonl"


def test_an_empty_ledger_has_spent_nothing(ledger: Path) -> None:
    assert spent_usd(ledger) == 0.0


def test_spending_adds_up_across_runs(ledger: Path) -> None:
    record("smoke", "smoke-1", "m", 10, 5, 0.001, ledger)
    record("evaluation", "run-1", "m", 10, 5, 0.25, ledger)
    assert spent_usd(ledger) == pytest.approx(0.251)


def test_entries_are_added_never_replaced(ledger: Path) -> None:
    record("smoke", "one", "m", 1, 1, 0.5, ledger)
    first = ledger.read_text(encoding="utf-8")
    record("smoke", "two", "m", 1, 1, 0.5, ledger)
    assert ledger.read_text(encoding="utf-8").startswith(first)


def test_a_call_that_could_pass_the_cap_doesnt_happen(ledger: Path) -> None:
    record("evaluation", "run", "m", 1, 1, 4.99, ledger)
    require_room(0.01, 5.0, ledger=ledger)
    with pytest.raises(CapReached, match="the cap is"):
        require_room(0.02, 5.0, ledger=ledger)


def test_the_worst_case_counts_not_the_likely_cost(ledger: Path) -> None:
    with pytest.raises(CapReached):
        require_room(5.01, 5.0, ledger=ledger)


def test_other_work_cant_eat_the_held_out_reserve(ledger: Path) -> None:
    record("evaluation", "dev", "m", 1, 1, 2.40, ledger)
    require_room(0.10, 5.0, reserve_usd=2.50, ledger=ledger)
    with pytest.raises(CapReached, match="reserved"):
        require_room(0.11, 5.0, reserve_usd=2.50, ledger=ledger)


def test_held_out_itself_can_use_the_reserve(ledger: Path) -> None:
    record("evaluation", "dev", "m", 1, 1, 2.50, ledger)
    require_room(2.50, 5.0, ledger=ledger)


def test_a_negative_cost_cant_buy_room(ledger: Path) -> None:
    with pytest.raises(ValueError, match="negative"):
        record("evaluation", "run", "m", 1, 1, -1.0, ledger)
    with pytest.raises(ValueError, match="negative"):
        require_room(-1.0, 5.0, ledger=ledger)


def test_unknown_kinds_are_refused(ledger: Path) -> None:
    with pytest.raises(ValueError, match="unknown kind"):
        record("mock", "run", "m", 1, 1, 0.0, ledger)


def test_the_ledger_holds_no_message_or_key(ledger: Path) -> None:
    record("smoke", "one", "claude-haiku-5-5", 10, 5, 0.001, ledger)
    keys = '"at_utc", "cost_usd", "input_tokens", "kind", "model", "output_tokens", "run"'
    text = ledger.read_text(encoding="utf-8")
    assert all(f'"{name}"' in text for name in keys.replace('"', "").split(", "))
    assert "key" not in text and "message" not in text
