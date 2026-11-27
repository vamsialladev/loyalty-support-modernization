# Provider prompt caching (L3)

**What it is:** arm C asks the model provider to cache the prompt it re-sends on every call of a case
(`FEATURE_PROMPT_CACHE`, default **off**; ADR-0090). The model reads exactly the same input either way, so caching
can make a call cheaper or slower to start, never different. It avoids no model calls. **Proposed owner:** AI
operations owner (L3). Synthetic data only.

**Where to look:** `/metrics` (the "Prompt cache" line per arm: tokens read from the cache, written, share, cost per
1,000 cases); `/admin` (the flag's state and the switch); Grafana gauge `loyalty.ai.cache_tokens` by `kind`; trace
spans `chat <model>` with `gen_ai.usage.cache_read.input_tokens` and `gen_ai.usage.cache_write.input_tokens`.

## Turn it off now (no restart)
1. `/admin` → "Prompt caching" → give a reason (at least 10 characters) → **Turn prompt caching off**.
2. It applies from the next AI run; a run already going keeps its setting to the end.
3. **Check it worked:** new runs show 0 cache tokens on `/metrics`, and new spans carry no cache attributes.

## Situations

| You see | Likely cause | Do |
|---|---|---|
| Cost per case **up** after turning it on | Cache writes (1.25× input) with few reads: calls of a case more than 5 minutes apart, or a prefix that changes every call | Turn it off. Compare `cache_write` with `cache_read` on `/metrics`. If reads stay near 0, look for something that changes the prompt between calls (a timestamp, unsorted JSON, a changed tool list) before turning it on again |
| Reads near 0 but writes normal | A silent invalidator, or a prompt under the 512-token minimum (arm C's first call is about 2,100 tokens, so it shouldn't be) | As above. Prompts and tool definitions are versioned files: a changed `config/prompts/*.md` or `app/ai/tools.py` starts new cache entries, as it should |
| Draft-ready time worse | Rare: writes add a little time | Turn it off and compare p95 on the same cases (Phase 3's method, `docs/m13-phase3-plan.md`) |
| "A bad cached answer" reported | **Not possible with L3:** no answer is stored or reused. The model wrote that answer from this case's own input | Treat it as an ordinary wrong answer (QA review, `ai-quality-drift.md`). Turning caching off won't change it |
| Spend near its cap | Normal cap handling; cached tokens are counted at their own rates, and the check before each call assumes the dearest one | [ai-spend.md](ai-spend.md) |
| Provider incident or a change in its caching | Outside our control | Turn it off; turn it on again after the provider's status page clears |

## A policy is published
Nothing to do. Policy text isn't in the cached prompt prefix as a stored answer; each case reads its own excerpts
through `search_policy`, and they're part of that case's conversation only. The cache lives at most 5 minutes after
its last use, and entries never cross organizations (provider documentation, read 2026-11-26).

## Change the flag (deploy)
`FEATURE_PROMPT_CACHE=true` or `false` in the environment, then restart the app and the worker. Production changes
go through the release gate like any configuration change (ADR-0082). The switch above can only turn it **off**.

## Roll back the code
Image rollback as in `docs/rollback.md`. Migration 0014 only adds two columns with a default of 0; the previous image
ignores them, so no downgrade is needed.

## Privacy
The provider holds cache entries in memory only, for at least 5 minutes after the last use, then deletes them; it
stores no raw prompt text for caching, and prompt caching is eligible for zero data retention (provider documentation,
read 2026-11-26). What's cached is what the provider already receives for the call. **This app stores no cached
content anywhere**, so there is nothing of ours to purge by tenant or member: only the token counts.
