# Live smoke test, 2026-11-07

> **LIVE PROVIDER SMOKE TEST. Not an evaluation, and not evidence of quality** (spec E.5). One made-up message, with no case data. SYNTHETIC project.

| Field | Value |
|---|---|
| Command | `$env:LIVE_AI_SMOKE="yes"; uv run python scripts/live_smoke_ai.py --env-file .env` |
| Code | `2b3bb16` |
| Model | `claude-haiku-5-5` |
| Result | **PASS** |
| Stop reason | `tool_use` |
| Tools called | `get_member` (the one expected) |
| Tokens | 1,389 in, 26 out |
| Cost at list price | $0.000152 (`config/ai/hg-demo.yaml`; the Anthropic Console is the record of what was charged) |
| Spent against the $5 cap after this | $0.000152 (`benchmarks/results/live/spend-ledger.jsonl`) |

**What this shows:** the adapter's request shape and the tool-call round trip work, and the key and model ID are good.

**What this doesn't show:** anything about arm C's quality, cost per case or latency on real cases. Milestone 10's live evaluation measures those.
