"""The runtime harness around the loop (spec B.9; AI-11, AI-12, LIVE-05, ENT-15): run records, steps, spending caps.

A run's record holds what ran and how it ended, never the content of evidence or the model's hidden reasoning.
Exactly-once business effects can't come from a checkpoint and aren't attempted here: the loop has no business
effects, and credits stay on the write path.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import correlation
from app.ai.config import AiConfig, ModelPrice, ai_config, load_prompt
from app.ai.loop import Budget, Loop, LoopResult, StepEvent, Stop
from app.ai.tools import ToolContext
from app.clock import utc_now
from app.domain.roles import Identity
from app.persistence.models import AiRun, AiSpend, AiStep, Case
from app.ports.model_provider import ModelProvider, ModelTurn, UserMessage
from app.services import jobs
from app.services.instrumentation import record

MICRO = 1_000_000
RUNNING, FINISHED, STOPPED = "running", "finished", "stopped"
UNKNOWN_MODEL = "unknown_model"
NO_PROVIDER = "no_provider"


@dataclass(frozen=True)
class SpendCaps:
    per_run_usd: float = 1.0
    daily_usd: float = 5.0
    monthly_usd: float = 5.0


@dataclass(frozen=True)
class AiRuntime:
    """What the settings allow. `provider` is None when live AI isn't properly set up: arm C then shows arm B's
    result."""

    provider: ModelProvider | None
    caps: SpendCaps = SpendCaps()
    unavailable_reason: str = ""

    @property
    def description(self) -> str:
        if self.provider is None:
            return f"unavailable ({self.unavailable_reason}), showing the rules result"
        kind = "MOCK" if self.provider.is_mock else "LIVE"
        return f"{kind} {self.provider.model_id}"


def periods(now: datetime | None = None) -> tuple[str, str]:
    moment = now or datetime.now(UTC)
    return f"day:{moment:%Y-%m-%d}", f"month:{moment:%Y-%m}"


def spent_microusd(s: Session, period: str) -> int:
    row = s.get(AiSpend, period, populate_existing=True)
    return row.cost_microusd if row else 0


def add_spend(s: Session, cost_microusd: int, now: datetime | None = None) -> None:
    """Add to both totals in one statement per row, so two runs at once can't lose an amount."""
    if cost_microusd <= 0:
        return
    for period in periods(now):
        if s.get(AiSpend, period) is None:
            try:
                with s.begin_nested():
                    s.add(AiSpend(period=period, cost_microusd=0, updated_at_utc=utc_now()))
            except IntegrityError:
                pass  # another run added it first
        s.execute(
            update(AiSpend)
            .where(AiSpend.period == period)
            .values(cost_microusd=AiSpend.cost_microusd + cost_microusd, updated_at_utc=utc_now())
        )
    s.commit()


def remaining_microusd(s: Session, caps: SpendCaps, now: datetime | None = None) -> int:
    day, month = periods(now)
    return min(
        int(caps.per_run_usd * MICRO),
        int(caps.daily_usd * MICRO) - spent_microusd(s, day),
        int(caps.monthly_usd * MICRO) - spent_microusd(s, month),
    )


def _price(config: AiConfig, provider: ModelProvider) -> ModelPrice | None:
    """A model that isn't listed, or is listed as deprecated, doesn't run (ENT-15)."""
    price = config.models.get(provider.model_id)
    return None if price is None or price.deprecated else price


def _start(
    s: Session, who: Identity, case: Case, provider: ModelProvider, prompt_version: str, versions: list[str]
) -> AiRun:
    run = AiRun(
        case_id=case.id,
        caller=who.username,
        provider=provider.name,
        model_id=provider.model_id,
        is_mock=provider.is_mock,
        prompt_version=prompt_version,
        policy_versions=versions,
        status=RUNNING,
        correlation_id=correlation.current(),
        started_at_utc=utc_now(),
    )
    s.add(run)
    s.commit()
    return run


def request_cancel(s: Session, case: Case) -> bool:
    """Ask the running loop to stop before its next step. Returns whether one was running."""
    run = s.scalars(
        select(AiRun).where(AiRun.case_id == case.id, AiRun.status == RUNNING).order_by(AiRun.id.desc()).limit(1)
    ).first()
    if run is None:
        return False
    run.cancel_requested = True
    s.commit()
    return True


def latest_run(s: Session, case: Case) -> AiRun | None:
    return s.scalars(select(AiRun).where(AiRun.case_id == case.id).order_by(AiRun.id.desc()).limit(1)).first()


def steps_of(s: Session, run: AiRun) -> list[AiStep]:
    return list(s.scalars(select(AiStep).where(AiStep.run_id == run.id).order_by(AiStep.step)))


def run_loop(
    s: Session,
    who: Identity,
    case: Case,
    runtime: AiRuntime,
    ctx: ToolContext,
    opening: UserMessage,
    policy_versions: list[str],
) -> tuple[AiRun | None, LoopResult]:
    provider = runtime.provider
    if provider is None:
        return None, LoopResult(Stop.PROVIDER_REJECTED, problems=[NO_PROVIDER])
    config = ai_config(case.customer_id)
    prompt = load_prompt()
    run = _start(s, who, case, provider, prompt.version, policy_versions)
    price = None if provider.is_mock else _price(config, provider)
    if not provider.is_mock and price is None:
        return run, _finish(
            s, case, run, LoopResult(Stop.PROVIDER_REJECTED, problems=[UNKNOWN_MODEL]), UNKNOWN_MODEL, 0
        )

    def priced(turn: ModelTurn) -> int:
        return 0 if price is None else price.cost_microusd(turn.usage.input_tokens, turn.usage.output_tokens)

    budget = Budget(None if provider.is_mock else remaining_microusd(s, runtime.caps), priced)
    step_number = [0]

    def on_step(event: StepEvent) -> None:
        step_number[0] += 1
        s.add(
            AiStep(
                run_id=run.id,
                step=step_number[0],
                kind=event.kind,
                name=event.name,
                arguments_hash=event.arguments_hash,
                status=event.status,
                result_chars=event.result_chars,
                elapsed_ms=event.elapsed_ms,
            )
        )
        s.commit()

    def on_turn(_turn: ModelTurn, cost: int) -> None:
        add_spend(s, cost)  # stored straight away, so a crash mid-run can't under-count

    def cancelled() -> bool:
        s.expire(run, ["cancel_requested"])
        asked = run.cancel_requested
        s.commit()  # no transaction stays open while the model thinks
        return asked

    started = time.monotonic()
    loop = Loop(
        provider, prompt.text, config.limits, ctx, budget, cancelled=cancelled, on_step=on_step, on_turn=on_turn
    )
    result = loop.run(opening)
    return run, _finish(s, case, run, result, result.stop.value, int((time.monotonic() - started) * 1000))


def _finish(s: Session, case: Case, run: AiRun, result: LoopResult, reason: str, elapsed_ms: int) -> LoopResult:
    run.status = FINISHED if result.proposal is not None else STOPPED
    run.stop_reason = reason
    run.turns, run.tool_calls = result.turns, result.tool_calls
    run.input_tokens, run.output_tokens = result.input_tokens, result.output_tokens
    run.cost_microusd = result.cost_microusd
    run.elapsed_ms = elapsed_ms
    run.problems = list(result.problems)
    run.finished_at_utc = utc_now()
    s.flush()
    record(s, case, jobs.SYSTEM, "ai_run_finished", run=run.id, stop=reason, turns=run.turns, mock=run.is_mock)
    s.commit()
    return result
