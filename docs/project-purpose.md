# Project purpose

> Set by the owner on 2026-10-28, before Milestone 3, and applied in every milestone from then on. The purpose and
> the lenses below are the owner's words, kept verbatim. Section 4 says where each artifact lives and when it is
> updated. These lenses are applied inside each milestone's existing work: they do not add milestones or scope, and
> the documents stay proportionate to what has actually been built.

## 1. Purpose (owner's words)

Stage 9 is my reusable, end-to-end Forward Deployed Engineer project. It must work like a real company engagement
from discovery to handover, connect to the real tools a company uses, and be something I can bring into future
projects and hand to a newly joined engineer, who should understand how a senior FDE, a principal engineer and every
other role on a real AI engagement handle each part. Treat every milestone through these lenses:

1. Business: problem, owner, success metric, cost, and when AI is not the answer.
2. Data: sources of truth, quality, mapping, privacy, retention.
3. AI: where it helps, what stays deterministic, evaluation, limits.
4. Engineering: architecture, integrations, reliability, testing.
5. Security and governance: access, secrets, threats, approvals, audit.
6. Operations: deployment, monitoring, incidents, recovery, cost control.
7. People: users, training, handover, ownership, change management.
8. Tools: which real tool each step uses, how it connects (adapter, API, MCP, connector), what access it needs, and
   what happens when it isn't available.
9. Reuse: what generalizes to other customers and domains, and what must be redone each time.
10. Principal engineering: technical strategy and long-term direction; how the design scales (10x volume, more
    customers, more domains) and where it breaks first; platform vs. one-off decisions; build vs. buy vs. partner at
    organization scale; technical debt taken on deliberately and the plan to pay it down; standards other teams could
    adopt; risks across teams and vendors; total cost of ownership over 1–3 years; and how to explain decisions to
    executives, security, finance and other engineering teams.
11. Every role on the engagement: show how each role contributes and what it would check, so the project demonstrates
    fit for all of them:
    - Forward Deployed Engineer / Solutions Engineer: discovery, customer workflow, integration, demo, handover.
    - AI / Applied AI Engineer: prompts, context, tools, agent loop, harness, evaluation.
    - ML Engineer / Applied Scientist: classical-ML baseline, calibration, datasets, experiment design, statistics.
    - MLOps / LLMOps Engineer: model lifecycle, regression gates, monitoring, drift, cost tracking.
    - Data Engineer: generator, pipelines, data quality, lineage, data dictionary.
    - Backend / Platform Engineer: services, durable jobs, idempotency, APIs, performance.
    - Site Reliability Engineer: SLOs, alerts, runbooks, drills, recovery.
    - Security Engineer: threat model, authorization, secrets, red-team tests.
    - Solutions / Enterprise Architect: target architecture, integration patterns, real-system swap paths.
    - Staff / Principal Engineer: strategy, scaling, standards, RFCs, debt, TCO.
    - Engineering Manager / Tech Lead: plan, risks, dependencies, team onboarding, delivery tracking.
    - Product Manager: problem framing, user stories, success metrics, rollout, what not to build.
    - Technical Program Manager: milestones, cross-team dependencies, status and risk reporting.
    - QA / Test Engineer: test strategy, regression suites, browser tests, acceptance criteria.
    - Customer Success / Support Lead: training, UAT, support handover, feedback loop.
    - Responsible AI / Governance: system card, fairness, human oversight, regulatory assessment.
    - Executive sponsor: business case, cost, risk and decisions in one page.

## 2. How to apply it in every milestone (owner's words)

- Real-company readiness: every synthetic or mock component sits behind an adapter or configuration with a documented
  path to connect the real system (what changes, what access is needed, who approves). Record these in
  docs/real-system-swap-guide.md, updated each milestone.
- Tool connections: keep docs/tool-access-matrix.md and docs/fde-tool-map.md current, so for each tool you know its
  role, connection method, permissions, data it touches, and status (exercised / configured / blocked).
- Onboarding: create docs/onboarding.md and update it at the end of every milestone, so a newly joined engineer can
  understand the system in a day: what it does, how to run it, where each part lives, why the key decisions were made
  (link the ADRs), common failure modes, and the first tasks to try.
- Senior judgment: for every important decision, record the options considered, why one was chosen, the trade-off, and
  what would change the decision, in the ADRs, written so a new engineer learns how a senior thinks.
- Principal-level artifacts (keep current, short and honest):
  - docs/technical-strategy.md: the target architecture, the path from this simulation to a multi-customer platform,
    what to standardize, what not to build, and the key bets with how we'd know they were wrong.
  - docs/scaling-and-limits.md: expected bottlenecks at 10x and 100x (data volume, model cost, queue, database, team
    size), the first thing that breaks, and the planned response; label estimates as estimates.
  - docs/tech-debt-register.md: deliberate shortcuts, why they were taken, their risk, and the trigger to fix them.
  - docs/tco.md: 1–3 year total cost of ownership under stated assumptions (model, hosting, engineering time,
    support), with sensitivity, never presented as measured.
  - docs/rfcs/: one short RFC-style design doc for each design-heavy milestone (6, 8, 10, 11), with context, options,
    decision, risks, rollout and open questions.
  - docs/executive-brief.md: a one-page update per phase for a non-technical sponsor: outcome, evidence, risks,
    decisions needed, cost. Plain language, no jargon.
- Role coverage: keep docs/role-coverage-map.md, a table with one row per role from lens 11 and columns for the
  artifacts and evidence that demonstrate it, the milestone where it was shown, its status (shown / planned / not
  covered), and two or three interview questions that role would ask with where the answer lives in the repo. At the
  end of each milestone, add which roles it exercised. Never claim a role is covered without real evidence in the repo.
- Reuse: note in each milestone what will move into the starter kit (Part J) and what is customer-specific.

Don't expand the milestone order or scope for this; apply these lenses inside each milestone's existing work, and keep
these documents proportionate to what has actually been built.

## 3. Additional purpose items (owner's words)

- Public data option: design the data layer so a public dataset can later be added as a clearly labelled, optional
  source alongside the synthetic default. Before any public data is used, record in docs/data-sources.md its license
  and terms (commercial use, redistribution, attribution), confirm it contains no personal data, credit the source,
  and keep synthetic data as the default for demos and evaluation.
- Showcase kits: in Milestone 19, create portfolio/role-pitches/ with one short file per role from lens 11: a 2-minute
  pitch, the three strongest pieces of evidence for that role with links, and the likely interview questions with
  where the answers live. Only verified evidence.
- Consulting and company use: in Milestone 19, add portfolio/engagement-method.md presenting this as my method and
  reference architecture for running an AI engagement end to end, plus a pilot/discovery offer template (scope,
  duration, deliverables, success criteria, what the client provides). Never present it as past client work, invent
  clients, or quote unmeasured savings.
- Using it at an employer: add docs/using-at-a-company.md explaining what must happen before this foundation is used
  with company data or systems: security and privacy approval, the approved-deployment profile, real-system adapters,
  and a reminder to check the employer's IP and personal-project policies. Documentation only.

## 4. Where each artifact lives and when it is updated

| Artifact | Updated | Matrix ID |
|---|---|---|
| `docs/real-system-swap-guide.md` | End of every milestone that adds or changes a mock, generator or adapter | PURP-02 |
| `docs/onboarding.md` | End of every milestone | PURP-03 |
| `docs/tool-access-matrix.md`, `docs/fde-tool-map.md` | Whenever a tool's role, access or status changes | TOOLMAT-01, TOOL-MAP |
| ADRs in `docs/decisions.md` (options considered, what would change the decision) | With every important decision | PURP-01 |
| `docs/technical-strategy.md`, `docs/scaling-and-limits.md`, `docs/tech-debt-register.md`, `docs/tco.md` | End of every milestone, proportionate | PURP-04 |
| `docs/rfcs/` | Milestones 6, 8, 10, 11 | PURP-05 |
| `docs/executive-brief.md` | End of each phase (discovery, data, core build, AI, evidence, enterprise, handover) | PURP-06 |
| `docs/role-coverage-map.md` | End of every milestone: roles exercised, with evidence | PURP-07 |
| `docs/data-sources.md` | Before any non-synthetic data is used | PURP-08 |
| `portfolio/role-pitches/` | Milestone 19 | PURP-09 |
| `portfolio/engagement-method.md` (+ offer template) | Milestone 19 | PURP-10 |
| `docs/using-at-a-company.md` | When the approved-deployment profile or adapters change | PURP-11 |
