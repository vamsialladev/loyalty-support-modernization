"""Thresholds match what was pre-registered, and configurations can't exceed the owner's cap (BENCH-01, -02, -11)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
import yaml

from evaluations.run_config import ConfigError, RunConfig, check, hard_cap_usd, load
from tests.conftest import ROOT

HYPOTHESES = (ROOT / "docs" / "hypotheses.md").read_text(encoding="utf-8")
THRESHOLDS: dict[str, Any] = yaml.safe_load((ROOT / "benchmarks/benchmark-thresholds.yaml").read_text(encoding="utf-8"))
ALL = ("arm-a", "arm-a-as-is", "arm-b", "arm-c-mock", "arm-c-live")
MINUS = "\u2212"  # as the pre-registered document writes it


def _row(hypothesis: str) -> str:
    return next(line for line in HYPOTHESES.splitlines() if line.startswith(f"| **{hypothesis}** |"))


def test_each_threshold_is_the_one_pre_registered() -> None:
    h = THRESHOLDS["hypotheses"]
    assert f"B {MINUS} A ≥ **{h['H1']['min_difference_pp']} percentage points**" in _row("H1")
    assert f"C {MINUS} B ≥ **{h['H2']['min_difference_pp']} pp**" in _row("H2")
    assert f"B {MINUS} C ≥ **{h['H3']['min_difference_pp']} pp**" in _row("H3")
    assert f"(a) C {MINUS} B ≥ **{h['H4']['min_difference_pp']} pp**" in _row("H4")
    assert f"C ≤ B {MINUS} **{h['H4']['contacts_margin']} contacts**" in _row("H4")
    assert f"**${h['H5']['cost_per_correct_case_usd_max']}** per correctly resolved case" in _row("H5")
    assert f"≤ **{h['H5']['investigation_latency_p95_seconds_max']} s**" in _row("H5")
    assert h["H6"]["unauthorized_actions_max"] == 0 and h["H6"]["duplicate_credits_max"] == 0
    assert "**0** of each" in _row("H6")
    assert f"C ≤ **{round(h['H7']['max_ratio'] * 100)}%** of B's median" in _row("H7")
    assert f"fewer than {h['H7']['min_participants']} participants" in _row("H7")


def test_the_statistics_are_the_ones_pre_registered() -> None:
    stats = THRESHOLDS["statistics"]
    assert f"{stats['resamples']:,} resamples, fixed seed {stats['seed']}, {stats['interval_percent']}%" in HYPOTHESES


def test_the_thresholds_say_nobody_has_approved_them() -> None:
    assert THRESHOLDS["status"] == "provisional" and THRESHOLDS["approved_by_stakeholder"] is False


def test_the_cap_is_the_owners() -> None:
    assert hard_cap_usd() == 5.00
    assert "hard cap of $5 total" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert THRESHOLDS["live_spend"]["heldout_reserve_usd"] <= hard_cap_usd()


@pytest.mark.parametrize("name", ALL)
def test_every_configuration_loads_and_passes_its_checks(name: str) -> None:
    assert load(name).dataset_version == "v1"


def test_results_go_to_separate_places_by_kind() -> None:
    assert load("arm-b").kind == "deterministic"
    assert load("arm-c-mock").kind == "mock"
    assert load("arm-c-live").kind == "live"


@pytest.fixture
def live() -> RunConfig:
    return load("arm-c-live")


def test_a_live_run_with_no_ceiling_never_starts(live: RunConfig) -> None:
    with pytest.raises(ConfigError, match="ceiling"):
        check(replace(live, cost_ceiling_usd=None), 5.0)
    with pytest.raises(ConfigError, match="ceiling"):
        check(replace(live, cost_ceiling_usd=0.0), 5.0)


def test_a_ceiling_above_the_cap_never_starts(live: RunConfig) -> None:
    with pytest.raises(ConfigError, match="owner's cap"):
        check(replace(live, cost_ceiling_usd=5.01), 5.0)


def test_a_live_run_names_its_model(live: RunConfig) -> None:
    with pytest.raises(ConfigError, match="model"):
        check(replace(live, model=None), 5.0)


def test_a_mock_run_cant_look_like_one_that_spends_money() -> None:
    with pytest.raises(ConfigError, match="only a live run"):
        check(replace(load("arm-c-mock"), cost_ceiling_usd=1.0), 5.0)


def test_only_arm_c_uses_a_model() -> None:
    with pytest.raises(ConfigError, match="doesn't use a model"):
        check(replace(load("arm-b"), provider="live"), 5.0)
    with pytest.raises(ConfigError, match="needs a provider"):
        check(replace(load("arm-c-mock"), provider="none"), 5.0)


def test_a_missing_field_is_named(tmp_path: Any) -> None:
    (tmp_path / "broken.yaml").write_text("arm: B\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="cost_ceiling_usd"):
        load("broken", tmp_path, 5.0)
