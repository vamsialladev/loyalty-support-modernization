# Milestone 13, Phase 3: pre-registered plan for the live runs (CACHE-03)

> Written and committed **before** any live run, so the arms, metrics and pass marks can't move after seeing results.
> Real model (claude-haiku-5-5), SYNTHETIC cases, members and messages. Nothing here runs until the owner approves
> the cost below.

## What is compared
Only L3 was built (ADR-0089, owner's gate 2026-11-26), so the brief's four arms reduce to two. The others are
**not run, because those layers weren't built**, and the reports say so:

| Arm in the brief | Here | Configuration |
|---|---|---|
| A: no cache | **A** | `benchmarks/configs/arm-c-live.yaml` (arm C as frozen in Milestone 10) |
| B: exact | not run: L1 not built | — |
| C: exact + semantic | not run: L1, L2 not built | — |
| D: all supported layers | **D = A + L3** | `benchmarks/configs/arm-c-live-prompt-cache.yaml`; differs from A only in `prompt_cache: true` and `cache_state` |

- **Cases:** the frozen held-out split, 80 cases, dataset v1 (SHA-256 in its manifest). Its labels have been public
  since 2026-11-13, so this is a **paired regression comparison between A and D on the same code**, not a held-out
  claim (`CLAUDE.md`).
- **Runs:** 3 per arm, alternating A, D, A, D, A, D, so time-of-day effects fall on both arms alike. Concurrency 1,
  disposable database per run, mock customer API, as in Milestone 10.
- **Freeze:** after the L3 pull request merges, `python -m evaluations.freeze --write` records the code being
  compared, committed before the first run. Any change after that stops the runs (`CLAUDE.md`, 2026-11-10).
- **Shadow mode:** the brief's shadow step checks would-be answer reuses. L3 reuses no answer, so there is nothing to
  shadow: the model's input is the same bytes with or without caching
  (`tests/test_prompt_cache.py::test_the_request_is_identical_apart_from_one_cache_marker`). The paired A/D runs are
  the safety check instead.

## Metrics and pass marks (from `docs/m13-baseline.md` §4)
| Metric | Pass mark for D | Source |
|---|---|---|
| Wrong reuses | 0 (none possible: test above) | test |
| Case success | Not below A's lowest run by more than A's own run-to-run range | Milestone 10 scorer |
| False approvals | 0 in every run | same |
| p95 draft-ready time | Not above A's highest run p95 | per-case `latency_s` |
| Cache used | `cache_read_tokens` > 0 on ≥ 90% of calls after a case's first | spend ledger, per call |
| Cost per 1,000 cases | At least 20% below A's mean | spend ledger |
| Also reported | p50 / p99, model calls per case (expected equal), hit rate (cache-read share of input tokens), counts with 95% intervals, every run separately | |

A fail on any pass mark keeps L3 **off** in the decision memo, with the numbers shown.

## Cost estimate, for the owner's approval
From the stored Milestone 10 held-out runs: $0.13652, $0.135411 and $0.13623 for 80 cases each (mean $0.001701 a
case); input is 56% of the cost (`benchmarks/reports/m13/baseline.json`).

| Step | Cases | Expected | Worst case | Hard limit enforced by the runner |
|---|---:|---:|---:|---:|
| Smoke: D on 5 dev cases, to see `cache_read_tokens` > 0 before the full runs | 5 | $0.01 | $0.01 | `--budget-usd 0.05` |
| A, 3 runs | 240 | $0.41 | $0.41 (as measured) | `--budget-usd 0.25` per run |
| D, 3 runs | 240 | $0.29 (−30%, projected) | $0.47 (every input token billed as a 1.25× write, no reads) | `--budget-usd 0.25` per run |
| **Total** | **485** | **about $0.71** | **about $0.89** | **$1.55** |

- The ledger's overall cap stays at $5.00 (spent so far: $1.83), so the most this can reach is $3.38 there.
- Prices re-checked on Anthropic's pricing page on 2026-11-26: input $0.10, output $0.50, 5-minute cache writes
  $0.125, cache reads $0.01 per million tokens, for prompts up to 100,000 tokens (arm C's largest call is 5,307).
- Before the first call: `python -m app.preflight --profile live-model` must say ready (set or missing only, never a
  value). `.env` goes back to mock afterwards.

## Labels on every result
"Real model (claude-haiku-5-5) · SYNTHETIC cases and personal data · paired A/D regression on the frozen held-out
split, not a held-out claim". MultiWOZ isn't used in these runs (`docs/datasets.md`).
