# Milestone 13, Phase 1: where would caching help arm C?

> CACHE-01. **Measured from stored files. Real model token counts (claude-haiku-5-5, Milestone 10's live runs);
> SYNTHETIC cases, members and messages. Cost figures are projections from stated assumptions, not results.**
> Independent portfolio simulation. No model was called and no code path changed for this phase.
>
> Every number below comes from `benchmarks/reports/m13/baseline.json`, written by
> `uv run python -m evaluations.m13_baseline` and checked by `tests/test_m13_baseline.py` (the committed file must
> reproduce exactly). Inputs: dataset v1 (280 cases), its labels, the nine frozen-configuration live runs (500 cases)
> and `benchmarks/results/live/spend-ledger.jsonl` (one row per paid model call).

## The answer in five lines
1. **Answer caching (exact or semantic) has no safe target in this workflow.** Of 910 pairs of cases whose masked
   messages are word-for-word identical, **0** share the correct answer, and **654** (72%) need a different next
   action. Reusing a draft by message text would be wrong every time.
2. **Nobody asks a general policy question.** 5 of 280 cases contain a question mark; none is a general policy
   question (4 ask for another member's points, which must be refused; 1 is the claim itself). An FAQ-style cache
   would have no traffic.
3. **The one cacheable thing is the prompt the model re-reads.** Arm C makes 3.8 model calls a case (p50 3, p95 7),
   and each call re-sends the previous call's whole input: **68% of input tokens** on held-out.
4. **Provider prompt caching is projected to cut cost per case by about 30%** (input cost −54%; input is 56% of the
   case cost). It avoids **0** model calls: it makes the same calls cheaper.
5. **In money it is small:** about **$0.16 a month** at two properties and **$8.21 a month** (about $99 a year) at
   100 properties, at today's Haiku prices. Projection.

## 1. What each step of arm C does, and whether it may be reused

Arm C is arm B plus a bounded model loop (`app/ai/loop.py`): up to 6 model turns, five read-only tools, then one
`submit_recommendation` call that carries the explanation and the draft reply together (`app/ai/tools.py`). The
rules engine decides; the model explains.

| Step | What it reads or produces | Class | Why | Cache layer it would be |
|---|---|---|---|---|
| System prompt `arm_c_v1` + 6 tool definitions | 1,749 + 2,726 characters, the same for every case and customer | **Reusable, public** | No customer or member data; changes only with a prompt or tool version | L3 (provider prompt cache) |
| Opening context | Engine result, data checks, redacted member messages, document text | **Private, never cache** | Member-specific; redaction lowers risk but doesn't make it public | — |
| Calls 2 to n of one case | The same conversation, plus tool results | **Private, reuse within the same case only** | Each call re-sends the previous one; nothing crosses to another case | L3 (provider prompt cache, 5 minutes, held by the provider) |
| `get_member`, `get_stay` | Name, tier, stays of the confirmed member | **Private, never cache** | Personal data; profiles merge and change | L6: no |
| `get_points_ledger` | Ledger entries and pending postings | **Private, never cache** | Changes the moment an adjustment posts; stale reads are exactly the bug the write path guards against (ADR-0061) | L6: no |
| `evaluate_eligibility` | The engine's result for one stay | **Private, never cache** | Deterministic, but over private, changing evidence; the approval binds a hash of the evidence it saw (ADR-0059) | — |
| `search_policy` | Model-written query → excerpts of the policy versions in force on the checkout day | **Reusable, per customer** | Policy text is per customer, never personal; changes only on publish | L5 (retrieval cache keyed by index version) |
| Policy explanation | Inside `submit_recommendation`, mixed with the member's facts | **Private as produced** | It is written in the same call as the draft, about this member's stays | L1/L2: no separate step to reuse |
| Draft reply | Names the member's stay, points and next step | **Private, never cache** | See the answer in five lines, point 1 | L1/L2: no |
| Embeddings | None exist: retrieval is Postgres full-text (ADR-0024, `docs/retrieval.md`) | — | Nothing to cache | L4: not applicable |
| Document reading (`read_image`) | Fields from the member's own document | **Private, never cache** | A member's document | — |
| Published policy versions | Loaded per case, per customer | **Reusable, per customer** | Changes only on publish; already one small query | L6: not worth it |

## 2. How often things repeat

### Member messages (all 280 cases; `messages` in the JSON)
Masking removes emails, codes such as `BR-6754` and `GR-97315`, every number, month names and every name the data
holds. Then:

| Measure | All 280 | Held-out 80 |
|---|---:|---:|
| Distinct masked messages | 125 | 49 |
| Cases whose masked message repeats an earlier one word for word | 155 (55%) | 31 (39%) |
| Cases with an earlier message at word-set overlap (Jaccard) ≥ 0.8 | 240 | 61 |
| Pairs of word-for-word identical masked messages | 910 | 68 |
| … of which the correct answer is the same (action, points owed, stays) | **0** | **0** |
| … of which even the next action is the same | 256 | 16 |
| Wrong if an answer were reused, 95% Wilson interval | 910/910 (99.6–100%) | 68/68 (94.7–100%) |

**Read this carefully: the repeat rate is high because the messages come from templates (ADR-0032).** Real members
write more varied text, so real repeat rates would be lower. That doesn't rescue answer caching: the cases that *do*
repeat word for word still need different answers, because the answer depends on the member's records, not the words.

### Policy context (`policy_context` in the JSON)
Four policy versions exist for the one customer (two policies, two versions each). On dev, 100 cases used **5**
distinct sets of policy versions, and 95 reused a set seen earlier; on held-out run 1, 80 cases used **6** sets and
74 reused one. So policy search results would repeat often, per customer. But search is one local Postgres
full-text query, with no model call behind it.

### 2b. Real hotel messages: how often is it a general question? (`benchmarks/reports/m13/multiwoz-questions.json`)
> **Real public conversation data: MultiWOZ 2.2 test split, crowd-written role-play (licence: MIT per the
> repository, Apache-2.0 per the Hugging Face card; `docs/datasets.md`). No model used.** Added after the owner
> approved the dataset at the Phase 1 gate (2026-11-26).

Of 1,000 test dialogues, 395 involve a hotel. They hold 1,713 user turns about the hotel:

| Kind of hotel turn | Turns | Share | Could an answer cache serve it? |
|---|---:|---:|---|
| Asks a question (requested slots in the turn) | 287 | 17% of 1,713 | Depends on the next three rows |
| … about the guest's own booking (`hotel-ref`) | 44 | | **No:** private |
| … about a property not named yet ("what area is it in?" while searching) | 95 | | **No:** nothing safe to key on |
| … a public fact about a named hotel (phone, postcode, address, parking, internet…) | 148 | 9% of 1,713 | **Yes**, keyed by property, version and question |
| Booking turns (`book_hotel`) | 483 | 28% of 1,713 | No: a transaction |

- Of the 148 public questions about a named hotel, **22 (15%) repeat** one asked earlier about the same hotel, in
  this 1,000-dialogue sample.
- Keyed by the question alone, without the property, 109 would "repeat", and **106 of those had another hotel's
  answer to reuse**. The property has to be part of the key.

So even in a channel built for questions, about one turn in eleven is a public, cacheable question, and a key must
carry the property. Stage 9's channel is claims: none of its 280 cases asks one. **The answer cache belongs in front
of Stage 1's knowledge assistant (public policy and property questions) or a Stage 12 gateway, not in Stage 9's
claims workflow** (backlog BL-M13-02).

### Model calls (`model_calls` in the JSON)
The ledger was split into cases by matching each case's stored token totals exactly; all 500 cases matched (a test
checks every run). The ledger also holds an earlier attempt for `c-live-dev` and `c-live-validation` under the same
names; only the later run, which matches the stored results, is used.

| Measure | Value |
|---|---|
| Model calls per case (500 cases) | mean 3.81, p50 3, p95 7, p99 8, max 10 |
| Input tokens on a case's first call | p50 2,140, p95 2,325 (above Haiku 5.5's 512-token minimum for caching) |
| Input tokens per call (1,903 calls) | p50 2,474, p95 3,144, max 5,307 |
| Held-out input tokens re-sent from the call before (3 runs, 240 cases) | 1,569,924 of 2,298,324 (**68%**) |
| Held-out cost per case | mean $0.0017, p50 $0.0016, p95 $0.0029 |
| Input share of held-out cost | 56% |
| Draft-ready time per case, held-out r1 / r2 / r3, p95 | 10.95 s / 11.24 s / 11.58 s (p50 7.59 / 7.84 / 7.78 s) |

**Per-step latency is not measured yet.** The live runs stored per-case time and per-call tokens, not per-step
spans: their databases were disposable. Phase 3's shadow runs will record model and tool spans (the GenAI spans
from Milestone 12, ADR-0077).

## 3. Opportunity per layer (estimates)

Prices: $0.10 / $0.50 per million input / output tokens (`config/ai/hg-demo.yaml`, checked 2026-11-06). Cache
multipliers: reads 0.1×, writes 1.25× of the input price, 5-minute lifetime, from the Claude API reference as cached
on 2026-11-03. **Both are re-checked on the official pricing page before any live run.** Volumes: 320 cases a month
at two properties (`docs/load-profile.md`); 100 properties = 50 × that, 16,000 a month.

The L3 projection is within a case only: call *k* reads call *k − 1*'s whole input from the cache and writes the
rest; the first call of every case pays a full write; the last write is wasted. That is conservative: at 100
properties a new case would find the shared prompt prefix still warm about 84% of the time (3.6% at two properties),
if cases arrived evenly at random. Working hours bunch arrivals, so the real figure would be higher. An assumption,
not counted.

| Layer | Calls avoided | Cost per case | Two properties, per month | 100 properties, per month | Wrong reuses possible? | Draft decision |
|---|---:|---:|---:|---:|---|---|
| L1 exact answer | 0 safe | — | — | — | Yes: 910 of 910 identical pairs | **Don't build** |
| L2 semantic answer | 0 safe | — | — | — | Yes: 0 of 7,749 near pairs share an answer | **Don't build** |
| L3 provider prompt caching | 0 (same calls, cheaper) | **−30%** ($0.0017 → about $0.0012) | **−$0.16** of $0.54 | **−$8.21** of $27.21 | No: same model input, byte for byte | **Build, flag OFF** |
| L4 embedding cache | 0 | — | — | — | — | **Not applicable** |
| L5 retrieval cache | 0 model calls; saves local queries | not measured | — | — | Yes, if a publish were missed | **Don't build now**; revisit with Phase 3 spans |
| L6 tool/API results | 0 | — | — | — | Yes: stale ledger, other member's data | **Never** for member data |
| L7 GPU KV/prefix cache | — | — | — | — | — | **Explain only** (Stage 11) |

Cost per 1,000 cases, held-out mean: **$1.70 now; about $1.19 projected with L3** (estimate).

## 4. Draft targets for Phases 2 and 3 (for the owner's gate)

**Build only L3** (provider prompt caching on arm C's model calls), behind `CACHE_PROMPT` (default OFF), with the
kill switch. Its targets, all measured on the same frozen cases with the real model, 3 runs per arm:

| Target | Threshold | How it's measured |
|---|---|---|
| Wrong reuses | **0**. L3 can't reuse an answer: the model reads the same bytes. A test proves the request is identical apart from the cache marker | `tests/` request-shape test; shadow comparison |
| Case success | Not below the no-cache arm beyond its run-to-run range | Same scorer as Milestone 10 |
| False approvals | **0**, as now | Same scorer |
| p95 draft-ready time | Not worse than the no-cache arm's p95 range in the same session | Per-case latency, 3 runs each |
| Cache actually used | `cache_read_input_tokens` > 0 on ≥ 90% of calls after a case's first | Provider usage fields, stored per call |
| Cost per 1,000 cases | **At least 20% lower** than the no-cache arm (the minimum that justifies even this small change) | Spend ledger, actual billed tokens |

**Don't build L1, L2, L4, L5 or L6 in this milestone.** What would change that:
- **L1/L2:** a channel where members ask general policy questions (for example, "how long do points take to post?")
  answered from policy text alone. That is new scope, so it goes to `docs/backlog.md` (BL-M13-01), not here.
- **L5:** Phase 3 spans showing `search_policy` takes 10% or more of draft-ready time at p95.
- **L6:** nothing; member data stays live (spec B.12: cache only where correctness and authorization allow).

## 5. Limits of this baseline
- Messages are template-generated, so repeat rates are inflated; the conclusion about answers doesn't depend on them.
- The cost projection assumes the provider charges as the reference says and that every call after the first finds
  its predecessor cached. Thinking blocks and tool results are passed back unchanged (`app/adapters/anthropic_model.py`),
  so the prefix should match; Phase 3 measures it.
- Held-out labels have been public since 2026-11-13 (`CLAUDE.md`). Phase 3 uses the frozen cases as a regression set
  comparing arms, not as a new held-out claim.
- One customer (`hg-demo`), four policy versions. A second customer (Milestone 14) changes the per-customer numbers,
  not the classification.
