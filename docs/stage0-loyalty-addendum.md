# Stage 0 addendum: loyalty support (requirement REUSE-01)

> **Simulated client engagement with synthetic data.** This extends stage 0's discovery pack
> ([hotel-ai-discovery](https://github.com/vamsialladev/hotel-ai-discovery)) rather than starting a new one. It
> reuses stage 0's scoring, its 4-check test, its SOW structure and its security questionnaire, and records only what
> changes for loyalty. Scores are my judgement after the fictional sessions in `docs/customer-discovery.md`, not
> measurements. Prices are a method until Milestone 10 measures the inputs.

## 1. Use case scoring (same scale as stage 0's PROBLEM_SELECTION.md)

1 (poor) to 5 (strong). Stage 0's rejected idea F is repeated for comparison.

| # | Use case | Value | Feasibility | Risk (5 = low) | Data readiness | Total |
|---|---|---|---|---|---|---|
| F | Automatic refunds and upgrades decided by AI (stage 0, rejected) | 3 | 3 | 1 | 2 | **9** |
| G1 | Missing-points investigation, **AI decides and credits** | 4 | 3 | 1 | 2 | **10** |
| G2 | Missing-points investigation with fixed rules and tools, no AI | 4 | 5 | 4 | 3 | **16** |
| G3 | G2 plus an AI layer that reads requests and drafts cited recommendations; rules decide; a supervisor approves every adjustment | 5 | 4 | 3 | 3 | **15** |

### Why the scores
- **G1** has the same flaw as F: it removes the person from a money-like decision. Rejected for the same reason.
- **G2** fixes the tools: search, rules that match the policy, one evidence view, a safe write path. High feasibility,
  low risk. It may deliver most of the value on its own (hypothesis H1).
- **G3** adds what G2 can't do (free text, several stays, other languages, receipts) but brings model risk: injected
  instructions, a wrong stay matched. Only worth it if it beats G2 on held-out cases without more false approvals (H2).

## 2. The 4-check test

| # | Use case | Someone has felt the problem | Someone would pay | V1 buildable in a week | First customer known | Pass? |
|---|---|---|---|---|---|---|
| G1 | AI decides and credits | Yes | No: the sponsor named "points moving without a supervisor" as a stop condition | Technically | No | **Fail** |
| G2 | Fixed rules and tools | Yes: agents, supervisor, finance | Yes: loyalty operations manager owns the pilot budget | Yes for one property's rules and the evidence view | Yes: the loyalty support team | **Pass** |
| G3 | G2 + AI recommendations | Yes: free-text and multi-stay cases come back as new tickets | Only if measured better than G2 | Yes on top of G2, with the mock provider first | Yes: same team | **Pass, conditional on the benchmark** |

**Decision:** build G2 and G3 side by side with the legacy workflow as arms B, C and A, and let the pre-registered
benchmark (`docs/hypotheses.md`) decide what to recommend. G1 is out of scope.

## 3. SOW addendum (extends stage 0's SOW.md; same structure)

**Parties:** the hotel group (client) and Vamsi Alla (engineer). **Scope addendum to:** the stage 0 statement of work.

### 3.1 Scope
Investigate missing-points requests for Guest Rewards members at both properties: gather evidence, apply the policy
version in force on the checkout date, recommend an action with citations, route adjustments to a supervisor, execute
approved adjustments through the loyalty platform's adjustment API with idempotency and reconciliation, and measure
legacy vs improved vs AI-assisted workflows.

### 3.2 Out of scope
Refunds and payments; messages sent to members; adjustments without supervisor approval; changes to the loyalty
program itself; real customer systems or data until a separate access approval; the posting pipeline (Stage 10).

### 3.3 Deliverables and acceptance criteria
| Deliverable | Accepted when |
|---|---|
| Legacy baseline (arm A) and defect catalog | Arm A completes cases end to end; catalog pre-registered (done 2026-10-28) |
| Improved workflow (arm B) with the safe write path | Approval binding, idempotency and reconciliation tests pass on real Postgres; self-approval blocked |
| AI-assisted workflow (arm C) | Every loop stop condition and injection test passes; live smoke test run or marked NOT RUN |
| Benchmark and business-value report | A/B/C results from actual runs on held-out cases, with counts and denominators; conclusion follows the evidence |
| Security pack | Threat model, authorization and red-team tests pass; residual risks named with owners |
| Handover | Runbooks, UAT scripts, training and admin guides; drills recorded with actual results |

### 3.4 Timeline (projected)
Twenty milestones (`docs/implementation-plan.md`). A prototype timeline is not a production timeline.

### 3.5 Assumptions
The assumptions in `docs/customer-discovery.md` §6 (A1–A7). Synthetic data throughout this engagement.

### 3.6 Client responsibilities
Name a sponsor, a supervisor for UAT, a data owner for merges and channel fixes, and a security reviewer; approve
each rollout gate in writing.

### 3.7 Change control
Same as stage 0: written change request (what, why, effect on scope, timeline and price) → estimate within 3
business days → nothing changes until the client owner approves in writing → recorded in `CHANGELOG.md` and
`docs/decisions.md`. Template: `docs/business-requirements.md` §8.

### 3.8 Price (projection, method only)
Same build-up as stage 0's PRICING.md: measured model cost per 1,000 cases plus assumed hosting, database,
monitoring, support hours, engineering rate, margin. **Stage 9's model cost per 1,000 cases is not measured yet**; it
comes from the Milestone 10 live runs. Until then no price is quoted. The financial model
(`evaluations/financial_model.py`, Milestone 3) will produce pessimistic / base / optimistic projections, labelled as
estimates under stated assumptions.

## 4. Security questionnaire deltas (against stage 0's SECURITY_QUESTIONNAIRE.md)

Only the answers that change for Stage 9. Anything not built yet is marked **Planned (M#)**.

| # | Question | Stage 0 answer (summary) | Stage 9 delta |
|---|---|---|---|
| 1 | Data residency | Managed Postgres in a US region; model provider in the US | Same pattern. Stage 9 adds member profiles, stays and points ledgers (synthetic). The provider region becomes configurable in the approved-deployment profile (**Planned (M12)**) |
| 2 | Retention | Request logs 30 days | Cases and audit records are kept longer for finance (assumed seven years, for legal to confirm); free text and derived summaries on a shorter schedule; legal hold flag (**Planned (M9)**) |
| 4 | SSO | Not in the pilot; documented as next | OIDC with a local Keycloak for the enterprise identity profile (**Planned (M9)**); group-to-role mapping from IdP claims |
| 5 | RBAC | guest / staff / owner; stage 7 roles | Agent, supervisor, administrator, auditor; the creator can't approve their own adjustment (**Planned (M6)**) |
| 6 | Audit logs | Redacted request log; append-only tool audit | Every proposal, approval, rejection, execution and reconciliation, with an append-only database role; integrity guarantees stated honestly (**Planned (M6)**) |
| 9 | Data sent to the model | Question and passages only | The request text (PII redacted), the authorized member, stay and ledger fields needed, the policy excerpts. Never card or passport numbers; the model never decides eligibility, amounts or approvals (**Planned (M8)**) |
| 11 | Incident response | Kill switch for AI | Two switches: live AI off (falls back to arm B, the manual mode) and adjustment execution off (investigation keeps working) (**Planned (M6, M8)**) |
| New | Can the system move points? | Not applicable (stages 1–8 only propose) | Yes, only after a bound supervisor approval, through the loyalty platform's adjustment API with an idempotency key derived from the approval; uncertain outcomes are reconciled before any retry (**Planned (M6)**) |
| New | Prompt injection with money at stake | Injection cases as CI gates | Red-team cases assert on business effects (no points moved, no approval skipped), not reply wording (**Planned (M9)**) |
