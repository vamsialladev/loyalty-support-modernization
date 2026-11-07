# AI system card: arm C (ENT-01, ENT-02, ENT-15)

**Draft. SYNTHETIC: a simulated engagement for a fictional hotel group.** No quality result here comes from a real model yet. The live smoke test passed on 2026-11-07, one call, which shows the connection works and nothing about quality (`benchmarks/results/live/smoke/`). **The live evaluation is NOT RUN:** Milestone 10 does it, under the owner's $5 cap.

## What it is
A model reads a member's missing-points message, works out which of the member's real stays it means, explains the rules engine's result with citations, and drafts a reply for staff.

## What it isn't allowed to do
Decide. Identity, eligibility, the amount, permissions, approval and execution are deterministic Python, the same as arm B. It can't send anything, and it has no tool that writes. A credit still needs the engine's `adjust`, a different supervisor, a fresh re-check and the write path.

## Use-case register entry (draft)
| Field | Value |
|---|---|
| Use case | Assist loyalty support agents with missing-points cases |
| Owner | The (fictional) loyalty operations lead |
| Users | Support agents and supervisors. Members never talk to the model |
| Decisions it influences | Which stay a case is about, and whether a person reads a message first. Both are checked by code, and a person reviews everything |
| Impact if wrong | A case wrongly asks or escalates: a slower answer. A wrong explanation: a reviewer may be misled, which is why evidence comes first. It can't move points by itself |
| Risk level (draft) | Limited: a human decides. To be reviewed by the customer's governance team |
| Data sent to the provider | The member's message and documents, redacted for email, phone, card and secret patterns; stay and ledger summaries; policy excerpts. **Names stay**, since they're needed to read the request. Not sent: email, phone, birth date |
| Retention | Run records hold what happened, not evidence. The provider's retention terms need checking before any real data is sent (`docs/known-limitations.md`) |

## Model and lifecycle
- **Model:** Claude Haiku 5.5 (`claude-haiku-5-5`), effort `low`. Pinned in configuration. Only models listed in `config/ai/hg-demo.yaml` run; an unknown or deprecated ID fails safe to arm B's result.
- **Upgrading:** check the provider's deprecation notices monthly while live. Add the new model to the list with its price and the date checked, compare it on the held-out set, and only then switch. A change of model or of prompt version is recorded on every run.
- **Prompt:** versioned in `config/prompts/`; a test fails if the text changes without a new version.

## Known limits
- Redaction is pattern matching. It misses a phone number written in words, and addresses.
- A person can still over-trust good-looking text. Evidence and the engine's result come first, and Milestone 10 tests this with an automation-bias variant.
- Injection is contained, not prevented. The model may well repeat an injected instruction in its draft; drafts aren't sent, and the validator refuses invented amounts. Tests assert on business effects.
- All numbers shown from a mock are labelled, and say nothing about quality.

## Fallback
If the model is off, unlisted, over budget, failing or cancelled, or its result is invalid, the case holds arm B's result, flagged `ai_fallback`, with the reason on the page.
