"""A language model, as the loop sees it (spec B.9; RFC-0002). Adapters: `app/adapters/mock_model.py`,
`anthropic_model.py`.

Messages are provider-neutral. An assistant turn keeps the provider's own content as `state`, passed back unchanged and
never written to the database: it can hold thinking blocks, and hidden reasoning isn't stored (AI-15).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

MODEL_DONE, MODEL_WANTS_TOOLS, MODEL_REFUSED, MODEL_TRUNCATED = "end_turn", "tool_use", "refusal", "max_tokens"


class ProviderUnavailable(Exception):
    """Overloaded, rate limited, timed out or unreachable. It may work later, within the loop's limit."""


class ProviderRejected(Exception):
    """The provider refused the request itself: bad credentials, an unknown model, an invalid request. No retry
    helps."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass(frozen=True)
class ModelTurn:
    stop_reason: str
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage = field(default_factory=Usage)
    state: Any = None


@dataclass(frozen=True)
class UserMessage:
    text: str


@dataclass(frozen=True)
class AssistantMessage:
    turn: ModelTurn


@dataclass(frozen=True)
class ToolResults:
    results: tuple[ToolResult, ...]


Message = UserMessage | AssistantMessage | ToolResults


class ModelProvider(Protocol):
    name: str
    model_id: str
    is_mock: bool

    def complete(
        self, system: str, messages: list[Message], tools: list[ToolSpec], max_tokens: int, timeout_seconds: float
    ) -> ModelTurn: ...

    def read_image(
        self, media_type: str, content: bytes, timeout_seconds: float
    ) -> tuple[dict[str, str | None], Usage]: ...
