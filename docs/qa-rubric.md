# QA rubric for online sampling (proposed)

Used by online quality sampling (spec E5; ENT-18; `app/services/qa_sampling.py`). **Proposed:** written in Milestone
12 from the spec and the arms' outputs, not yet tried with the people who would use it. User acceptance testing in
Milestone 18 calibrates it (TD-48). All cases are synthetic.

A reviewer (a supervisor or an auditor, never the person who closed the case) opens the sampled case, reads its
evidence, recommendation and closing, and answers five items. Answers are codes, so a review holds no personal data
and no free text.

| Item | Question | Answers |
|---|---|---|
| `outcome` | Was the case's outcome right for the member's points? | `right` · `wrong` · `unsure` |
| `evidence` | Was the evidence that decided it attached and enough? | `complete` · `missing` · `wrong` |
| `policy_cited` | Was the policy cited the one that applies? | `right` · `wrong` · `none_needed` |
| `explanation` | Would a supervisor understand the reasoning from the case alone? | `clear` · `unclear` · `misleading` |
| `member_message` | Could the reply to the member go out as written? | `ready` · `needs_edit` · `wrong` |

**How results are used:** counts per answer on the QA summary, kept apart from the offline benchmark (they never
enter `benchmarks/reports/`). A `wrong` outcome becomes a candidate for the regression dataset only through the
label-review step (ENT-21), never automatically. A rising share of `wrong` or `misleading` answers is a drift signal
for the AI operations owner (`docs/runbooks/ai-quality-drift.md`).

**What would change it:** UAT showing reviewers disagree on an item (split it or define it with examples), or a
customer's own QA form (map its items onto these codes).
