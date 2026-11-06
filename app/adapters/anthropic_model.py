"""Claude through the official SDK (RFC-0002). The key comes from the SDK's own environment lookup and never passes
here.

Haiku 5.5 runs adaptive thinking by default and rejects non-default sampling values, so neither is sent. It has no
server-side refusal fallback, so `refusal` is a stop condition in the loop. `tool_choice` is `auto`, with strict
schemas.
"""

from __future__ import annotations

from typing import Any

import anthropic

from app.ports.model_provider import (
    AssistantMessage,
    Message,
    ModelTurn,
    ProviderRejected,
    ProviderUnavailable,
    ToolCall,
    ToolResults,
    ToolSpec,
    Usage,
    UserMessage,
)

MAX_SDK_RETRIES = 1  # the loop counts failures itself; a long SDK backoff would eat its deadline


class AnthropicModel:
    name = "anthropic"
    is_mock = False

    def __init__(self, model_id: str, *, effort: str = "low", client: Any = None) -> None:
        self.model_id, self.effort = model_id, effort
        self.client = client if client is not None else anthropic.Anthropic(max_retries=MAX_SDK_RETRIES)

    @staticmethod
    def _wire(messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for message in messages:
            if isinstance(message, UserMessage):
                out.append({"role": "user", "content": message.text})
            elif isinstance(message, AssistantMessage):
                out.append({"role": "assistant", "content": message.turn.state})  # unchanged, thinking blocks included
            elif isinstance(message, ToolResults):
                blocks = [
                    {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content, "is_error": r.is_error}
                    for r in message.results
                ]
                out.append({"role": "user", "content": blocks})  # all results of a turn in one message
        return out

    def complete(
        self, system: str, messages: list[Message], tools: list[ToolSpec], max_tokens: int, timeout_seconds: float
    ) -> ModelTurn:
        try:
            create: Any = self.client.with_options(timeout=timeout_seconds).messages.create
            response = create(
                model=self.model_id,
                max_tokens=max_tokens,
                system=system,
                messages=self._wire(messages),
                tools=[
                    {"name": t.name, "description": t.description, "input_schema": t.input_schema, "strict": True}
                    for t in tools
                ],
                tool_choice={"type": "auto"},
                output_config={"effort": self.effort},
            )
        except (anthropic.RateLimitError, anthropic.APITimeoutError, anthropic.APIConnectionError) as exc:
            raise ProviderUnavailable(type(exc).__name__) from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ProviderUnavailable(f"status_{exc.status_code}") from exc
            raise ProviderRejected(f"status_{exc.status_code}") from exc
        calls = tuple(
            ToolCall(block.id, block.name, dict(block.input)) for block in response.content if block.type == "tool_use"
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = response.usage
        return ModelTurn(
            stop_reason=str(response.stop_reason),
            text=text,
            tool_calls=calls,
            usage=Usage(
                usage.input_tokens,
                usage.output_tokens,
                getattr(usage, "cache_read_input_tokens", 0) or 0,
                getattr(usage, "cache_creation_input_tokens", 0) or 0,
            ),
            state=response.content,
        )
