"""Milestone 13, L3: provider prompt caching, flag off by default (CACHE-02, ENT-17, ADR-0089, ADR-0090).

Written before the code. What has to hold:
- the request is byte-for-byte the same with and without caching, apart from the one top-level `cache_control`;
- nothing turns it on except the flag, and the kill switch turns it off without a restart;
- cached tokens are priced and counted against the caps, so a cap can't be passed by caching;
- runs, the spend ledger, spans and metrics carry the cache tokens.
No network, no key: the Anthropic client is fake.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.adapters.anthropic_model import AnthropicModel
from app.adapters.circuit import CircuitBreaker
from app.adapters.circuit import GuardedModel as CircuitGuarded
from app.adapters.mock_model import ScriptedModel, wants
from app.ai.config import ModelPrice, ai_config
from app.ai.harness import AiRuntime, SpendCaps, periods, run_loop, spent_microusd
from app.ai.loop import Stop
from app.domain.roles import NotPermitted
from app.observability import genai
from app.observability.model_calls import TracedProvider
from app.ports.model_provider import ModelTurn, Usage, UserMessage
from app.services import prompt_cache
from app.services.assisted import runtime_from_settings
from app.services.cases import WorkflowError
from app.settings import AppSettings
from evaluations.live_model import GuardedModel as LedgerGuarded
from tests.arm_a import ArmA
from tests.test_ai_loop import context, proposal
from tests.test_ai_provider import FakeClient, LiveLike, _case, arm, complete, response, tool_block  # noqa: F401
from tests.test_observability import spans  # noqa: F401

HAIKU = "claude-haiku-5-5"


def _cached_response(read: int, write: int, plain: int = 11) -> Any:
    out = response(tool_block())
    out.usage = SimpleNamespace(
        input_tokens=plain, output_tokens=7, cache_read_input_tokens=read, cache_creation_input_tokens=write
    )
    return out


def _submit(input_tokens: int = 1000, output_tokens: int = 100, read: int = 0, write: int = 0) -> ModelTurn:
    turn = wants(
        SimpleNamespace(
            call_id="s",
            name="submit_recommendation",
            arguments=proposal(stay_ids=[], recommended_action="request_info", missing_information=["x"]),
        ),  # type: ignore[arg-type]
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    return ModelTurn(
        turn.stop_reason, tool_calls=turn.tool_calls, usage=Usage(input_tokens, output_tokens, read, write)
    )


# ---------- the adapter ----------


def test_the_request_is_identical_apart_from_one_cache_marker() -> None:
    plain, cached = FakeClient(response(tool_block())), FakeClient(response(tool_block()))
    complete(AnthropicModel(HAIKU, client=plain))
    AnthropicModel(HAIKU, client=cached).complete("system text", [UserMessage("hello")], *_rest(), prompt_cache=True)
    sent_plain, sent_cached = dict(plain.messages.kwargs), dict(cached.messages.kwargs)
    assert "cache_control" not in sent_plain
    assert sent_cached.pop("cache_control") == {"type": "ephemeral"}  # the 5-minute cache, automatic breakpoint
    assert json.dumps(sent_cached, sort_keys=True, default=str) == json.dumps(sent_plain, sort_keys=True, default=str)


def _rest() -> tuple[Any, ...]:
    from app.ai.tools import TOOL_SPECS

    return (list(TOOL_SPECS), 500, 12.5)


def test_caching_is_off_unless_the_call_asks_for_it() -> None:
    client = FakeClient(response(tool_block()))
    complete(AnthropicModel(HAIKU, client=client))
    assert "cache_control" not in client.messages.kwargs


def test_reading_a_document_is_never_cached() -> None:
    image = SimpleNamespace(type="tool_use", id="t", name="report_fields", input={})
    client = FakeClient(response(image))
    AnthropicModel(HAIKU, client=client).read_image("image/png", b"\x89PNG", 5.0)
    assert "cache_control" not in client.messages.kwargs


def test_the_cache_token_counts_come_back_from_the_response() -> None:
    client = FakeClient(_cached_response(read=1800, write=300))
    turn = AnthropicModel(HAIKU, client=client).complete("s", [UserMessage("h")], *_rest(), prompt_cache=True)
    assert (turn.usage.input_tokens, turn.usage.cache_read_tokens, turn.usage.cache_write_tokens) == (11, 1800, 300)


def test_wrappers_pass_the_request_on() -> None:
    inner = ScriptedModel([wants(), wants()], model_id=HAIKU)
    CircuitGuarded(inner, CircuitBreaker("test")).complete("s", [UserMessage("h")], [], 100, 5.0, prompt_cache=True)
    TracedProvider(inner).complete("s", [UserMessage("h")], [], 100, 5.0, prompt_cache=True)
    assert inner.cache_requests == [True, True]


# ---------- prices and caps ----------


def test_cached_tokens_are_priced_at_their_own_rates() -> None:
    price = ai_config("hg-demo").models[HAIKU]
    assert (price.cache_write_per_mtok, price.cache_read_per_mtok) == (0.125, 0.01)
    # 1,000 plain at $0.10, 100 out at $0.50, 2,000 read at $0.01, 400 written at $0.125 (per million): 220 micro-USD
    assert price.cost_microusd(1000, 100, cache_read=2000, cache_write=400) == 100 + 50 + 20 + 50
    assert price.usage_cost_microusd(Usage(1000, 100, 2000, 400)) == 220


def test_without_cache_prices_cached_tokens_cost_the_most_a_write_can() -> None:
    price = ModelPrice(input_per_mtok=1.0, output_per_mtok=5.0, checked_on="2026-11-26")
    # Unknown rates mustn't let a cap be passed: 2x the input price, the 1-hour write rate, the highest there is.
    assert price.cost_microusd(0, 0, cache_read=1000, cache_write=1000) == 4000
    assert price.worst_input_per_mtok == 2.0


def test_the_worst_case_check_assumes_every_input_token_could_be_a_write() -> None:
    price = ai_config("hg-demo").models[HAIKU]
    assert price.worst_input_per_mtok == 0.125


# ---------- the harness: flag, kill switch, records, caps ----------


def test_the_flag_is_off_by_default_and_reaches_the_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.delenv("FEATURE_PROMPT_CACHE", raising=False)
    assert AppSettings.from_env().feature_prompt_cache is False
    monkeypatch.setenv("FEATURE_PROMPT_CACHE", "true")
    on = AppSettings.from_env()
    assert on.feature_prompt_cache is True
    # A live runtime carries the flag; without live AI there's no provider to ask.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-key")
    live = replace(on, ai_provider="anthropic", feature_live_ai=True, anthropic_model=HAIKU)
    assert runtime_from_settings(live).prompt_cache is True
    assert runtime_from_settings(replace(live, feature_prompt_cache=False)).prompt_cache is False


def test_a_run_asks_for_caching_only_when_the_runtime_allows_it(arm: ArmA) -> None:  # noqa: F811
    for allowed in (False, True):
        model = ScriptedModel([_submit()])
        with arm.sessions() as s:
            run_loop(
                s,
                arm.who("agent.ana"),
                _case(arm, s),
                AiRuntime(model, prompt_cache=allowed),
                context(),
                UserMessage("x"),
                [],
            )
        assert model.cache_requests == [allowed]


def test_the_kill_switch_turns_caching_off_without_a_restart(arm: ArmA) -> None:  # noqa: F811
    model = ScriptedModel([_submit(), _submit()])
    with arm.sessions() as s:
        assert prompt_cache.is_killed(s) is False  # no row yet: the flag decides
        run_loop(
            s, arm.who("agent.ana"), _case(arm, s), AiRuntime(model, prompt_cache=True), context(), UserMessage("x"), []
        )
        prompt_cache.set_killed(s, arm.who("admin.ada"), True, "a cost spike on the dashboard")
        assert prompt_cache.is_killed(s) is True
        run_loop(
            s, arm.who("agent.ana"), _case(arm, s), AiRuntime(model, prompt_cache=True), context(), UserMessage("x"), []
        )
    assert model.cache_requests == [True, False]


def test_only_an_administrator_with_a_reason_can_change_the_switch(arm: ArmA) -> None:  # noqa: F811
    with arm.sessions() as s:
        with pytest.raises(NotPermitted):
            prompt_cache.set_killed(s, arm.who("agent.ana"), True, "a cost spike on the dashboard")
        with pytest.raises(WorkflowError):
            prompt_cache.set_killed(s, arm.who("admin.ada"), True, "why")
        row = prompt_cache.set_killed(s, arm.who("admin.ada"), True, "a cost spike on the dashboard")
        assert row.changed_by == "admin.ada" and row.reason == "a cost spike on the dashboard"


def test_a_run_records_cache_tokens_and_their_cost_counts_against_the_caps(arm: ArmA) -> None:  # noqa: F811
    model = LiveLike([_submit(1000, 100, read=2000, write=400)], model_id=HAIKU)
    with arm.sessions() as s:
        runtime = AiRuntime(model, SpendCaps(1.0, 1.0, 1.0), prompt_cache=True)
        run, result = run_loop(s, arm.who("agent.ana"), _case(arm, s), runtime, context(), UserMessage("x"), [])
        assert result.stop is Stop.MISSING_INFORMATION and run is not None
        assert (run.input_tokens, run.cache_read_tokens, run.cache_write_tokens) == (1000, 2000, 400)
        assert run.cost_microusd == 220 and spent_microusd(s, periods()[0]) == 220


def test_the_benchmark_guard_prices_and_records_cache_tokens(tmp_path: Path) -> None:
    ledger = tmp_path / "spend.jsonl"
    inner = LiveLike([_submit(1000, 100, read=2000, write=400)], model_id=HAIKU)
    price = ai_config("hg-demo").models[HAIKU]
    guarded = LedgerGuarded(inner, price, cap_usd=1.0, run_limit_usd=0.5, ledger=ledger, run_name="t")
    guarded.complete("s", [UserMessage("h")], [], 100, 5.0, prompt_cache=True)
    (row,) = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert (row["input_tokens"], row["cache_read_tokens"], row["cache_write_tokens"]) == (1000, 2000, 400)
    assert row["cost_usd"] == pytest.approx(0.00022)
    assert inner.cache_requests == [True]


# ---------- spans ----------


def test_spans_carry_cache_tokens_and_the_total_input(spans: InMemorySpanExporter) -> None:  # noqa: F811
    inner = ScriptedModel([_submit(1000, 100, read=2000, write=400)], model_id=HAIKU)
    TracedProvider(inner).complete("s", [UserMessage("h")], [], 100, 5.0, prompt_cache=True)
    (span,) = [x for x in spans.get_finished_spans() if x.name == f"chat {HAIKU}"]
    attrs = dict(span.attributes or {})
    # GenAI conventions v0.1.0: input tokens SHOULD include cached ones; the cache counts are their own attributes.
    assert attrs[genai.INPUT_TOKENS] == 3400
    assert attrs[genai.CACHE_READ_INPUT_TOKENS] == 2000 and attrs[genai.CACHE_WRITE_INPUT_TOKENS] == 400


def test_a_call_without_caching_sets_no_cache_attributes(spans: InMemorySpanExporter) -> None:  # noqa: F811
    TracedProvider(ScriptedModel([_submit()], model_id=HAIKU)).complete("s", [UserMessage("h")], [], 100, 5.0)
    (span,) = [x for x in spans.get_finished_spans() if x.name == f"chat {HAIKU}"]
    attrs = dict(span.attributes or {})
    assert attrs[genai.INPUT_TOKENS] == 1000
    assert genai.CACHE_READ_INPUT_TOKENS not in attrs and genai.CACHE_WRITE_INPUT_TOKENS not in attrs


# ---------- the admin page, the dashboard and the gauge ----------


def test_the_admin_page_shows_the_state_and_only_an_administrator_can_switch_it_off(arm: ArmA) -> None:  # noqa: F811
    from tests.test_security_authz import browser

    admin = browser(arm, "admin.ada", feature_prompt_cache=True)
    page = admin.get("/admin").text
    assert "Prompt caching is <strong>on</strong>" in page
    agent = browser(arm, "agent.ana")
    assert agent.post("/admin/prompt-cache", kill="on", reason="a cost spike on the dashboard").status_code == 403
    admin.get("/admin")
    assert admin.post("/admin/prompt-cache", kill="on", reason="a cost spike on the dashboard").status_code == 200
    page = admin.get("/admin").text
    assert "Prompt caching is <strong>off</strong>" in page and "the switch below has turned it off" in page
    with arm.sessions() as s:
        assert prompt_cache.is_killed(s) is True


def test_the_dashboard_and_the_gauge_report_cache_tokens(arm: ArmA) -> None:  # noqa: F811
    from app.observability import ops_metrics
    from app.services import metrics

    model = LiveLike([_submit(1000, 100, read=2000, write=400)], model_id=HAIKU)
    with arm.sessions() as s:
        run_loop(
            s, arm.who("agent.ana"), _case(arm, s), AiRuntime(model, prompt_cache=True), context(), UserMessage("x"), []
        )
        rows = [r for r in metrics.collect(s, arm.who("supervisor.sam")).rows if r.arm == "C"]
        assert [(r.ai_cache_read_tokens, r.ai_cache_write_tokens, r.ai_input_tokens) for r in rows] == [
            (2000, 400, 3400)
        ]
        assert ops_metrics.snapshot(s)["ai_cache_tokens"] == {"read": 2000, "write": 400, "input": 3400}
