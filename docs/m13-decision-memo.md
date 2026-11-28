# Decision memo: turn on prompt caching for arm C, with conditions

> CACHE-04. A five-minute read for the operations director and the AI operations owner. **Simulated engagement,
> synthetic data; money per month is a projection.** Evidence: [m13-results.md](m13-results.md).

## The decision
**In this workflow, answer caching is unsafe (910 look-alike pairs, 0 shared correct answers); prompt caching is the
safe win.** We recommend turning prompt caching **on** for arm C's model calls (`FEATURE_PROMPT_CACHE=true`), under
the four conditions below. We recommend **no** answer cache of any kind for this workflow.

## Why
- **Same quality, lower cost.** Across six live runs on the same 80 frozen cases, case success was 78 of 80 and false
  approvals 0, with and without caching. Cost per case fell 26.0% over three runs per arm, and 30.4% in runs 1 and 2,
  the clean comparison.
- **It can't give a wrong answer.** The model reads the same input either way; nothing is stored or reused.
- **It's cheap to reverse.** One switch in `/admin` turns it off from the next AI run, without a restart.
- **The money is small today:** about $8 a month at 100 properties (projection, runs 1–2). The rate is what scales:
  a longer prompt, a pricier model or more volume keeps the same share.

## Conditions
1. **Watch the first week** on `/metrics`. The "Prompt cache" line should show the cache read on most calls after a
   case's first (95.9% in the test). Cost per 1,000 cases should be at or below the no-cache figure (about $1.73).
   If cost goes up instead, switch it off and follow [the runbook](runbooks/prompt-cache.md).
2. **Quality stays watched as before.** QA sampling and the weekly drift check (`docs/runbooks/ai-quality-drift.md`)
   are unchanged. One run in the test had more invalid model results than the others (5 against 0 or 1), with no
   cause found. If the validation-failure rate moves past its drift threshold, switch caching off while it's
   investigated.
3. **Security signs off on data handling.** The provider keeps cached prompts in memory for at least 5 minutes, isolated
   per organization, and states prompt caching is eligible for zero data retention (read 2026-11-26). The prompt holds
   redacted member text the provider already receives; our app stores no cached content.
4. **Prices are re-checked** whenever the model or its price changes (`config/ai/hg-demo.yaml` holds the cache rates),
   because the saving depends on the read and write rates.

## Owners (proposed roles)
| What | Owner |
|---|---|
| The flag, in each environment's configuration | Application team (L2) |
| The `/admin` switch, the first week's watch, the runbook | AI operations owner (L3) |
| The data-handling sign-off (condition 3) | Security (L3) |
| Cost tracking against the projection | Finance partner |

## Risks
| Risk | How likely | What limits it |
|---|---|---|
| Cost rises (writes cost 1.25× and no reads) | Low: 95.9% of later calls read the cache in the test | The first week's watch; the switch |
| A provider-side caching change or incident | Low | The switch; the provider's status page |
| A quality change blamed on caching | Possible, from noise | The request test shows the input is unchanged; QA sampling decides |
| The test's limits (one laptop, 80 synthetic cases, 3 runs, one shared-load episode) | Known | A pilot on real cases repeats the comparison before any claim |

## What would reverse this decision
- Cost per case not lower than the no-cache figure over a week of real traffic.
- A change in case success, false approvals or QA reviews that follows the switch-on and goes away when it's off.
- The security sign-off failing (condition 3).

## What this decision is not
- **Not a deployment.** The flag stays off in this repository and the public demo (which uses mock AI, so it has no
  provider cache). Turning it on in a real environment is that environment's change, made by its owners.
- **Not an answer cache.** For a channel where people ask general questions, an answer cache can make sense: keyed by
  property and policy version, intent-checked, invalidated on publish. That belongs in front of a knowledge
  assistant or a gateway (backlog BL-M13-02), not in a claims workflow.
