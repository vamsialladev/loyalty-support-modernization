"""GenAI span attribute names, in one place (spec L2, LIVE-03, ADR-0077).

Source: OpenTelemetry GenAI semantic conventions, `open-telemetry/semantic-conventions-genai`, read 2026-11-13. Their
status is **Development** (not stable), and the repository has no release yet; they moved out of the core
semantic-conventions repository in its v1.42.0. So every name lives here, and a rename is a one-file change.

Recorded: operation, provider, request and response model, input and output tokens, finish reasons, response ID, and
the duration (the span itself). **Never recorded:** `gen_ai.input.messages`, `gen_ai.output.messages`,
`gen_ai.system_instructions`, `gen_ai.tool.definitions` (all Opt-In in the conventions). Prompt and response text never
leave the AI harness through telemetry.
"""

from __future__ import annotations

from typing import Any

OPERATION_NAME = "gen_ai.operation.name"  # Required
PROVIDER_NAME = "gen_ai.provider.name"  # Required
REQUEST_MODEL = "gen_ai.request.model"  # Conditionally Required
RESPONSE_MODEL = "gen_ai.response.model"  # Recommended
RESPONSE_ID = "gen_ai.response.id"  # Recommended
FINISH_REASONS = "gen_ai.response.finish_reasons"  # Recommended, string[]
INPUT_TOKENS = "gen_ai.usage.input_tokens"  # Recommended
OUTPUT_TOKENS = "gen_ai.usage.output_tokens"  # Recommended
# Not in the conventions: this project's own, kept under its own prefix so it can't collide.
COST_MICROUSD = "loyalty.ai.cost_microusd"
CASE_ID = "loyalty.case.id"

CHAT = "chat"
# Content attributes the conventions define. Listed so a test can prove none of them is ever set.
CONTENT_KEYS = frozenset(
    {
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.system_instructions",
        "gen_ai.tool.definitions",
        "gen_ai.tool.call.arguments",
        "gen_ai.tool.call.result",
    }
)
# The conventions list well-known provider names; the mock is ours, so it gets a name that can't be mistaken for one.
PROVIDERS = {"anthropic": "anthropic", "mock": "loyalty.mock"}


def span_name(operation: str, model: str) -> str:
    """`{gen_ai.operation.name} {gen_ai.request.model}`, as the client-inference page says."""
    return f"{operation} {model}".strip()


def request_attributes(provider: str, model: str, case_id: int | None = None) -> dict[str, Any]:
    attrs: dict[str, Any] = {OPERATION_NAME: CHAT, PROVIDER_NAME: PROVIDERS.get(provider, provider)}
    if model:
        attrs[REQUEST_MODEL] = model
    if case_id is not None:
        attrs[CASE_ID] = case_id
    return attrs


def response_attributes(
    *,
    model: str = "",
    response_id: str = "",
    finish_reason: str = "",
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_microusd: int | None = None,
) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    if model:
        attrs[RESPONSE_MODEL] = model
    if response_id:
        attrs[RESPONSE_ID] = response_id
    if finish_reason:
        attrs[FINISH_REASONS] = (finish_reason,)
    if input_tokens is not None:
        attrs[INPUT_TOKENS] = input_tokens
    if output_tokens is not None:
        attrs[OUTPUT_TOKENS] = output_tokens
    if cost_microusd is not None:
        attrs[COST_MICROUSD] = cost_microusd
    return attrs
