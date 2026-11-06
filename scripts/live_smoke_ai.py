"""The Claude provider's live smoke test (Appendix C, M8): one small real call, with a hard limit on its cost.

    uv run python scripts/live_smoke_ai.py            # says NOT RUN and why, unless it's asked for and set up
    $env:LIVE_AI_SMOKE="yes"; uv run python scripts/live_smoke_ai.py --env-file .env

**It spends real money: a few hundredths of a cent.** It runs only with `LIVE_AI_SMOKE=yes`, `ANTHROPIC_API_KEY` and
`ANTHROPIC_MODEL`. The model must be on the allowed list in `config/ai/`. It prints pass or fail, the model, tokens
and cost, and never the key. It sends a made-up message only: no case data. It proves the adapter's request shape and
tool call round trip, not the model's quality.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from app.ai.config import ai_config  # noqa: E402
from app.ai.tools import TOOL_SPECS  # noqa: E402
from app.ports.model_provider import ProviderRejected, ProviderUnavailable, UserMessage  # noqa: E402

MAX_OUTPUT_TOKENS = 300


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    args = parser.parse_args(argv)
    load_dotenv(args.env_file)  # never overrides a variable that's already set; values are never printed
    if os.environ.get("LIVE_AI_SMOKE") != "yes":
        print("NOT RUN: set LIVE_AI_SMOKE=yes to spend real money on one small call")
        return 0
    model_id = os.environ.get("ANTHROPIC_MODEL", "").strip()
    if not model_id or not os.environ.get("ANTHROPIC_API_KEY"):
        print("NOT RUN: ANTHROPIC_MODEL or ANTHROPIC_API_KEY isn't set")
        return 0
    price = ai_config("hg-demo").models.get(model_id)
    if price is None:
        print(f"NOT RUN: {model_id} isn't on the allowed list in config/ai/hg-demo.yaml")
        return 0

    from app.adapters.anthropic_model import AnthropicModel

    model = AnthropicModel(model_id)
    system = "You test a tool connection. Call get_member with no arguments, and nothing else."
    try:
        turn = model.complete(
            system, [UserMessage("Please check the member.")], list(TOOL_SPECS), MAX_OUTPUT_TOKENS, 30.0
        )
    except (ProviderUnavailable, ProviderRejected) as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    cost = price.cost_microusd(turn.usage.input_tokens, turn.usage.output_tokens) / 1_000_000
    called = [c.name for c in turn.tool_calls]
    print(f"model {model_id}: stop_reason={turn.stop_reason}, tools={called}")
    print(f"tokens in {turn.usage.input_tokens}, out {turn.usage.output_tokens}; cost at the listed price ${cost:.6f}")
    if called != ["get_member"]:
        print("FAIL: the model didn't make the expected tool call")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
