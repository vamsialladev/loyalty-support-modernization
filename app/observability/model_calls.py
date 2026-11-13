"""A span around every model call, with the GenAI attributes and never the content (spec L2; LIVE-03, ADR-0077).

Wraps any `ModelProvider`, so the loop and the adapters don't change. A failure records the exception's type as
`error.type` and nothing from its message, which can quote the request.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from opentelemetry.trace import SpanKind, Status, StatusCode

from app.observability import genai, tracing
from app.ports.model_provider import Message, ModelProvider, ModelTurn, ToolSpec, Usage

ERROR_TYPE = "error.type"  # a stable OpenTelemetry attribute


@dataclass
class TracedProvider:
    inner: ModelProvider
    case_id: int | None = None
    cost: Callable[[ModelTurn], int] | None = None
    name: str = field(init=False)
    model_id: str = field(init=False)
    is_mock: bool = field(init=False)

    def __post_init__(self) -> None:
        self.name, self.model_id, self.is_mock = self.inner.name, self.inner.model_id, self.inner.is_mock

    def _span(self) -> Any:
        return tracing.tracer("app.ai").start_as_current_span(
            genai.span_name(genai.CHAT, self.model_id),
            kind=SpanKind.CLIENT,
            attributes=genai.request_attributes(self.name, self.model_id, self.case_id),
            record_exception=False,
            set_status_on_exception=False,
        )

    def complete(
        self, system: str, messages: list[Message], tools: list[ToolSpec], max_tokens: int, timeout_seconds: float
    ) -> ModelTurn:
        with self._span() as span:
            try:
                turn = self.inner.complete(system, messages, tools, max_tokens, timeout_seconds)
            except Exception as exc:
                span.set_attribute(ERROR_TYPE, type(exc).__name__)
                span.set_status(Status(StatusCode.ERROR))
                raise
            span.set_attributes(
                genai.response_attributes(
                    model=self.model_id,
                    finish_reason=turn.stop_reason,
                    input_tokens=turn.usage.input_tokens,
                    output_tokens=turn.usage.output_tokens,
                    cost_microusd=self.cost(turn) if self.cost else None,
                )
            )
            return turn

    def read_image(
        self, media_type: str, content: bytes, timeout_seconds: float
    ) -> tuple[dict[str, str | None], Usage]:
        with self._span() as span:
            try:
                fields, usage = self.inner.read_image(media_type, content, timeout_seconds)
            except Exception as exc:
                span.set_attribute(ERROR_TYPE, type(exc).__name__)
                span.set_status(Status(StatusCode.ERROR))
                raise
            span.set_attributes(
                genai.response_attributes(
                    model=self.model_id, input_tokens=usage.input_tokens, output_tokens=usage.output_tokens
                )
            )
            return fields, usage
