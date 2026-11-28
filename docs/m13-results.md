# Milestone 13 results: safe AI caching, proven by metrics

> CACHE-04. **Real model (claude-haiku-5-5) · SYNTHETIC cases, members and messages · real public conversation data
> (MultiWOZ 2.2; licence MIT per the repository, Apache-2.0 per the Hugging Face card) for one count only.**
> Independent portfolio simulation. Money per month is a **projection**: measured cost per case times an assumed
> volume. Every number links to a stored file.

## The headline
**In this workflow, answer caching is unsafe (910 look-alike pairs, 0 shared correct answers); prompt caching is the
safe win: 26.0% lower cost per case, with the same quality.**

- **Same quality:** case success 78 of 80 and 0 false approvals in all six runs, with caching and without
  ([phase3-results.md](../benchmarks/reports/m13/phase3-results.md)).
- **26.0% lower cost:** $0.001723 → $0.001275 a case over three runs per arm. In runs 1 and 2, the clean
  comparison, it is **30.4%** ($0.001732 → $0.001205), next to the 30.2% that Phase 1 projected before any run
  ([m13-baseline.md](m13-baseline.md) §3).
- **Zero wrong reuses, by construction:** the model reads the same bytes either way. Prompt caching stores no answer,
  so none can be reused (`tests/test_prompt_cache.py::test_the_request_is_identical_apart_from_one_cache_marker`).

## Three flags that travel with these numbers
1. **A requeue in A3.** One worker job was requeued after a database error (job 36, case HO-032), most likely the
   SQLite lock race of the benchmark environment (TD-57). HO-032 hit its 60 s deadline and then succeeded on a second
   run: 464.7 s, A3's slowest case. A3's p95 is 14.78 s with or without it. The rule for which case a requeue hit was
   committed before the run (verification log, Milestone 13, rows 31 and 35).
2. **CPU contention in A3 and D3.** Another batch ran on the same laptop during both: CPU samples of 12 to 100%
   ([cpu-load.csv](../benchmarks/reports/m13/run-logs/cpu-load.csv), 29 samples). Runs 1 and 2 weren't sampled. They
   ran before the other batch was noticed, so they are the clean comparison, but their load isn't measured either.
3. **Invalid results in D3.** D3 had 5 `invalid_result` stops, against 0, 0 and 1 for A, and 1 and 1 for D1 and D2.
   It also had one `provider_failures` stop, so 95 AI runs instead of 87. The cause isn't established. Caching can't
   change what the model reads, and the two runs under load had the most fallbacks. Case success held at 78/80.

## Before and after
| | No cache (A) | Prompt caching (D) | Source |
|---|---|---|---|
| Case success, per run | 78, 78, 78 of 80 | 78, 78, 78 of 80 | phase3-results.md |
| False approvals, per run | 0, 0, 0 | 0, 0, 0 | same |
| Cost per case, 3 runs | $0.001723 | $0.001275 (**−26.0%**) | same, from the spend ledger |
| Cost per case, runs 1–2 (clean) | $0.001732 | $0.001205 (**−30.4%**) | same |
| Cost per 1,000 cases, runs 1–2 | $1.73 | $1.21 | same |
| Model calls per case, runs 1–2 | 3.763 | 3.694 | same |
| Calls after a case's first that read the cache | 0 of 658 | 650 of 678 (95.9%) | same |
| p95 draft-ready, runs 1–2 | 12.7, 13.8 s | 11.5, 12.0 s | same |
| p50 draft-ready, runs 1–2 | 8.0, 8.5 s | 8.0, 9.2 s | same |
| Wrong reuses | — | 0 (none possible) | request test |

All six pass marks were fixed before the runs ([m13-phase3-plan.md](m13-phase3-plan.md)), and all six were met.

## Business outcome (projection)
At the measured cost per case and the volumes in [load-profile.md](load-profile.md):

| Volume | Without caching | With caching | Saving |
|---|---:|---:|---:|
| Two properties, 320 cases a month | $0.55 | $0.39 | $0.17 a month, $2.02 a year |
| 100 properties, 16,000 cases a month | $27.71 | $19.28 | $8.43 a month, **$101.18 a year** |

Runs 1–2 figures; all three runs give $7.17 a month ($86.02 a year) at 100 properties. These are model costs only:
Haiku is cheap, so the absolute saving is small. What scales is the rate: the same change on a larger prompt or a
pricier model saves the same share.

## What didn't improve
- **Model calls avoided: 0.** Prompt caching makes the same calls cheaper; it doesn't skip any.
- **Latency: no reliable change.** In runs 1–2, D's p95 was lower (11.5 and 12.0 s against 12.7 and 13.8 s), but
  its p50 was the same or higher (9.2 s against 8.5 s in run 2). Six runs on a shared laptop can't separate a small
  latency effect from noise, so none is claimed.
- **Two properties:** 17 cents a month doesn't justify the work on its own. The case rests on the zero-risk change
  and on scale.
- **Answer caching (L1, L2): not built.** In Stage 9's 280 frozen cases, 0 of 910 word-for-word identical masked
  pairs share a correct answer, and no case asks a general policy question ([m13-baseline.md](m13-baseline.md) §2). In
  real hotel dialogues (MultiWOZ 2.2), 148 of 1,713 hotel turns ask a public question about a named hotel, and 22 of
  those repeat one about the same hotel (§2b). That kind of cache belongs in front of Stage 1's knowledge assistant
  or a gateway (backlog BL-M13-02), not here.
- **L4, L5, L6:** no embeddings exist; policy search is a local query with no model call behind it; member data
  must stay live (ADR-0090).

## Spend
| Phase | Spend | Against |
|---|---:|---|
| 1 and 2 (measured from stored files; built with mocks) | $0.00 | — |
| 3 (live) | **$0.809158** | the owner's $1.55 cap |
| … of which the killed partial D2 (in the ledger, not scored) | $0.084858 | |

The ledger total for the project is $2.637470, against its overall $5.00 cap
(`benchmarks/results/live/spend-ledger.jsonl`; verification log, Milestone 13, row 36).

## How to check these numbers
```powershell
uv run python -m evaluations.m13_baseline
```

```powershell
uv run python -m evaluations.m13_results
```

Both rebuild their reports from stored files, with no model call. The tests `tests/test_m13_baseline.py` and
`tests/test_m13_results.py` check that they reproduce, and that the scorer gives the committed Milestone 10 numbers
on a stored run.
