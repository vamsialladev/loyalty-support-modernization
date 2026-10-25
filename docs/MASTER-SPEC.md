# MASTER BUILD PROMPT: AI Loyalty Support Modernization Platform
## Stage 9 of the simulated hotel-group engagement on vamsialla.com

> **How to use:** Save this file in a new repository as `docs/MASTER-SPEC.md` and commit it. Start Claude Code in that repository and send:
> *"Read docs/MASTER-SPEC.md completely and follow it. Begin with Part 0 and Milestone 1."*
> For every later session send:
> *"Read CLAUDE.md, docs/MASTER-SPEC.md, docs/session-handoff.md and docs/implementation-status.md. Run the tests, then continue with the next incomplete milestone."*

---

## PART 0: Role, mission, and working rules

### 0.1 Role
Act as my senior Forward Deployed Engineer, applied AI engineer, product engineer, integration architect, data engineer, AI evaluation engineer, enterprise AI security engineer, platform/deployment engineer, business analyst, and implementation mentor.

### 0.2 Mission
Build, verify, and hand over **AI Loyalty Support Modernization Platform**. Earlier drafts used the names "AI Loyalty Support Resolution Assistant" and "AI Loyalty Support Resolution Platform"; they are the same project. It becomes **Stage 9** of the existing simulated hotel-group engagement on vamsialla.com. Part 0.7 governs continuity, reuse, and scope.

The project has five connected outcomes, and each is a required deliverable:
1. **Product:** a working, verified AI application for missing-points investigations, with human-approved simulated adjustments.
2. **Evidence-based modernization:** a credible legacy baseline, an improved non-AI workflow, and an AI-assisted workflow, benchmarked fairly to show whether AI adds incremental value.
3. **Learning tracks:** hands-on exercises with the actual development tools, model providers, and AI protocols listed in Parts H and G.
4. **Reusable FDE foundation:** a starter kit and playbooks extracted from the working application.
5. **Honest portfolio package:** for vamsialla.com, with real evidence.

The project must demonstrate the complete FDE lifecycle:
1. Discover the business problem.
2. Understand existing systems.
3. Establish approved access and data boundaries.
4. Choose where AI is useful.
5. Build a working integration.
6. Evaluate correctness and business usefulness.
7. Deploy progressively.
8. Monitor and recover from failures.
9. Train users and hand over ownership.
10. Measure outcomes.
11. Extract reusable patterns.

This is an **independent portfolio simulation** using fictional companies and synthetic data. Prepare an enterprise deployment path without claiming certification, real customer adoption, or universal production readiness.

Do the actual implementation: create files, install dependencies, run the application, execute tests, fix failures, and produce deployment, handover, and portfolio materials. **Do not stop at plans, architecture, scaffolding, diagrams, or sample snippets. A summary is not a substitute for implementation.**

### 0.3 Working rules
- Inspect the workspace, the repository, and any `CLAUDE.md` / `AGENTS.md` instructions first. Preserve existing work and unrelated files. If an earlier version exists, assess it against this spec and extend it. Do not create a duplicate project.
- Make reasonable, reversible decisions autonomously and record them in `docs/decisions.md`. Ask only when a missing business decision, external access, or a consequential action genuinely requires my input. **Batch account and access questions** so you interrupt me as rarely as possible.
- Use current **official documentation** to verify package, SDK, model, protocol, and platform APIs. Pin compatible versions and provide a reproducible lockfile.
- **Never invent** credentials, integrations, tool usage, approvals, sign-offs, test results, benchmark numbers, interviews, users, testimonials, customer dissatisfaction, deployment URLs, GitHub URLs, savings, ROI, or adoption.
- **Never** do any of the following without my explicit authorization in chat:
  - Purchase subscriptions or services.
  - Create paid cloud resources.
  - Run `terraform apply` or an equivalent.
  - Push to remote repositories or install GitHub apps or org-wide integrations.
  - Publish the website or any public page.
  - Connect real customer or company accounts.
  - Reuse personal browser sessions for customer systems.
  - Upload confidential data to unapproved services.
  - Send messages, invitations, or emails.
  - Fund wallets or execute real payments.
  - Scan third-party systems.

  Prepare the concrete, reviewable artifacts first, then ask.
- **Never ask me to paste secrets into chat.** Never commit secrets. Give me environment-variable or secret-manager instructions instead.
- When an external dependency is unavailable, complete and verify the local equivalent, mark the external part precisely (for example "Blocked: requires X"), and **continue with independent work**.
- Never weaken, skip, or delete a failing test to report success. Never mark a feature complete based only on generated code or a screenshot.
- **Generated code is not proof of working functionality.** Do not declare the whole scope complete when only the MVP or happy path works.
- Do not quietly remove difficult requirements. Defer them explicitly with a reason.
- Use fictional branding only:
  - The primary customer is the **same fictional hotel group, properties, and loyalty tiers already used on vamsialla.com** (Part 0.7). If the existing material names no loyalty program, define one and record it in `docs/continuity.md`.
  - The second fictional customer is **"Cedarpoint Inns,"** a different fictional hotel group.
  - No Marriott branding. Never imply a real customer engagement.
- If the session ends before completion, update the status and handoff files with the exact completed work, blockers, and next commands, so the next session continues without restarting.

### 0.4 Status labels (use these everywhere)
- **Implemented and verified:** a test or recorded check passed in this repo.
- **Implemented but unverified.**
- **Configured but untested.**
- **Simulated.**
- **Documentation-only.**
- **Manual step required:** give the exact steps.
- **Blocked:** give the precise prerequisite.
- **Deferred:** give the reason.
- **Not applicable:** give the justification.

### 0.5 Tracking files (create first, keep current)
- `docs/implementation-plan.md`
- `docs/implementation-status.md`
- `docs/requirements-matrix.md`: every requirement gets an ID, mapped to implementation files, tests, evidence, and status.
- `docs/feature-checklist.md`
- `docs/verification-log.md`: every check run, with command, date, and result.
- `docs/decisions.md`: ADR style.
- `docs/known-limitations.md`
- `docs/session-handoff.md`

Maintain **separate completion scores** for:
1. Core product functionality.
2. Benchmarks and evaluation.
3. Actual-tool exercises.
4. Protocol labs.
5. Security controls.
6. My demonstrated personal understanding.

### 0.6 Resolved design decisions
The source drafts conflicted on several points. These are the binding resolutions. Record each in `docs/decisions.md`.

| Topic | Decision |
|---|---|
| Implementer | **Claude Code is the primary implementer** for this build. Codex and Cursor are exercised as separate, attributed tool exercises (Part H). Never attribute one tool's work to another. |
| Database | PostgreSQL 16. **Alembic owns all application schema migrations.** Supabase is used as the managed PostgreSQL host (hosted profile) and for Supabase local development via its CLI. Supabase migration tooling must not also manage the application schema. |
| Identity | An `IdentityProvider` port with three adapters: (a) local demo auth (offline default), (b) local OpenID Connect provider (Keycloak in Compose) for the enterprise identity profile, (c) Supabase Auth profile. Only one adapter is active per deployment. Never run two competing auth systems at once. |
| Frontend | (1) **Server-rendered Jinja2 + HTMX + CSS console**, built first. It is the always-working operational UI and the fallback. (2) A **React/TypeScript frontend** that starts from a real bolt.new prototype, consumes the same backend API and AG-UI events, and is the candidate for Vercel hosting. If bolt.new is unavailable, the React frontend remains "Blocked: bolt.new access" and the Jinja console stays primary. Never fabricate a bolt.new artifact. |
| Hosting | Local Docker Compose first. AWS (ECS Fargate + RDS, or Supabase-hosted Postgres) for the API, worker, and mock API. Vercel only for the compatible React frontend. Never assume the worker or the full Compose stack runs on Vercel. |
| Live model | Claude API through the provider interface. Claude Code (dev tool) is distinct from the Claude API (runtime). One alternative provider (Kimi, GLM, or Qwen) is added only behind the same interface, only with access, and only with explicit selection. |
| Eval size | At least **60** labeled cases (supersedes the earlier 40). |
| Retrieval | Postgres full-text search is the baseline. Embeddings, hybrid search, or reranking only after a controlled comparison justifies them. |
| Orchestration | Plain Python state machine. A graph framework or extra agents only with a demonstrated, documented benefit. |
| Priority | Core product correctness first. Then protocols MCP → A2A → AG-UI. Then optional protocol labs and tool exercises. Never expand optional tooling while core correctness is broken. |

---

### 0.7 Portfolio continuity, reuse, and scope control (read before Milestone 1)

**Where this fits**
- vamsialla.com presents one simulated engagement for a fictional hotel group, built in stages 0–8. As of October 2026, stage 6 is unpublished.
- Its public repositories are under `github.com/vamsialladev`:
  - `hotel-ai-discovery`
  - `hotel-ops-assistant`
  - `guest-request-agent`
  - `eval-harness`
  - `hotel-ai-handoff`
  - `hotel-tools-mcp`
  - `hotel-ops-analytics-agent`
- This project is **Stage 9: Loyalty Support Modernization** for the same hotel group.

**Continuity rules**
- Before Milestone 1, read the published site and those repositories, read-only. Clone the public repos, or ask me for local paths.
- Record the following in `docs/continuity.md`:
  - Hotel group and property names.
  - Loyalty tier names and benefits.
  - Writing tone.
  - How metrics are presented (counts, runs, held-out results, dates, versions).
  - Status vocabulary.
  - Existing synthetic data shapes.
  - Existing CI and eval conventions.
- Follow those conventions so stage 9 reads as part of the same engagement.
- **Never modify the existing repositories without my explicit OK.** Prefer adapters in this repo. When a change to an existing repo is worthwhile, prepare it as a small, separate, reviewable change for me.

**Reuse rather than rebuild** (cite the reuse in the case study as evidence of platform thinking)

| Existing stage | Reuse in stage 9 |
|---|---|
| 0 Discovery & Scoping | A loyalty **addendum**, not a new discovery: FICTIONAL stakeholder sessions for loyalty, the use case scored with the same four-check test, an SOW addendum, pricing from stage 9's measured costs, and security-questionnaire deltas |
| 1 Knowledge Assistant | Same citation conventions and refusal style ("check with a manager"). Use it as a policy tool if its interface fits; otherwise document why not |
| 2 Guest Request Agent | Same approval-UX conventions. State the difference explicitly: stage 2 only proposes, stage 9 **executes** money-like actions with idempotency and reconciliation |
| 3 Eval Harness | Export stage 9 cases and results in the harness's format and register stage 9 as an additional system with regression gates. Reuse its judge-calibration approach. The A/B/C benchmark stays in this repo |
| 4–5 Production & Handoff | Reuse runbook, SLO, budget, and handoff templates. Add only what is new: write path, reconciliation, durable jobs, AWS IaC, OIDC |
| 7 MCP Server | Use the same conventions (role decides tools and fields, tenants invisible to each other, every call audited) for the loyalty read-only tools. Either extend that server through a reviewed change, or implement in `protocols/mcp/` and explain the choice |
| 8 Ops Analytics Agent | Optional: make the synthetic legacy history (Appendix F2) queryable by it for the day-one discovery analysis |

**What stage 9 must prove that stages 0–8 do not.** Lead with these:
1. **Legacy → conventional → AI comparison**, with pre-registered hypotheses and end-to-end final-ledger accuracy (Appendix F).
2. **A correct write path for money-like actions:**
   - Approval binding.
   - Idempotency.
   - Reconciliation after commit-then-lost-response.
   - Durable jobs.
   - Kill switch.
3. **An enterprise stack:** PostgreSQL, containers, CI with security scanning, AWS IaC, OIDC, OpenTelemetry, beyond free hosting.
4. **Document and vision extraction with review routing** (Appendix H).
5. **A classical-ML and small-model baseline vs. an LLM** (Appendix I).
6. **A domain-agnostic engagement method**, proven on a second mini-domain generated from the starter kit (Appendix J).

**Scope tiers (stay in one direction)**

| Tier | Contents | Milestones |
|---|---|---|
| 1. Core proof | Parts A, B, D, E; Part C items needed for the core (auth, authorization, approval integrity, injection tests); Appendix F | 1–10 |
| 2. Enterprise readiness | Rest of Part C, Part F, Appendices E, H, I, MCP/A2A/AG-UI | 11–14 |
| 3. Learning tracks and labs | Part G optional labs, Part H, Appendix G | 15–16 |
| 4. Reuse, handover, portfolio | Parts I, J, K, L, Appendix J | 17–20 |

Rules for the tiers:
- Do not start a higher tier while a lower tier's verified checks fail. Exception: Tier 3 items may stay Blocked without blocking Tier 4.
- Every piece of work maps to a requirement ID.
- New ideas go to `docs/backlog.md` with a proposed tier. They are **not built until I approve them.**

**Owned by Stage 10 (a separate future project; do not build here)**
- Kafka/event-driven posting pipeline.
- Incident investigation and AIOps over telemetry.
- Outbox pattern at scale.
- Java services.
- Workflow-automation platforms.

Record these in the backlog as "Stage 10." Stage 9 may note that some missing-points root causes are posting-pipeline failures, and that stage 10 will investigate them.

**Main portfolio storyline (what a recruiter sees in three minutes)**
- **One headline sentence of measured results:** A vs. B vs. C on held-out cases, final-ledger accuracy, false approvals.
- **One 3-minute demo:**
  1. A messy multi-stay request with a receipt image.
  2. AI investigation with citations.
  3. Supervisor approval.
  4. Execution.
  5. Injected timeout, then reconciliation, with no duplicate credit.
  6. Benchmark slide, **including where AI did not help**.
- Everything else lives in the case study and repository.

**Portfolio coverage map:** create `docs/portfolio-coverage-map.md`.
- Rows are stages 0–10. Columns are capability categories:
  - Discovery and scoping.
  - Retrieval and citations.
  - Agents and tool use.
  - Human-in-the-loop.
  - Evals and judges.
  - Legacy benchmark.
  - Write-path integrity.
  - Document AI.
  - Classical ML / fine-tuning.
  - Text-to-SQL and analytics.
  - MCP and protocols.
  - Security and governance.
  - Enterprise identity.
  - Cloud IaC and deployment.
  - Production ops and handoff.
  - Event-driven systems and observability.
  - Workflow automation.
- Mark each cell **proven (link to evidence) / planned (stage) / not covered**.
- State honestly what no stage covers, for example model pretraining, ML research, and speech.

---

## PART A: Customer discovery, business case, and governance

### A.1 Business scenario
A fictional hotel loyalty support team investigates missing-points requests such as *"I completed my stay, but my points are missing."*

Today an employee manually checks:
- Member profiles.
- Reservations and stays.
- Booking channel.
- The points ledger.
- Versioned policies.
- Supporting documents.
- Case notes.
- Adjustment history.

The employee then decides whether to adjust, request information, or escalate. A supervisor approves adjustments.

To decide, the employee must establish:
- Does the stay belong to the member?
- Is the stay eligible?
- Has the waiting period elapsed?
- Were points already credited?
- Which policy version applies?
- Is information missing?
- Is an adjustment or an escalation appropriate?

**Target end-to-end workflow:**
1. Request.
2. Authorized evidence retrieval.
3. Applicable policy, selected by business date.
4. Deterministic eligibility.
5. Explanation with citations.
6. Clarification, escalation, or proposed adjustment.
7. Supervisor approval.
8. Simulated adjustment.
9. Reconciliation of uncertain outcomes.
10. Audit history and operational metrics.

**Initial business hypotheses:**
- Reduced handling time.
- Better evidence consistency.
- Fewer duplicate adjustments.
- Better auditability.

These are **hypotheses to measure, not results**. Do not assume the legacy system is inaccurate, that customers are dissatisfied, or that AI will improve results.

**Appendix F governs how the synthetic legacy environment is built:**
- It contains realistic, pre-registered problems.
- It has a synthetic operating history.
- It models member-journey signals.
- AI must prove its improvement end to end, on held-out cases, against both the legacy and the non-AI arms.

**Core exclusions:**
- Refunds.
- Real payments.
- Real customer messaging.
- Autonomous adjustments.
- Complex multi-agent orchestration.

Commerce and payment work lives only in the sandbox labs (G.10–G.12).

### A.2 Discovery package
Create:
- `docs/customer-discovery.md`
- `docs/business-requirements.md`
- `docs/product-requirements.md`
- `docs/workflow.md`
- `docs/architecture.md`
- `docs/legacy-discovery.md`

Together they must contain:
- **Fictional customer context.**
- **Stakeholder map:** sponsor, support agent, supervisor, administrator, auditor, IT, security, operations, data owner.
- **Personas** and a **discovery interview guide**.
- **Clearly labeled FICTIONAL/SIMULATED interview examples** and assumed customer statements.
- **Workflows:** current and proposed, with the current user journey, system boundaries, ownership, manual steps, and handling costs.
- **Problem framing:**
  - Pain points.
  - Assumptions to validate with a real customer.
  - Who owns the problem.
  - What successful resolution means.
  - When ordinary software is sufficient.
  - What AI adds.
  - Conditions for stopping or redesigning the project.
- **Requirements:** business requirements, nonfunctional requirements, MVP scope, and exclusions.
- **Systems and data:** system inventory, integration constraints and contracts, and a data quality assessment.
- **Registers:** an access and dependency register, a risk register, and dependencies.
- **Success measures:** success metrics and acceptance criteria.
- **Planning:** a pilot and rollout plan, a milestone plan, and a scope-change template.
- **Responsibility and ownership matrix (RACI).**
- **Architecture:** an architecture diagram, technical tradeoffs, and an explicit separation of prototype, pilot, and production expectations.

### A.3 Decisions to document (`docs/decisions.md`)
- AI versus deterministic rules. AI is used for interpreting requests, summarizing evidence, finding policy text, and explaining recommendations. Eligibility, calculations, permissions, approvals, and execution stay deterministic.
- Build versus buy.
- Managed versus self-hosted components.
- Integration options.
- REST versus MCP.
- Full-text search versus embeddings.
- Single agent versus complex orchestration.
- Data processing boundaries.
- Operational ownership.

Include a **decision guide** explaining when each of these would be useful:
- Managed backends.
- Visual prototyping tools.
- External code review.
- Workflow automation.
- Self-hosted models.

### A.4 Governance and ownership
- Define responsibility boundaries for:
  - The application/FDE team.
  - The identity team.
  - The platform/cloud team.
  - The security team.
  - The data owner.
  - The product/business owner.
  - Incident response.
  - Vendor management.
- Create templates for access requests, security exceptions, and risk acceptance. Each exception needs a named owner, rationale, compensating controls, and an expiry date.
- Distinguish technical controls implemented here from organizational controls that need external owners. **Never fabricate approvals or sign-offs.**

---

## PART B: Core product

### B.1 Technology
- **Language and API:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL 16.
- **UI:** Jinja2 + HTMX + CSS (no JavaScript build system) for the core console, and React/TypeScript for the bolt.new-based frontend (see 0.6).
- **Background work:** a durable, database-backed job queue and worker.
- **AI:** Claude through an application-owned provider interface, plus a deterministic offline mock provider.
- **Testing:** pytest and Playwright.
- **Delivery:** Docker Compose and GitHub Actions.
- **Observability:** structured logging and OpenTelemetry.
- **Shape:** a modular monolith plus a separate mock customer API service. Avoid unnecessary microservices, agent frameworks, vector databases, extra databases, or multiple model providers.
- **Ports and adapters:** domain code never imports web, database-session, HTTP, or model-SDK code directly. Keep the reusable foundation separate from loyalty-specific rules. All business logic stays in Python.

### B.2 Operating profiles
Provide explicit configuration profiles:

1. **Portfolio (default)**
   - Synthetic data, local mock APIs.
   - Offline AI provider by default; live model optional with a budget cap.
   - Restricted public-demo capabilities.
2. **Live-model mode**
   - Explicit credentials, spending caps, per-request and per-run budgets.
3. **Customer discovery**
   - Synthetic customer-shaped examples, configurable policies and field mappings.
   - No real customer connections by default.
4. **Hosted staging**
   - Supabase-hosted database, Vercel frontend, and AWS API/worker, once authorized.
5. **Approved deployment / company**
   - Configured enterprise identity, authorized integration endpoints, managed secrets.
   - Explicit model and telemetry destinations, production configuration checks.
6. **Enterprise identity demo**
   - Local OIDC provider.

Rules for all profiles:
- The UI always shows a banner: **SYNTHETIC DATA** · active profile · AI mode (MOCK / LIVE: model ID / provider) · customer configuration.
- Never describe mock responses as live model results.
- **Never silently fall back** from an approved provider to another provider or data destination.
- Provide a **preflight command** (`python -m app.preflight --profile X`) that reports configuration readiness without printing secret values.
- Separate four access types: developer-assistant access, runtime model access, customer-system access, and deployment access. **One never implies another.**

### B.3 Synthetic customer systems (separate mock service)
Endpoints:
- Member lookup.
- Stay lookup.
- Points ledger lookup.
- Support ticket creation.
- Adjustment submission (requires an idempotency key).
- Adjustment status lookup.

Requirements:
- **Contracts:** versioned OpenAPI contracts and adapter interfaces, so real systems can replace the mocks later.
- **Responses:** realistic identifiers and timestamps, pagination, and typed error responses.
- **Persistence:** a persistent store. **The operation and its idempotency record are persisted atomically** in one transaction.
- **Handled failure cases:**
  - Pagination.
  - Authentication failures.
  - Rate limits (429).
  - Timeouts.
  - Transient errors (503).
  - Malformed or invalid responses.
  - Schema changes and mismatches.
  - Duplicate requests.
  - Partial failures.
  - **Adjustment completed but response lost.**
- **Deterministic failure injection** for demos and tests, via a header and seeded scenarios.
- **Control commands:** reset and seed.
- **Contract tests** and **reconciliation jobs**.

Seeded scenarios must cover:
- Eligible stay with missing points.
- Points already credited.
- Missing member or stay.
- Stay not checked out.
- Stay within the waiting period.
- Ineligible booking channel.
- Conflicting records.
- Missing documentation.
- Upstream timeout.
- Rate limiting.
- Temporary upstream failure.
- Adjustment completed but response lost.

### B.4 Two fictional customers (configuration, not a copy)
The primary hotel group and Cedarpoint Inns differ in:
- Policy rules.
- Upstream field mappings.
- Waiting periods.
- Approval limits.

Rules:
- Adapt through configuration and adapters, never by copying the codebase.
- Use **separate deployment profiles and databases**. Do not claim tenant isolation because a `customer_id` column exists, and do not claim shared multitenancy unless it is implemented and tested.

### B.5 Synthetic data generator
- Reproducible: fixed seeds, configurable scale, referential integrity, realistic timestamps.
- Generates:
  - Members.
  - Stays.
  - Booking channels.
  - Ledger entries.
  - Policy versions.
  - Support requests.
  - Case notes.
  - Investigation events.
  - Approvals.
  - Adjustments.
- Includes straightforward cases and these scenarios:
  - Eligible with missing points.
  - Already credited.
  - Posting delay within the waiting period (include exact boundary days).
  - Stay not completed.
  - Ineligible booking channel.
  - Incorrect or missing member association.
  - Missing member.
  - Missing stay.
  - Duplicate stay records.
  - Incomplete stay information.
  - Conflicting timestamps.
  - Historical policy changes.
  - Ambiguous messages.
  - Different descriptions of the same problem.
  - Multiple stays in one request.
  - Missing evidence.
  - Duplicate submissions.
  - Upstream delays and outages.
  - Embedded prompt-injection text.
- Scenario proportions are documented, configurable **assumptions**.
- Synthetic data must never be derived by renaming real records. Language fluency is not proof of realistic traffic.
- Provide seed, reset, and cleanup commands.
- Document every field in `docs/data-dictionary.md`.

### B.6 Data readiness, policies, and retrieval
- For each source, identify the authoritative source, freshness requirement, field mapping, ownership, and conflict-resolution rule.
- Validate missing, conflicting, stale, and changed data.
- **Fictional versioned policies:**
  - Fields: title, document and section IDs, effective dates, source checksum, publication status (draft/published/superseded), superseded versions.
  - One configurable policy set per customer.
- **Ingestion pipeline:** ingestion, validation, chunking, storage of source text, and PostgreSQL full-text retrieval as the baseline.
- **Retrieval:**
  - Select the applicable policy by the **relevant business date** (stay checkout date).
  - Citations open the exact stored excerpt and version.
  - Record evidence provenance and retrieval time.
- **Publishing:** a controlled policy publishing workflow with regression checks. A changed policy or changed evidence **invalidates affected pending approvals**.
- **Evidence handling:**
  - Handle missing policy, conflicting policies, stale evidence, unsupported claims, ineligible stays, and incomplete records.
  - **Never invent policy.** Escalate when the available policy cannot support a recommendation.
  - Authorization filters content **before** it enters model context.
- **Sensitivity:** treat embeddings, caches, and derived summaries as potentially sensitive.
- **Documentation:** document the retrieval approach and its limitations.

### B.7 Deterministic eligibility
- Pure Python rules, parameterized by customer configuration.
- Returns a typed result: `eligible | ineligible | insufficient_evidence | needs_escalation`, plus points, reasons, and policy references.
- The model can interpret and explain but **can never override** eligibility, calculation, permissions, approval, or execution.

### B.8 Three comparison arms (Part E benchmarks them)
**A. Legacy baseline** (built first, credible, runnable):
- A basic case queue.
- Separate member and stay searches.
- Ledger lookup.
- Keyword policy search.
- Deterministic eligibility rules.
- Manual evidence collection.
- Manual notes and escalation.
- Supervisor approval.
- Simulated adjustment.

Do not make it intentionally incompetent, insecure, or incomplete. In `docs/legacy-discovery.md`, document its limitations, distinguishing:
- Known functionality.
- Missing functionality.
- Configuration errors.
- Data problems.
- Operational delays.
- UI friction.

**B. Improved conventional (no generative AI):**
- Corrected rules.
- Consolidated evidence.
- Better filters.
- Improved keyword and full-text search.
- Data validation.
- Automated deterministic calculations.
- An improved interface.

This arm is also the **manual/fallback mode** when the model is unavailable.

**C. AI-assisted:**
- B plus request interpretation.
- Targeted retrieval.
- Evidence summarization.
- Policy explanation with citations.
- Missing-information detection.
- Resolution drafting.
- Human-reviewed recommendations.

Rules for all arms:
- Authorization, approval, and execution safeguards are **identical** across arms.
- AI gets no access to hidden ground truth or better source records unless that is an explicitly separate experiment.
- Document every difference between arms. Do not credit interface or integration improvements to AI.

### B.9 AI engineering (document all of it in `docs/ai-engineering-matrix.md`)
For each discipline, record:
- The problem it solves.
- Implementation location.
- A learning exercise.
- Tests and measured results.
- Tradeoffs and limitations.

The disciplines are prompt, context, tool, agent, loop, workflow/graph, retrieval, memory/state, harness, evaluation, reliability/platform, and human oversight/feedback engineering. These labels are a learning structure, not a claim about a standard taxonomy.

**Prompt engineering:**
- Versioned templates with a clear task and constraints, typed output expectations, examples where useful, and explicit missing-information and escalation behavior.
- Trusted instructions are separated from untrusted content.
- No secrets or authorization decisions in prompts.
- A prompt regression suite. Meaningful changes are compared on held-out cases, never chosen from a few demos.

**Context engineering:**
- A context builder that selects:
  - The current request.
  - Authorized member and stay evidence.
  - Relevant ledger entries.
  - Applicable policy excerpts.
  - Prior investigation state.
  - Remaining budget.
- A configurable context budget, and targeted retrieval rather than whole documents.
- Track evidence provenance and freshness.
- **Prompt minimization:** send only the fields needed for the task, and redact secrets and unnecessary PII.
- If compaction is used:
  - Keep references to the original evidence.
  - Keep unresolved questions.
  - Never treat summaries as authoritative facts.
  - Revalidate critical facts before approval or execution.
- Test irrelevant, missing, conflicting, and long-history context.

**Tool engineering:**
- Tools have:
  - A narrow purpose.
  - Validated input and output schemas.
  - Clear descriptions.
  - Authorization checks.
  - Timeouts and limited retries.
  - Structured errors.
  - Bounded response sizes.
  - Correlation IDs.
- Large results are returned as bounded summaries plus identifiers.
- Read-only tools are separate from state-changing services.
- The model never decides its own permissions.
- Test malformed arguments, unavailable tools, access denial, and oversized results.
- **Read-only investigation tools:** `get_member`, `get_stay`, `get_points_ledger`, `search_policy`, `evaluate_eligibility`.
- Drafting a resolution (`draft_resolution` in early drafts) is a **validated application service** that persists the recommendation, not an unrestricted model capability.
- **Never give the business agent arbitrary SQL, shell, filesystem, browser, network, payment, or adjustment authority.**

**Runtime agent loop** (an explicit state machine, not an unbounded while loop):
1. Load authorized case state.
2. Assemble bounded context.
3. Request a structured model response.
4. Validate the requested tool calls against the allowlist and schema.
5. Authorize and execute the permitted tools.
6. Persist the outcomes and updated state.
7. Check progress and budgets.
8. Continue, produce a validated recommendation, request information, or escalate.

Stop conditions, **each with a test**:
- Sufficient evidence and a valid recommendation.
- Missing information requiring a user response.
- An unauthorized action request.
- Repeated tool calls without new evidence.
- Unresolvable conflict.
- Maximum steps.
- Token or cost budget reached.
- Wall-clock deadline.
- Cancellation.
- Repeated provider or tool failures.

Limits are configurable, and their rationale is documented. The loop never runs indefinitely or retries until the budget is exhausted.

**Workflow and graph engineering:**
- Intake → evidence gathering → policy retrieval → deterministic eligibility → recommendation validation.
- Then one of four branches:
  - Awaiting information.
  - Human escalation.
  - Pending approval.
  - No adjustment required.
- After approval: execution → confirmed success or uncertain outcome → reconciliation.
- Persist transitions.
- Parallelize independent read-only retrieval with bounded concurrency. Keep dependent writes ordered.
- Test invalid transitions, duplicate events, cancellation, and restart recovery.
- No extra agents just for a diagram.

**Runtime execution harness:**
- Components:
  - Run ID and case ID.
  - Authenticated caller context.
  - Tool registry and allowlist.
  - Provider adapter.
  - Context builder.
  - Schema validation.
  - Budget and deadline enforcement.
  - Retry policy.
  - Cancellation.
  - Persistent checkpoints.
  - Trace and audit hooks.
  - Final-result validation.
- Store run metadata: prompt version, model ID, policy version, tool-call statuses, usage, timing, and the completion or stop reason.
- Keep secrets out of traces.
- Document that **exactly-once business effects require downstream cooperation**. A local checkpoint cannot guarantee them.

**Memory and state:**
- Separate the model context, durable case state, execution checkpoints, optional user preferences, and audit history.
- The database is the source of truth for business state.
- Conversational memory is never proof of identity, approval, eligibility, or execution.
- Apply authorization and retention rules to persisted state.
- Test stale state, concurrent updates, case separation, and deletion.
- No vector memory store without an evaluated need.

**Validation and bounded revision:**
- Validate the final output for:
  - Required fields.
  - Supported citations.
  - Consistency with deterministic eligibility.
  - Permitted actions.
  - Disclosure of missing information.
- One bounded repair attempt for repairable problems. After that, escalate or use the deterministic fallback.
- Self-review is not independent proof.
- **Never request or store hidden chain-of-thought.** Record observable actions, evidence references, concise decision summaries, and validation results.

**Recommendation contents:**
- Case summary.
- Observed facts.
- Eligibility result (from the deterministic engine).
- Evidence and policy citations.
- Missing information.
- Proposed or recommended action.
- Escalation reason when applicable.

**No uncalibrated confidence percentages.**

### B.10 Case state machine, approval, and execution integrity
**States:** `New`, `Investigating`, `Awaiting information`, `Pending approval`, `Approved`, `Executing`, `Resolved`, `Escalated`, `Rejected`, `Execution unknown`. Validate transitions server-side, document them with a diagram, and support case reopening.

**Roles:**
- Agents create and investigate cases.
- Supervisors approve or reject.
- Administrators manage configuration.
- Auditors have read-only access.

**Approval binding** covers the exact proposed action:
- Member and stay.
- Adjustment amount.
- Policy version.
- Evidence snapshot.
- Approver identity.
- Expiration time.

**Approval rules:**
- Supervisor approval is required.
- **The creator cannot approve their own adjustment.**
- A model response, browser field, or user-supplied field can never grant approval or a role.
- Any change to the amount, member, stay, policy, or relevant evidence **invalidates approval**.

**Execution:**
- Revalidate eligibility and existing ledger credits immediately before execution.
- Use concurrency control (row locks or optimistic versioning) plus upstream idempotency, so concurrent actions cannot create duplicate adjustments.
- On timeout or an uncertain outcome, move to `Execution unknown` and run **status reconciliation before any retry**.

**Emergency switch:** disables all adjustments while keeping read-only investigation running. Test it under concurrent requests.

**Audit history:**
- Covers decisions, approvals, rejections, executions, reconciliation, and overrides.
- Has restricted modification permissions (an append-only DB role).
- **State its actual integrity guarantees honestly.** Never claim tamper-proof unless that property is implemented and tested.

### B.11 Data model and API
**Alembic migrations** for:
- Users and roles.
- Cases.
- Case evidence.
- Policy documents and chunks.
- Recommendations.
- Approvals.
- Execution attempts.
- Idempotency records.
- Jobs.
- Audit events.
- Evaluation and benchmark runs.
- Feedback and overrides.

**APIs** for:
- Creating and listing cases.
- Viewing a case.
- Starting an investigation.
- Supplying missing information.
- Viewing recommendations and citations.
- Approving and rejecting.
- Executing.
- Execution status.
- Audit history.
- Aggregate metrics.
- Feedback.

**API quality:** pagination, input validation, consistent errors, and generated OpenAPI docs. Prevent accidental duplicate investigation runs.

### B.12 Durable processing
- A persistent job queue with:
  - Worker leases.
  - Heartbeats.
  - Recovery of abandoned jobs.
  - Bounded retries with backoff.
  - Dead-job handling.
  - Duplicate-job prevention.
  - Graceful shutdown.
  - Correlation IDs.
- **No in-memory background tasks for critical work.**
- Document transaction boundaries and failure semantics.
- Retries and restarts must not create duplicate business effects.
- Cache only where correctness and authorization allow, with defined invalidation and expiry.

### B.13 User interface
**Console features:**
- Login.
- Case queue with filters and statuses.
- Case creation.
- Case detail.
- Member, stay, and ledger evidence panels.
- Investigation progress.
- Recommendation with clickable citations opening the exact excerpt.
- Missing-information prompts and workflow.
- Supervisor approval and rejection with reasons.
- Execution and reconciliation status.
- Audit timeline.
- Operational metrics.
- Feedback and override-reason capture.
- The visible synthetic-data and mode indicator.

**Evaluation-only comparison dashboard:**
- Shows the same case across the A/B/C arms: evidence, expected outcome (evaluation mode only), actual decision, citations, time and cost, failure category, and human review result.
- Includes examples where legacy works, a non-AI fix solves the problem, AI adds value, AI fails or escalates, and no system can answer.
- **Never cherry-pick.** Never expose ground truth to operational users.

**Quality bar:**
- Responsive, keyboard navigable, accessible labels, readable (AA) contrast.
- Useful loading, empty, error, and retry states.
- Correct time zones and date boundaries.
- Documented localization limits.
- **Every visible control has implemented behavior.**

---

## PART C: Security, identity, and data governance

### C.1 Baseline and evidence
- Consult current official versions of:
  - NIST AI RMF and its Generative AI Profile.
  - NIST SSDF.
  - OWASP ASVS.
  - OWASP generative AI and agentic security guidance.
  - The protocol security specifications.
  - Platform and identity-provider guidance.
- Record versions and access dates. Select applicable controls and explain exclusions.
- **Never claim certification, regulatory compliance, SOC 2, enterprise approval, or perfect security.**

Create:
- `security/system-inventory.md`
- `security/data-flow.md`
- `security/threat-model.md` (canonical; `docs/threat-model.md` links to it)
- `security/risk-register.md`
- `security/control-matrix.md`
- `security/test-plan.md`
- `security/test-results.md`
- `security/evidence/` (sanitized)
- `security/residual-risks.md`
- `security/incident-runbooks.md`
- `security/production-readiness.md`
- `docs/production-readiness.md`

For each control, record: requirement, threat, owner, implementation location, evidence, result, and limitation.

### C.2 Threat model
**Trust boundaries:**
- Browser and frontend.
- Backend.
- Agent runtime.
- Worker and queue.
- Database and storage.
- Model provider.
- MCP servers.
- Remote agents.
- Customer APIs.
- CI/CD.
- Monitoring.
- External development tools.

**Actors and threats:**
- Malicious users.
- Compromised accounts.
- Malicious documents and tool responses.
- Compromised dependencies.
- Overprivileged services.
- Misconfiguration.
- Insider misuse.
- Accidental disclosure.
- Replay.
- Resource exhaustion.

Prioritize by impact, likelihood, and exposure. Update the model whenever integrations change.

### C.3 Data governance and tool register
Create:
- `docs/tool-and-access-register.md`
- `docs/data-flow-map.md`
- `docs/data-classification.md`
- `docs/customer-access-checklist.md`
- Onboarding and offboarding/access-revocation checklists.

Distinguish these categories:
- **A.** Development assistants.
- **B.** Runtime model services.
- **C.** Customer system integrations.
- **D.** Logs, traces, analytics, exports, backups, and evaluation datasets.

For each connection record:
- Purpose.
- Account owner.
- Data categories.
- Read/write scope.
- Permitted environment.
- Credential storage.
- Retention assumptions.
- Auditability.
- Approval status (never claim simulated approvals are real).
- Revocation procedure.
- Whether it is implemented, simulated, or documentation-only.

**Implement:**
- Data minimization before model calls.
- Redaction of secrets and unnecessary personal fields (redaction is risk reduction, not anonymization).
- Configured outbound destinations.
- Integration timeouts.
- Safe diagnostic output.
- **Retention and deletion jobs**, including derived indexes and caches. Document backup-deletion limits.

Further rules:
- Provider settings are recorded as unverified unless confirmed. "Not used for training" does not mean no retention or company approval.
- These controls do not make arbitrary client data permissible.
- Never connect personal browser sessions or real company repositories automatically.

### C.4 Identity and authentication
- **Local demo auth:**
  - Securely hashed passwords (argon2 or bcrypt).
  - Server-managed sessions with environment-appropriate cookie settings.
  - CSRF protection for browser mutations.
  - Login and endpoint rate limiting.
  - Session expiry and revocation.
  - Account deactivation.
  - Secure recovery flow.
- **Enterprise OIDC profile (local Keycloak) and Supabase Auth profile:**
  - Signature verification, issuer, audience, and expiry checks.
  - Key-rotation behavior.
  - Maintained protocol libraries only. **No custom cryptography.**
- **MFA:** stronger authentication for privileged users where the IdP supports it. Don't claim MFA enforcement if only a guide exists.
- **Workload identity:** separate human identity from workload identity, and prefer short-lived workload credentials.
- **Documentation:** document local auth limitations and how enterprise identity replaces it.

### C.5 Authorization and record isolation
- **Backend checks on every operation:**
  - Deny by default, least privilege.
  - Validate role, deployment/customer scope, record access, requested action, and workflow state.
- **Tests** for object-level authorization, role escalation, cross-user, and cross-customer access.
- **Supabase:**
  - Privileged keys stay server-side and never reach the browser.
  - Test the **actual** database access path.
  - Use RLS where appropriate, but **don't assume RLS protects elevated connections**. Enforce and test backend restrictions independently.

### C.6 Secrets, crypto, and network
- **Secrets:**
  - Environment injection or an approved secret manager. `.env.example` without real secrets.
  - Secrets must not appear in Git history, browser bundles, logs, screenshots, fixtures, prompts, or errors.
  - Secret scanning, plus rotation and revocation procedures. Test rotation where feasible.
- **Encryption:** TLS for connections and encryption at rest. Distinguish verified local settings from managed-service settings.
- **Network and outbound access:**
  - Allowlisted outbound destinations.
  - Private databases and admin interfaces.
  - SSRF protection for URL fetching, discovery, callbacks, and webhooks: block internal networks, cloud metadata, redirect bypass, unsupported schemes, oversized responses, and slow responses.
  - No model-selected arbitrary URLs.
  - Document how browser- or cloud-hosted agents reach authorized services.

### C.7 AI input, output, and UI security
- **Inputs:**
  - Treat user text, documents, retrieved passages, and tool output as untrusted.
  - Don't rely solely on prompt wording or an injection detector.
- **Ingestion** (if uploads exist):
  - Authorized retrieval before content enters context.
  - Controlled publication, ingestion validation, and file size and type limits.
  - Safe parsing and quarantine.
  - Protection against path traversal and archive expansion.
- **Outputs and UI:**
  - Schema-validate outputs, then encode and sanitize them.
  - Protect against XSS, unsafe links, SQL/command injection downstream, and sensitive-data disclosure.
  - CSP, secure cookies, CSRF, restricted CORS (CORS is not authorization).
  - Client-side state never grants authority.
  - No detailed stack traces in user-facing errors.
- **Code execution:** any code-execution lab is isolated, with no production secrets, no host mounts, and no unrestricted network.

### C.8 Public demo mode
- Synthetic records only.
- Restricted administration and destructive operations.
- No shared writable admin account.
- Reset limited to a controlled mechanism.
- Request limits and model usage and spending budgets.
- All secrets server-side.

### C.9 Security testing and AI red-team suite
**Owned or authorized environments only.** Write repeatable tests for:
- Broken authentication and role escalation.
- Unauthorized record access.
- Direct and indirect prompt injection that tries to bypass policy, reveal secrets, access another customer, or execute an adjustment.
- Tool misuse and unsupported claims.
- Secret extraction.
- Malicious and poisoned documents.
- Unsafe generated output.
- SSRF and malicious callbacks.
- Approval tampering.
- Duplicate execution and replay.
- Expired credentials.
- Worker interruption and provider outage.
- Budget exhaustion and resource exhaustion.
- Cross-user stream access.

How to run and report the suite:
- **Assert on business effects and access boundaries, not refusal wording.**
- Repeat selected model-based tests to expose variability.
- Report attempted cases, failures, and residual risks.
- Never claim prompt injection is solved.

### C.10 Monitoring, incidents, release gates, maintenance
- **Security event logging:**
  - Covers failed auth, denied authorization, privilege changes, tool execution, approval and execution, suspicious repeats, budget limits, configuration changes, and credential revocation.
  - Minimal sensitive content, restricted log access, defined retention.
  - Alerts with owners and runbooks.
- **Incident exercises:** response procedures for each of the following, each covering containment, revocation, investigation, recovery, and post-incident improvement:
  - Leaked model key.
  - Compromised integration credential.
  - Unauthorized data access.
  - Malicious policy document.
  - Unexpected agent action.
  - Compromised dependency.
  - Excessive model spending.
- **Release gates:** separate gates for local/demo, staging, and production, requiring:
  - Authorization tests passing.
  - Approval and idempotency tests passing.
  - No exposed secrets.
  - Validated configuration.
  - Triaged findings.
  - High-impact risks with accountable decisions.
  - Monitoring and recovery in place.
  - Required external reviews identified.

  Use wording like: *"Technically verified for the tested scope; organizational approvals pending."*
- **Maintenance schedule**, with an owner and evidence requirement per activity:
  - Dependency and container updates.
  - Access reviews.
  - Provider changes.
  - Protocol upgrades.
  - Prompt, model, and policy changes.
  - Regression evaluations.
  - Restore drills.
  - Incident exercises.
  - Retention jobs.
  - Exception expiry.

  A change to a model, prompt, tool, policy, or protocol triggers the relevant tests. Never auto-deploy prompt or feedback changes.

---

## PART D: Testing

Implement:
- **Unit tests:**
  - Eligibility and date boundaries.
  - Policy version selection.
  - State transitions.
  - Approval binding.
  - Redaction.
- **Real PostgreSQL integration tests:**
  - Idempotency atomicity.
  - Concurrent approval and execution.
  - Duplicate prevention.
  - Timeout after upstream commit.
  - Status reconciliation.
  - Worker restart recovery.
  - Approval invalidation.
  - Object-level authorization.
- **Contract tests** against the mock API, including malformed and schema-changed responses.
- **AI harness tests:**
  - Every stop condition.
  - Malformed tool arguments.
  - Unauthorized tool requests.
  - Prompt injection.
  - Citation provenance.
  - Missing and conflicting information.
- **Security tests** (Part C.9).
- **Failure-injection tests:**
  - Upstream failures, timeouts, rate limits.
  - Provider outage.
- **Protocol tests** (Part G).
- **Playwright browser tests:**
  - The complete create → investigate → approve (as a different supervisor) → execute → resolved flow.
  - Self-approval blocked.
  - Escalation.
  - Missing information.
  - Supervisor rejection.
  - Reopening.
  - Reconciliation.

Deterministic system tests are separate from model evaluations. One offline command runs everything (`make test` and a PowerShell equivalent).

---

## PART E: Evaluation, legacy measurement, and benchmarking

### E.1 Datasets and ground truth
- **Size and splits:** at least **60 labeled synthetic cases**, split into development, validation, held-out test, and stress-test sets.
  - Group related members, duplicates, and paraphrases within one split to prevent leakage.
  - Use temporal or policy-family splits for historical-policy tests.
  - Record dataset versions and checksums.
- **Labels:** ground truth comes from explicit scenario facts and independently reviewed rules. For each case it gives:
  - Applicable policy.
  - Eligibility.
  - Expected points.
  - Existing-credit status.
  - Required evidence.
  - Correct next action.
  - Clarification need.
  - Escalation need.
- **Valid answers:** "Insufficient evidence" and "requires clarification" are valid labels.
- **Independence:** the evaluated AI is never the sole labeler. Expected answers and generator metadata are inaccessible to the application.
- **Review:** provide a label-review interface or reviewable file, and record reviewer status. If no independent human reviewed the labels, disclose that.
- **Held-out discipline:** never tune on held-out data. If held-out data becomes development data, create a new held-out set.

### E.2 Legacy measurement and root causes
- **Create:**
  - `docs/baseline-measurement-plan.md`
  - `docs/root-cause-analysis.md`
  - `docs/experiment-plan.md`
  - `docs/error-analysis.md`
- **Instrument the legacy arm** to capture:
  - Correct outcome and eligibility.
  - Incorrect approval and incorrect denial.
  - Appropriate escalation.
  - Missing-info detection.
  - Time to find evidence.
  - Time to complete.
  - Manual steps.
  - Reopened cases.
  - Duplicate adjustments.
  - Overrides.
  - System errors.

  Automated software metrics are kept separate from human usability measurements.
- **Case-by-case root-cause analysis.** Categories:
  - Missing or incorrect source data.
  - Delayed upstream.
  - Integration failure.
  - Incorrect rules.
  - Outdated policy configuration.
  - Poor search.
  - Ambiguous language.
  - Fragmented UI.
  - Excessive manual work.
  - Training or process issue.
  - Unknown.

  For each issue give: reproduction, expected vs. actual outcome, evidence, frequency, business consequence, and recommended intervention.
- **Not every problem is an AI opportunity.** Say when the fix is data cleanup, integration repair, policy correction, UI improvement, or training.

### E.3 Benchmark system
**Directory structure:**
- `benchmarks/configs/`
- `benchmarks/datasets/`
- `benchmarks/runner/`
- `benchmarks/results/`
- `benchmarks/reports/`
- `benchmarks/benchmark-thresholds.yaml`, written **before** any evaluation runs.

**Config fields:**
- Dataset version.
- Workflow arm.
- Model and provider.
- Prompt version.
- Retrieval configuration.
- Tool permissions.
- Loop and context limits.
- Timeout and retry policy.
- Concurrency.
- Repetitions.
- Cost ceiling.
- Environment.
- Cache state.

**Commands:** one command runs a benchmark (smoke or full); one compares runs.

**Layers benchmarked separately:**
- **Component:**
  - Retrieval relevance.
  - Policy version selection.
  - Structured extraction.
  - Tool selection and arguments.
  - Citation support.
  - Eligibility.
- **Agent:**
  - Task success.
  - Loop termination.
  - Correct escalation.
  - Recovery after interruption.
  - Tool-call efficiency.
  - Budget compliance.
- **Application:**
  - Correct completed case.
  - Approval enforcement.
  - Duplicate prevention.
  - Reconciliation.
  - Browser workflow completion.
  - API and investigation latency.
- **Business:**
  - Time and cost per *correctly resolved* case.
  - Human review and correction effort.
  - Rework.
  - Escalation.
  - Task completion.
  - Satisfaction (only when actually measured).

**Metrics to report:**
- Eligibility and recommended-action accuracy.
- **False approvals and false denials, reported separately.**
- Clarification and escalation correctness.
- **Coverage alongside accuracy.**
- Unsupported claims.
- Citation correctness.
- Retrieval relevance.
- Missing-information detection.
- Unauthorized actions.
- Duplicate effects.
- Tool failures and retries.
- Latency (median and tail, where the sample supports it).
- Tokens and cost.

**Reporting rules:**
- Always report counts, denominators, and per-scenario breakdowns. Don't hide dangerous errors inside an aggregate.
- Weighted-loss weights are documented assumptions.

### E.4 Fairness, statistics, and comparisons
- **Fair runs:** paired cases with comparable infrastructure. Declare cache state, simulated dependencies, and variability.
- **Repeats:** repeat selected live cases.
- **Uncertainty:** give estimates where justified. No significance claims without appropriate analysis. Separate statistical difference from practical value.
- **Engineering comparisons**, one factor at a time, with ablations:
  - Prompts.
  - Context selection.
  - Retrieval.
  - Model or provider.
  - Loop limits.
  - Structured validation.
  - Bounded revision.
  - Rules-only vs. retrieval + structured generation vs. bounded agent.
- **Complexity:** more complex designs must show measurable benefit.
- **LLM judge:** only if calibrated against human labels, with disagreement documented, and never the sole measure. Use human rubrics where needed.

### E.5 Mock vs. live separation
- Keep these distinct throughout the UI, docs, and reports:
  - Deterministic offline tests.
  - Live provider smoke tests.
  - Live model evaluations.
- **Mock success is never evidence of live Claude quality.**
- Run live evaluation only with credentials and a configured spending cap. Otherwise record **NOT RUN**.
- Store dataset, prompt, model, policy, and application versions with every run.

### E.6 Thresholds, failure loop, and release gates
- **Thresholds:**
  - Defined before evaluation: minimum quality, maximum false-approval and false-denial rates, escalation behavior, latency and cost limits, and the minimum worthwhile improvement over the non-AI arm.
  - Business thresholds are **provisional** until stakeholder-approved; never invent approval.
  - Authorization, approval, and duplicate-prevention tests must pass 100%. Zero observed failures does not prove zero risk.
- **Improvement loop:**
  - Observe → classify → reproduce → fix the responsible component → rerun → review → release.
  - Failure classes: data, retrieval, context, model, tool contract, business logic, authorization, infrastructure, UX.
  - Failing cases join the regression suite.
  - No automatic prompt changes or retraining from feedback.
- **Release:**
  - A changed prompt, model, policy, tool, retrieval setup, or code triggers regression evaluation before release.
  - Keep a known-good configuration for rollback.
  - Never silently change production model settings.

### E.7 Business value and timing
**Business metrics, measured where evidence exists:**
- Time and cost per correctly completed case.
- Manual steps.
- Rework.
- Escalations.
- Acceptance and overrides.
- Model and API usage.
- Infrastructure.
- Review, support, integration, and maintenance effort.

**Calculations:**
- Absolute percentage-point change.
- Relative change.
- Incremental AI cost.
- Break-even volume under explicit assumptions.

**Labeling:** keep observed, estimated, assumed, and unmeasured values clearly apart.
- Never extrapolate synthetic gains to guaranteed savings.
- Never present scripted timing as employee handling time.
- Measure cost only where usage and pricing inputs are known.

**Human timing protocol:** a repeatable manual-versus-assisted protocol (`docs/timing-protocol.md`).
- Same or equivalent representative cases.
- Counterbalanced order.
- Participant experience recorded.
- Sample-size limits stated.
- Report only measured values.

**Satisfaction:** a short task-based survey, with real participants only. Otherwise mark it **unmeasured**. Synthetic cases cannot establish customer satisfaction.

**Conclusion** (`docs/business-value-report.md`), chosen by the evidence:
- AI adds meaningful value, or
- Non-AI fixes deliver most of the value, or
- AI helps only certain categories, or
- Evidence is insufficient, or
- AI isn't justified.

### E.8 End-to-end proof and the required demonstrations
- **End-to-end flow:** request → evidence → policy → decision → explanation → approval → simulated adjustment → reconciliation → audit. A better text answer is not success if the action is wrong.
- **Scenarios to test:**
  - Changed policy.
  - Existing credit.
  - Missing evidence.
  - Duplicate submission.
  - Timeout after commit.
  - Incorrect AI recommendation.
  - Supervisor rejection.
  - Reopening.
- **Required demonstrations.** For each, record the observable trace, expected behavior, actual result, and test evidence in `docs/demonstrations.md`:
  1. Successful bounded investigation.
  2. Missing evidence leading to a question.
  3. Conflicting evidence leading to escalation.
  4. Repeated tool calls stopped by the loop controller.
  5. A run stopped by budget.
  6. An interrupted worker safely resumed.
  7. An unauthorized tool request rejected.
  8. A policy change invalidating approval.
  9. An uncertain adjustment reconciled without duplication.
  10. A prompt or model change evaluated before release.

---

## PART F: Performance, observability, deployment, operations

### F.1 Performance and observability
- **Load testing:**
  - Declare a realistic load profile and run a bounded load test.
  - Report API vs. investigation latency, throughput, queue age and delay, failure rate, and database behavior.
  - Identify simulated dependencies.
- **Instrumentation:**
  - `/healthz` and `/readyz`.
  - Structured logs with correlation IDs.
  - OpenTelemetry traces with trace-context propagation.
  - Sensitive-data filtering.
- **Metrics:** latency, failures, escalations, approvals, tool usage, queue, per-case model usage and cost, and provider spend tracking.
- **Dashboards and alerts:** operational dashboards, and actionable alerts linked to runbooks.
- **Platform reliability:**
  - Per-request and per-run budgets.
  - Bounded concurrency.
  - Circuit breakers where justified.
  - Backoff for transient errors only, never for permanent ones.
  - Queue backpressure.
  - Provider-outage handling with a manual fallback.
  - Feature flags for live AI and for adjustment execution.
- **SLOs:** proposed service objectives (API availability, investigation completion, queue age, reconciliation) kept separate from measured results. **No production-availability claims from local tests.**

### F.2 Delivery and supply chain
- **Containers:**
  - Non-root Dockerfiles where compatible, with resource limits.
  - Compose profiles: demo, test, enterprise-identity, labs.
  - Migration and seed commands. The quickstart must work in this shape:
    ```
    cp .env.example .env
    docker compose up --build -d
    docker compose exec app python -m app.seed --dataset demo
    ```
- **CI (GitHub Actions):**
  - Lint and format.
  - Type checks.
  - Tests with a Postgres service.
  - Migration validation (upgrade on an empty database).
  - Static analysis.
  - Dependency, secret, container, and infrastructure scanning.
  - Container build.
  - SBOM.
  - Playwright.
  - Artifact provenance and signing where supported.
- **CI rules:**
  - No paid AI key required.
  - Least-privilege tokens.
  - No secrets exposed to untrusted pull requests.
  - Report scanner failures and false positives; never disable a control to get a green build.
- **Deployment workflow:** a protected, manually triggered deploy with an environment approval gate and short-lived OIDC credentials. Not executed without authorization.
- **Environments:** separate local, staging, and production configurations. Production checks: no debug mode and no default credentials.
- **Infrastructure as code** for one AWS path:
  - Container service plus managed PostgreSQL in private subnets.
  - Networking, TLS guidance, secret references.
  - Least-privilege service roles.
  - Logging and monitoring.
  - Backup configuration.
  - Resource tagging.
  - Cleanup and teardown with cost controls.
  - Restricted ingress and egress.

  Validate it locally (`fmt`, `validate`, scan). **Do not apply.**
- **Shared responsibility:** document it for Supabase, Vercel, AWS, and model providers. Platform defaults are not assumed sufficient.
- **Rollback:**
  - Application rollback.
  - Migration compatibility (expand/contract).
  - API and schema compatibility with in-progress cases.
  - **Not all migrations are reversible.**
- **Backups:** backup and restore instructions.

### F.3 Rollout, drills, and recovery
- **Rollout stages:**
  1. Offline evaluation.
  2. Shadow recommendations without execution.
  3. Limited user pilot.
  4. Human-approved execution.
  5. Broader rollout after acceptance.

  Define stop and rollback criteria for each stage.
- **Local drills,** recording **actual** results in `docs/drills.md`:
  - Model/provider outage.
  - Customer API outage.
  - Worker crash.
  - Database backup and restore (measured).
  - Uncertain adjustment.
  - Incorrect recommendation.
  - Emergency execution shutdown.
- **Recovery rules:**
  - Restoring must not replay completed actions or reinstate revoked access.
  - Proposed RTO and RPO are stated separately from measured results.
- **Operational documents:**
  - Runbooks.
  - An incident response guide.
  - An **example incident report from an executed drill**.
  - An ownership and escalation matrix.

  Local drills are not proof of production availability.

---

## PART G: Protocol integration and interoperability lab

### G.1 Specification research first
Create:
- `docs/protocol-catalog.md`
- `docs/protocol-selection.md`
- `docs/protocol-compatibility.md`
- `docs/protocol-adoption-evidence.md`
- `docs/protocol-learning-labs.md`
- `docs/protocol-test-results.md`

For each protocol, from primary sources (specifications, maintainer repos, SDK docs, release and migration notices), record:
- Full name and identifier.
- Purpose and architectural layer.
- Official source.
- Governance body.
- Pinned specification version.
- SDK version and license.
- Status: stable, draft, experimental, or superseded.
- Transports.
- Authentication model.
- Limitations.
- Verification date.
- Adoption evidence.

Rules for reporting:
- Keep vendor support, announced partnerships, and documented production deployments separate.
- **Always spell out which "ACP" is meant.**
- Don't assume protocol support in Cursor, Codex, Claude Code, or any other client; verify the actual version.
- Don't claim exhaustive coverage or wide adoption without evidence.
- Pin compatible versions rather than incompatible drafts.
- **Never label ordinary REST endpoints protocol-compliant.**
- Don't force protocols into the core workflow.

**Supporting standards** (documented as supporting standards, not agent protocols):
- HTTPS/TLS.
- HTTP and JSON-RPC.
- OpenAPI and JSON Schema.
- SSE and WebSockets.
- OAuth and OIDC.
- JWT and JWKS.
- OpenTelemetry and trace context.
- Webhook signature verification.
- CloudEvents.
- DID and verifiable credentials (where an experimental protocol uses them).

Use each protocol's own authentication requirements; don't invent a universal scheme.

### G.2 Structure and isolation
Directories:
- `protocols/mcp/`
- `protocols/a2a/`
- `protocols/ag_ui/`
- `protocols/a2ui/`
- `protocols/mcp_apps/`
- `labs/agent_client_protocol/`
- `labs/legacy_acp/`
- `labs/anp/`
- `labs/commerce/ucp/`
- `labs/commerce/agentic_commerce/`
- `labs/payments/ap2/`
- `labs/payments/x402/`
- `labs/payments/mpp/`

Isolation rules:
- Domain services are shared: permissions, case access, eligibility, audit.
- No universal adapter that hides protocol differences.
- Each protocol has a feature flag and an independent startup command.
- **The core application stays usable with every lab disabled.**

**Harness integration:** every adapter preserves:
- Caller identity and authorization context.
- Case and run IDs.
- Deadlines, budgets, cancellation.
- Trace correlation.
- Audit records and checkpoints.
- Idempotency and reconciliation.

Adapter safety rules:
- Validate all inbound payloads.
- Protect discovery and callbacks against untrusted destinations, credential leakage, and SSRF.
- A session ID is not authentication.
- Remote agents and UI events never approve actions.

### G.3 MCP (core)
- **Server:** a specification-compatible MCP server built with the official SDK.
- **Read-only capabilities:** member, stay, ledger, policy retrieval, and case evidence.
- **Protocol handling:** initialization, capability negotiation, schemas, errors, and transports, with remote vs. local security made explicit.
- **Authentication and authorization:**
  - Auth follows the pinned version's guidance: issuer, audience, expiry, and scopes.
  - Reuse REST authorization.
  - **Never forward incoming tokens blindly.**
- **Excluded:** no SQL, filesystem, or adjustment execution.
- **Tests:** denied, expired, wrong-audience, insufficient-scope, and cross-record access.
- **Verification:** with an independent client or inspector, plus a local demo client with config examples that contain no secrets.
- **Documentation:** why MCP is optional and when REST suffices.

### G.4 A2A (core)
- **Agents:** two separately running services, a loyalty investigation coordinator and a reservation evidence specialist. The specialist returns a structured evidence artifact with provenance.
- **Protocol features:**
  - Agent Card discovery.
  - Task and message lifecycle.
  - Capabilities.
  - Peer authentication and per-task authorization.
  - Timeouts.
  - Cancellation.
  - Unavailable-peer handling.
  - Correlation to the case.
  - Protected artifacts, callbacks, and task state.
- **Trust:** Agent Cards describe capabilities and are not proof of trust.
- **Approvals:** adjustments stay under human approval.
- **Comparison:** with a simple REST adapter, including when each is sufficient.

### G.5 AG-UI (core)
- **Events:** use the pinned specification's events for run lifecycle, messages, tool activity, state changes, errors, and completion, between the runtime and the frontend. **Don't invent event names and call them standard.**
- **Connection handling:**
  - Reconnect through documented features or clearly labeled extensions.
  - Event deduplication.
  - Run-access authorization.
  - Inbound event validation.
  - Limited state exposure.
  - Reconnects never repeat actions.
- **Exposure:** no chain-of-thought, secrets, or unauthorized payloads. The frontend is never the source of truth for approval.

### G.6 A2UI (lab)
- **Scope:** one dynamic missing-information form or evidence checklist.
- **Rendering:** an allowlisted component catalog, with descriptions validated before rendering. **No model-generated JavaScript or HTML execution.**
- **Validation:** backend validation of submitted values.
- **Boundaries:** document the A2UI vs. AG-UI vs. application responsibilities. The static UI remains the fallback.

### G.7 MCP Apps (lab)
- **Viewer:** a read-only embedded case viewer showing summary, evidence references, citations, and status.
- **Isolation:** the supported resource, communication, sandbox, and CSP mechanisms.
- **Host verification:** verify in a compatible host. Otherwise mark it "host integration unverified." Not every MCP client supports it.

### G.8 Agent Client Protocol (development lab)
- **Pre-check:** verify current editor and agent support.
- **Exercise:** a small dev task through a compatible client-agent pair, covering session, task, progress, permission requests, cancellation, and result review.
- **Separation:** kept separate from the customer app. Don't replace a working editor setup to claim coverage. If support is missing, record the prerequisite.

### G.9 Historical and experimental labs
- **IBM/BeeAI Agent Communication Protocol (historical):**
  - Verify its relationship to A2A from maintainer sources.
  - Write a migration comparison: discovery, tasks, streaming, auth, errors.
  - Optionally, a translation exercise on recorded synthetic messages.
  - No production dependency on archived code. No general interoperability claims.
- **ANP (Agent Network Protocol, experimental):**
  - Official implementation, two local synthetic agents.
  - Only the identity, discovery, and communication mechanisms defined by the version.
  - Maintained crypto libraries. **No invented DID or encryption semantics.**
  - Test failed verification and untrusted peers.
  - Isolated from production identities and data.
  - Document limitations and adoption separately.

### G.10 Commerce module (separate from loyalty)
- **Merchant:** a fictional merchant selling synthetic hotel add-ons.
- **Adapters:** **Universal Commerce Protocol (UCP)** and the **Agentic Commerce Protocol**, as separate adapters over the same merchant domain.
- **Implementation:** official schemas and reference clients. Support only the capabilities the pinned versions define (discovery, catalog, checkout, order status, errors) and report partial support.
- **Rules:** the two protocols are not assumed to be wire-compatible. A loyalty adjustment is never treated as a payment.

### G.11 AP2 (Agent Payments Protocol) sandbox
- **Implementation:** the official specification and reference implementation. Verify mandate structures and signatures.
- **Tests:**
  - Identity and trust.
  - Merchant or recipient.
  - Amount and currency.
  - Expiry.
  - Purchase details.
  - Replay protection.
  - Altered transaction contents.
- **Application restrictions:** add them explicitly where the protocol doesn't provide them.
- **Data:** synthetic transactions and test credentials only.
- **Boundaries:** authorization evidence is distinct from payment execution and settlement. No custom crypto. A valid signature does not prove the purchase is legitimate.

### G.12 x402 and MPP (Machine Payments Protocol) sandboxes
- **Exercises:** separate paid-tool exercises, such as a fictional premium reference API, using official SDKs and references.
- **Flows:** payment-required, authorization, retry, and result.
- **Funds:** mocks, sandboxes, or testnets only. **No wallet funding and no real transfers.** Label simulated settlement prominently.
- **Tests:** duplicate, altered, failed-verification, and unknown-outcome requests.
- **Comparison:** compare purposes and assumptions without claiming the two are interchangeable.

### G.13 Protocol verification and Protocol Lab page
- **Tests per protocol:**
  - Schema validation.
  - Version compatibility.
  - Initialization and negotiation.
  - Authentication failures.
  - Insufficient permissions.
  - Malformed input.
  - Unsupported features.
  - Stream interruption.
  - Cancellation.
  - Duplicates.
  - Timeouts and unavailable peers.
  - Replay.
  - Expired credentials or mandates.
  - State recovery.
  - Cross-record access.
- **Verification tools:** official conformance tools where available, plus an independent peer. Matching client and server assumptions are not proof.
- **Reporting:** state the exact version, transport, capability subset, and peer.
- **Protocol Lab page** (developer-only): purpose, version, capabilities, scenarios, sanitized traces, test results, and limitations. No secrets.
- **Status groups:** core integrations, interface extensions, dev-tool exercises, experimental labs, historical exercises, and commerce/payment sandboxes.

---

## PART H: Actual-tool learning track

### H.1 Rules
- **Purpose:** produce real hands-on proficiency. A blocked exercise **stays visibly incomplete**; documentation is not use.
- **Attribution:**
  - Never claim a product was used because instructions were written.
  - **Never attribute Claude Code's work to another tool**, or another tool's work to Claude Code.
  - Avoid concurrent edits to the same files by different tools.
- **Core independence:** the core app stays runnable without any of these products. Don't replace the core architecture to include more products, and don't install every product from the source video.
- **Categories:** separate development tools, application infrastructure, model providers, collaboration tools, and personal productivity tools.
- **Accounts and plans:**
  - Verify current official product information before suggesting any plan or paid subscription.
  - Paying for a subscription doesn't establish permission to process company data.
  - Use synthetic project information only.
- **Data sharing:** no customer data on external boards or tools without approval.

Create:
- `docs/tool-access-matrix.md`
- `docs/tool-stack-coverage.md`
- `docs/tool-stack-labs.md`
- `docs/tool-stack-evidence.md`
- `docs/tool-experiment-results.md`
- `docs/fde-tool-map.md`

**Per tool, record:**
- Verified official identity and documentation.
- Purpose and whether it's necessary.
- Account, license, plan limits, and free-tier limits.
- OS requirements.
- Integration mechanism.
- Permissions and data sent.
- Estimated vs. verified charges.
- Setup steps.
- The assigned task and why it fits.
- The exercise and its acceptance criteria.
- Actual output and verification evidence.
- Setup, active, waiting, review, and correction time.
- Cost.
- Defects found and tests passed.
- Task order and prior familiarity.
- Whether I can explain the result.
- A follow-up task for me.
- Status: **exercised / configured but untested / documentation-only / blocked**.

**Time and benefit reporting:** report time to a *verified* result, not time to generated code. No claims of scientifically established speed-ups from single trials. State honestly whether each tool saved time, added overhead, or wasn't sufficiently tested.

### H.2 Tools and assigned exercises
- **Claude Code** (this build's primary implementer):
  - Requirement analysis, repo understanding, scripting, and features.
  - Record which work it did. It is distinct from the Claude API runtime.
- **Codex:**
  - A bounded, comparable exercise of my choosing: complex logic, tests, or debugging.
  - Record what was actually run.
- **Cursor:**
  - Prepare the repo with current rule mechanisms.
  - A personal exercise: inspect, make a bounded change, run tests, review the diff.
- **Shared repository guidance:**
  - `CLAUDE.md`, `AGENTS.md`, and Cursor rules all point to one shared architecture and coding standard, with no contradictions.
  - Development harness for sessions: inspect state → read status → pick the next requirement → run checks → bounded change → diff review → validate → record.
  - Comparable bounded tasks are used when comparing assistants.
- **CodeRabbit:**
  - Repo config using current official instructions, with the required permissions documented.
  - A small PR exercise only after authorized installation (never org-wide without authorization).
  - Record findings and fixes. Tests and human review remain independent.
- **Supabase:**
  - Managed Postgres and Auth profile, storage only if required, local CLI setup.
  - Test the actual access path. RLS caveat as in C.5.
  - Don't migrate the core just to claim coverage.
- **bolt.new:**
  - A detailed synthetic-data prototype brief, then actual generation when available.
  - Export through an authorized mechanism.
  - Review framework, dependencies, licensing, security, accessibility, and API fit.
- **Vercel:**
  - Verify compatibility with the bolt.new frontend, or a separate portfolio page.
  - Deploy only when authorized, and verify the endpoint and workflow before calling it deployed.
  - Document which components stay on the backend platform.
- **Monday.com:**
  - Backlog with milestones, requirements, acceptance criteria, dependencies, bugs, blockers, release readiness, and failures and improvements.
  - Provide an import file.
  - With authorized access, one narrow automation (for example, a status update on milestone completion).
  - No unsolicited messages or invites.
- **Miro:**
  - Workshop package: current and proposed workflow, architecture and integration diagram, trust boundaries, agent loop, open decisions, facilitation guide.
  - Importable assets. Create the actual board only with access.
- **Egolite:**
  - Verify the exact product, official site, OS, and integration first. If unverifiable, mark it **blocked**.
  - Exercise: research on public info or a local synthetic site into a research summary.
  - No customer browser sessions. No invented APIs or repeated unverified claims (speed, privacy, token savings).
  - No undisclosed substitution.
- **Mira:**
  - Verify the exact Telegram assistant from the source video. Don't treat a same-named product as equivalent.
  - If it's custom or unavailable, say so and **ask me** whether I want a separate generic Telegram assistant exercise. Never build a replacement and call it Mira.
  - Limits: synthetic updates only, no customer data, no deployment or adjustment authority, no messages sent without authorization.
- **Kimi, GLM, Qwen:**
  - Verify specific releases, licenses (don't call a family "open source" without checking the release), interfaces, tool-calling support, and hosting or hardware requirements.
  - With access, add **one** provider first behind the provider interface. Explicit selection only; never silently move data.
  - Run the same held-out evaluation. Compare correctness, tool-call behavior, latency, and measured cost, plus local hardware needs if self-hosted.
  - A bounded exercise per accessible family.
- **Invoco:**
  - Verify the exact product and OS.
  - Exercise: optional developer dictation of a synthetic requirement; compare with the intended text and correct errors.
  - Never a runtime dependency. Don't claim installation if unsupported.

### H.3 FDE tool map (`docs/fde-tool-map.md`)
**Per capability:**
- Tool exercised.
- Purpose and why selected.
- Required permissions.
- Data handled.
- Setup.
- Verification evidence.
- Replacement criteria (when a different customer requirement would justify replacing it).

**Capabilities to cover:**
- Discovery and collaboration.
- Coding assistance.
- Version control and review.
- API integration.
- MCP.
- Identity.
- Database and retrieval.
- AI runtime.
- Evaluation.
- Browser testing.
- CI/CD.
- Infrastructure.
- Observability.
- Incident response.
- Project tracking and handover.

Unavailable commercial tools are labeled **"not exercised / documentation-only."**

---

## PART I: UAT, adoption, and handover

**Create:**
- Agent and supervisor UAT scripts.
- A user training guide.
- An administrator guide.
- A pilot feedback form.
- An acceptance checklist.
- An open-issue register.
- A support handover checklist.
- An ownership and escalation matrix.
- A release checklist.
- A scope-change procedure.
- Estimates with assumptions.

**Measure** manual vs. assisted completion on the same representative cases:
- Handling time.
- Task completion.
- Acceptance and override rates with reasons.
- Escalations.
- Rework.

**Rules:**
- Label simulated users and results.
- No fabricated sign-off, adoption, satisfaction, or ROI.

**Real-customer validation plan:**
1. Authorized data preparation.
2. Representative labels.
3. Measure the actual baseline.
4. Shadow mode.
5. Review disagreements.
6. Supervised pilot.
7. Measure quality, time, cost, and satisfaction.
8. Expand only on agreed criteria, with stop and rollback criteria.

---

## PART J: Reusable FDE foundation and playbooks

- **Extraction** (only after the app works; no overengineering):
  - Model provider interface.
  - Integration adapter patterns.
  - Identity and authorization helpers.
  - Durable jobs and checkpoints.
  - Audit utilities.
  - Evaluation and benchmark runner.
  - Observability configuration.
  - Deployment templates.
  - Discovery and handover templates.

  These go in `starter_kit/`. Loyalty schemas, policies, and rules stay out.
- **Scaffold command:**
  - Creates a new directory and copies only generic templates.
  - Generates example configuration and includes synthetic sample data.
  - Never copies secrets, customer records, or proprietary material.
  - **The generated project must start and pass a smoke test.** Record the result.
  - Don't call it a universal generator.
- **Adaptation proof:** adapt the starter kit to a small second domain as an exercise.
- **`docs/new-customer-playbook.md`:**
  - Requirement discovery.
  - Environment approval.
  - Adapter implementation.
  - Domain modeling.
  - Evaluation dataset creation.
  - First vertical slice.
  - Pilot acceptance.
  - Production readiness.
  - Handover.
- **`docs/new-requirement-playbook.md`** walks through 12 steps:
  1. Clarify the user and outcome.
  2. Define success and exclusions.
  3. Identify approved tools and data boundaries.
  4. Inspect APIs and data quality.
  5. Decide what stays deterministic.
  6. Choose the smallest viable AI workflow.
  7. Build a synthetic demo.
  8. Review with the customer.
  9. Implement authorized adapters.
  10. Create representative evaluations.
  11. Pilot and observe.
  12. Release and hand over.

  It includes templates for clarifying questions, acceptance criteria, dependency tracking, estimates with assumptions, demo feedback, technical decisions, and release readiness.
- **Explicit statements in both playbooks:**
  - Reusable infrastructure doesn't eliminate customer-specific discovery, validation, or approval.
  - A prototype timeline is not a production timeline.
  - This project does not guarantee handling every future requirement "in minutes."
- **Redesign guidance:** document which parts need redesign for a different domain.

---

## PART K: Personal proficiency (tracked separately from assistant-built work)

### K.1 Milestone teaching
At each milestone, explain:
- What changed.
- Why that design was chosen.
- How to verify it.
- Common failure modes.
- One exercise for me.

Then ask me to explain the result or make a small modification.

### K.2 Exercises I must complete
**Product and operations:**
- Change a policy.
- Replace or add an API adapter.
- Diagnose a failed job.
- Change a loop stop condition safely.
- Add a new domain-specific tool, with authorization and schema validation.
- Diagnose a context or retrieval failure.
- Resume an interrupted run.
- Reproduce and interpret an evaluation failure.
- Compare two model configurations.
- Revoke access.
- Rotate a test secret.
- Restore a backup.
- Disable external AI while keeping manual operation.

**Explanation and judgment:**
- Explain the difference between a loop and a harness.
- Explain why a simpler workflow may be preferable.
- Explain an architectural tradeoff.
- Explain a protocol choice.
- Demonstrate approval and execution separation.
- Demonstrate the customer workflow.
- Estimate an unfamiliar requirement.
- Adapt the starter kit to a small second domain.

**Security:**
- Explain the trust-boundary diagram.
- Identify which service receives sensitive data.
- Demonstrate denied access.
- Trigger and investigate an alert.
- Show that prompt injection cannot bypass backend approval.
- Recover an uncertain operation.
- Explain one residual risk and its owner.

**Protocols** (for each protocol):
- Run a successful interaction.
- Trigger one failure.
- Explain its purpose.
- Explain whether an ordinary API would suffice.

### K.3 Final practical assessment
I must:
1. Implement a changed requirement.
2. Diagnose a deliberately introduced failure.
3. Explain an evaluation result.
4. Demonstrate the application.
5. Select an appropriate tool and justify the choice.

Generated code is never counted as my demonstrated understanding. Don't claim I'm ready for every AI role or customer requirement.

---

## PART L: Portfolio package for vamsialla.com

### L.1 Files in `portfolio/`
- `project-summary.md`: title, short description, two-minute overview.
- `case-study.md`, titled **"Modernizing a Loyalty Support Workflow: Measuring Legacy, Automation, and AI-Assisted Performance."**
- `demo-script.md` (five minutes).
- `technical-walkthrough.md` (fifteen minutes).
- `interview-talking-points.md`, plus interview Q&A grounded in actual files and results.
- `evaluation-report.md` and a portfolio-safe security summary.
- `tool-and-protocol-evidence.md`: tools actually used vs. configurations prepared vs. simulated services vs. unverified integrations vs. remaining manual steps.
- `cost-and-time-observations.md`.
- `starter-kit.md`: a concise explanation of the reusable kit.
- Architecture and trust-boundary diagrams.
- `project-metadata.json`: framework-neutral; links are `null` unless real.
- `screenshots/`: **real captures from the running app**, via Playwright.

### L.2 Case study content
The case study leads with the business problem, the working outcome, my engineering decisions, verified results, what failed and how it was corrected, and remaining limitations.

It must also explain:
- Assumptions.
- Users.
- The synthetic legacy environment.
- What was measured.
- Root causes.
- Why each intervention was chosen.
- Access boundaries.
- Technology decisions.
- What AI does and does not control.
- Integration failures and recovery.
- Evaluation methodology and actual results.
- **Cases where AI didn't help.**
- Security and human oversight.
- Deployment approach.
- Tradeoffs.
- Reuse for the second customer.
- The starter kit.
- What still needs real-customer validation.
- Future improvements.

### L.3 Demo content
**Five-minute demo**, covering at least:
1. Successful resolution.
2. Duplicate-credit prevention.
3. Missing evidence and escalation.
4. Timeout and reconciliation.
5. Approval enforcement (self-approval blocked).
6. Evaluation and benchmark findings, plus operational metrics.

**Technical walkthrough** additionally shows:
- The second customer configuration.
- Starter kit generation.
- A selected protocol lab.

Keep the main demo simple; advanced labs stay separate.

### L.4 Honesty and website
- Label everything as an **independent portfolio simulation with synthetic data**.
- No invented clients, testimonials, savings, adoption, production experience, GitHub URLs, or demo URLs.
- **Website:** if the vamsialla.com repository is available, inspect its conventions and existing project pages, and prepare a compatible project #9 page or card. **Do not publish without authorization.**

---

## PART M: Repository and developer experience

### M.1 Directories
- `app/`
- `worker/`
- `mock_customer_api/`
- `migrations/`
- `policies/`
- `seed_data/`
- `config/customers/`
- `tests/`
- `evaluations/`
- `benchmarks/`
- `protocols/`
- `labs/`
- `infrastructure/`
- `starter_kit/`
- `security/`
- `docs/`
- `portfolio/`
- `frontend/` (React)

### M.2 Required files and guidance
- README.
- Dependency lock.
- `.env.example`.
- Setup for Windows PowerShell and macOS/Linux.
- Commands for setup, migrate, seed, reset (including demo reset), test, evaluation, benchmark, preflight, and cleanup.
- Troubleshooting.
- Hardware and resource guidance.
- License (MIT) and third-party notices.
- An explicit known-limitations list.

### M.3 Usability checks
- A new developer can start the offline demo with a short documented sequence.
- **Verify a clean install from a fresh clone**, not only the configured environment.
- Have another person follow the docs if one is available. Otherwise record that independent usability testing is pending.

---

## PART N: Milestones and final report

### N.1 Order
Run the relevant checks and update the requirements matrix after each milestone.

1. Workspace, repo, and access audit; tool access matrix; tracking files; requirements matrix.
2. Discovery package, architecture, baseline measurement plan, threat model draft.
3. Synthetic data generator, independent labels, and dataset splits.
4. Mock customer APIs, persistent data, migrations, and contract tests.
5. Credible legacy workflow (arm A), runnable end to end.
6. Deterministic eligibility, policy retrieval, state machine, approvals, execution, reconciliation, durable worker.
7. Improved conventional workflow (arm B) and complete server-rendered UI vertical slice.
8. AI-assisted arm C: provider interface, mock and Claude providers, context builder, bounded loop, harness, validation.
9. Security and identity: local auth, OIDC profile, authorization, CSRF, rate limits, redaction, red-team suite.
10. Benchmark runner, thresholds, A/B/C comparison, error analysis, business-value report.
11. MCP, then A2A, then AG-UI.
12. Performance and load tests, observability, CI/CD, Docker hardening, IaC (validate only), rollback.
13. Operational drills, recovery, incident exercises.
14. Second customer configuration.
15. Actual-tool exercises, including bolt.new/React frontend and Supabase profile, as access allows.
16. Optional protocol labs: A2UI, MCP Apps, Agent Client Protocol, historical ACP, ANP, commerce, payments.
17. Reusable starter kit extraction and smoke test; playbooks.
18. UAT, training, handover, and my personal exercises.
19. Portfolio package, real screenshots, website page preparation.
20. Final clean-install verification.

Additional order rules:
- Do not stop after the vertical slice and call the expanded scope complete.
- Do not spend time on optional styling, tooling, or labs while critical correctness is broken.
- Continue independent milestones while access-dependent ones are blocked.

### N.2 Final acceptance report
Classify every item as Implemented and verified, Implemented but unverified, Simulated, Documentation-only, Manual step required, or Blocked. The report covers:
1. Features implemented and what works.
2. Startup instructions.
3. Demonstration accounts and login instructions.
4. Exact checks executed and their results.
5. Evaluation and benchmark results (A vs. B vs. C), with limitations.
6. Mock vs. live status.
7. Actual tools exercised, with evidence.
8. Protocol compatibility evidence.
9. Security findings and residual risks.
10. Deployment status.
11. Operational drill and recovery results.
12. Starter kit generation and smoke-test results.
13. Business-value measurements.
14. Time and cost observations.
15. My personal exercises completed.
16. Requirements matrix location.
17. Portfolio file locations.
18. Incomplete items with precise blockers and next steps.
19. Recommended next learning exercises based on demonstrated weaknesses.

**Do not say "everything is complete" unless the requirements matrix supports it. Never equate generated code with verified functionality, or an undeployed application with a deployed one.**

**Begin now:**
1. Inspect the workspace.
2. Complete the Part 0.7 continuity review (`docs/continuity.md`).
3. Create the tracking files, requirements matrix (tagged by tier), backlog, and tool access matrix.
4. Commit the Appendix F defect catalog and hypotheses.
5. Implement Milestones 1–5 toward the first verified end-to-end workflow.

---

## APPENDIX: Source-prompt coverage checklist

Your source file contained these prompts. Exact duplicates were merged into one section each.

| Source prompt | Covered in |
|---|---|
| 1. "AI Loyalty Support Resolution Assistant" (FDE lifecycle, 12 seeded failures, tools incl. draft_resolution, state machine, 40 evals, portfolio files) | 0.2, A, B.3, B.9, B.10, B.11, D, E, F, L (40→60 per 0.6; draft_resolution → validated service per B.9) |
| 2. "Resolution Platform" (stakeholders, access docs, MCP, two customers, rules baseline, rollout, tool map, 60 evals, 15-min walkthrough) | A, B.2, B.4, C.3, G.3, E, F.3, H.3, L |
| 3. "Platform + starter kit" (three profiles, preflight, data governance, retention jobs, starter kit, new-customer playbook, practice exercises) — appeared twice | B.2, C.3, J, K |
| 4. "Mission & expectations" (four access capabilities, new-requirement playbook, synthetic data rules) + tool-stack practice add-on | 0.2, 0.3, B.2, B.5, J, H |
| 5. Quickstart snippet (git clone / compose / seed) | F.2 |
| 6. "Actual products" prompt (Supabase/bolt/Vercel/React stack, tool-access matrix, benefit measurement) — appeared twice | 0.6, H, B.2 |
| 7. Mandatory personal proficiency + engineering quality loop + practical assessment | 0.5, E.6, K |
| 8. Agent loops, harnesses, AI engineering matrix, dev harness, 10 required demos | B.9, D, E.8, H.2 |
| 9. Protocol interoperability lab (MCP, A2A, AG-UI, A2UI, MCP Apps, Agent Client Protocol, IBM ACP, ANP, UCP, Agentic Commerce, AP2, x402, MPP, supporting standards) — first copy was truncated | G |
| 10. Enterprise AI security engineering (NIST/OWASP, governance, red team, incidents, release gates, maintenance) | A.4, C |
| 11. Consolidated "Modernization" prompt (28 sections) | All parts |
| 12. Legacy baseline and business-value validation | B.8, E.1, E.2, E.7, B.13 dashboard, I |
| 13. Legacy-to-AI benchmarking and release gates | E.3–E.6 |
| 14. Final "AI Loyalty Support Modernization Platform" (30 sections) | All parts; its sequence is merged into N.1 |
| 16. Enterprise AI practice gap review (added after review) | Appendix E |
| 17. Legacy problem design, synthetic operating history, KPI tree, pre-registered hypotheses, member journey, end-to-end ledger proof | Appendix F |
| 21. Keys, tokens, and account setup without secrets in the prompt | Appendix K and `.env.example` |
| 22. Live public demo link, GenAI telemetry conventions, AI observability tooling decision | Appendix L |
| 19. Portfolio continuity with stages 0–8, reuse of existing repos, scope tiers, backlog, Stage 10 boundary, coverage map | Part 0.7 |
| 20. Document/vision extraction, classical ML baseline, domain-agnostic method and second mini-domain | Appendices H, I, J |
| 18. Source video transcript and tool roles (Claude Code with MCPs, Egolite, Mira, Codex, Cursor, CodeRabbit, Supabase incl. vector and edge functions, Vercel + bolt.new, Monday.com agents, Miro, Kimi/GLM/Qwen routing, Invoco, minimal-stack principle) | Appendix G |
| 15. Earlier SPEC.md and CLAUDE-CODE-PROMPTS.md (from this conversation) | Appendices B, C, D. The SPEC.md "out of scope" list is **intentionally not applied**; everything stays in scope, in the order given by N.1. |

---

## APPENDIX B: Concrete implementation defaults

Use these unless official documentation or a recorded decision justifies a change.

- **Tooling:**
  - `uv` for dependency management and the lockfile.
  - `ruff` for lint and format, `mypy` for type checks.
  - `gitleaks` for secret scanning, `pip-audit` for dependency audit.
  - `syft` for the SBOM, Trivy (or equivalent) for container and IaC scanning.
  - Terraform for IaC.
- **App structure:** `app/domain/`, `app/services/`, `app/adapters/`, `app/ai/` (prompts in `app/ai/prompts/`, versioned), `app/web/` (Jinja/HTMX), `app/api/`.
- **Job queue:** Postgres `SELECT … FOR UPDATE SKIP LOCKED`, lease expiry timestamps, heartbeat updates, and a unique active-job key per (case, job type).
- **Approval binding:** store a hash over (member, stay, points, policy version, evidence snapshot hash, approver, expiry). Execution recomputes it; any mismatch invalidates the approval. An optional audit hash chain may be added, and its guarantee must be stated honestly.
- **Idempotency key:** derived deterministically from the approval ID, so retries and concurrent executes reuse the same key.
- **Policies:** 2–3 fictional Markdown policy documents per customer, each with at least 2 versions. Front-matter fields: `policy_id`, `version`, `effective_from`, `effective_to`, `status`, plus section IDs. Chunks are stored with a `tsvector`.
- **Time:** store UTC and display in the hotel's time zone. Waiting-period tests cover the exact boundary day and time-zone edges.
- **Second customer:** Cedarpoint Inns has a different field mapping, waiting period, and eligible channels. A proposed adjustment above its supervisor approval limit must escalate. It runs as a separate Compose project with its own database.
- **Arm A in benchmarks:** evaluated by a scripted agent that follows the legacy search and checklist steps, labeled "scripted, not human timing."
- **Evaluation commands:**
  - `python -m evaluations.run --arm {a,b,c} --split {dev,validation,heldout,stress} --provider {mock,live} --budget-usd N`
  - `python -m evaluations.compare RUN_A RUN_B`
- **Live evaluation:** only with a key set in `.env` by me and an explicit budget (suggest $5 for the first run). Repeat 10 selected cases 3× to show variability.
- **Metrics:** a `/metrics` page plus a JSON endpoint.
- **Public demo:** reset only through a scheduled or admin-controlled job, never a public button.
- **MCP:** official Python MCP SDK, streamable HTTP transport, read-only tools such as `get_case_evidence` and `search_policy`. Verify with MCP Inspector if available.
- **AWS reference path:** ECS Fargate (app, worker, mock API) + RDS PostgreSQL in private subnets + ALB with ACM TLS + Secrets Manager + least-privilege task roles + CloudWatch + automated RDS backups + tags + a teardown doc with cost warnings. Run `terraform fmt`/`validate` only.
- **Prerequisites to document:** Docker Desktop, Python 3.12, uv, Git, Node.js (for Playwright and the React frontend). The Anthropic API key is optional.
- **Commands:** make targets `up`, `migrate`, `seed`, `reset-demo`, `test`, `eval`, `benchmark`, `preflight`, `down`, `clean`, each with a `scripts/*.ps1` equivalent.

## APPENDIX C: "Done when" criteria per milestone

Do not start a milestone while the previous milestone's checks fail.

| Milestone (N.1) | Done when |
|---|---|
| 1–2 | Tracking files, requirements matrix with IDs, tool access matrix, and discovery and architecture docs exist and are linked |
| 3–4 | `docker compose up`, migrate, and seed succeed from scratch; data generator is reproducible (same seed → same checksum); mock API contract tests pass |
| 5 | Legacy arm A completes a case end to end in the browser |
| 6 | Real-Postgres tests pass for idempotency atomicity, concurrent execute, duplicate prevention, timeout-after-commit reconciliation, lease recovery, approval invalidation |
| 7 | Arm B works; Playwright happy path (create → investigate → approve by another supervisor → execute → resolved) and self-approval block pass |
| 8 | Every loop stop condition and injection test passes on the mock provider; the Claude provider is implemented and its live smoke test is run or marked NOT RUN |
| 9 | Authorization, CSRF, rate-limit, redaction, and red-team tests pass; OIDC profile login works locally |
| 10 | Thresholds file committed before runs; A/B/C reports generated from actual runs; error analysis written |
| 11 | MCP, A2A, and AG-UI tests pass against an independent client or peer where available |
| 12 | Local CI equivalent passes; load test report saved; Terraform validates |
| 13 | Drills recorded with actual results, including a measured restore time |
| 14 | Second-customer tests show different, correct outcomes from the same code |
| 15–16 | Each tool and lab has evidence or a precise Blocked status |
| 17 | Generated starter-kit project starts and passes its smoke test |
| 18–19 | UAT scripts, handover, and portfolio files exist; screenshots are real Playwright captures |
| 20 | Fresh clone → README quickstart → all offline tests pass |

## APPENDIX D: Claude Code session kit

### D.1 One-time setup (I do this)
```bash
mkdir loyalty-support-modernization && cd loyalty-support-modernization
git init && mkdir docs
# save this file as docs/MASTER-SPEC.md and the CLAUDE.md below at the repo root
git add . && git commit -m "Add master spec"
claude
```

### D.2 CLAUDE.md (create at repo root in Milestone 1 if it doesn't exist)
```markdown
# Project: AI Loyalty Support Modernization Platform (portfolio simulation)

Source of truth: docs/MASTER-SPEC.md. Read the relevant Part before changing code.

## Every session
1. Read docs/implementation-status.md and docs/session-handoff.md.
2. Run `make test` (or scripts/test.ps1) to see the current state before editing.
3. Work only on the milestone or task named in the prompt.
4. After changes: run the relevant tests, review `git diff`, update requirements-matrix,
   implementation-status, verification-log, session-handoff.
5. Commit with a descriptive message when checks pass. Never push without my OK.

## Rules
- Part 0 rules are non-negotiable: no fabricated results, URLs, users, approvals, savings, or tool usage.
- Never weaken or delete a failing test to get green.
- Eligibility, authorization, approval, amounts, execution: deterministic Python only.
- Domain code never imports FastAPI, SQLAlchemy sessions, httpx, or model SDKs.
- Verify library, SDK and protocol APIs in official docs; pin versions with uv.
- No paid resources, terraform apply, publishing, installs of GitHub apps, or messages without my explicit OK.
- Record which tool did each piece of work.
- Ask me only when blocked by a missing decision or authorization; batch questions.
```
Also create `AGENTS.md` and Cursor rules that point to the same standard (H.2).

### D.3 Prompts
**Kickoff:**
```
Read docs/MASTER-SPEC.md completely and follow it. Begin with Part 0 and Milestone 1.
```

**Each milestone:**
```
Continue with Milestone <N> from docs/MASTER-SPEC.md Part N.1 (relevant Parts: <x, y>).
First run the existing test suite and report its state; fix earlier failures first.
Implement the milestone, run its Appendix C "done when" checks, and report: what changed,
exact commands and results, what is unverified or blocked, and the next step. Include the
teaching notes from Part K.1 and one exercise for me. Update tracking files and commit.
```

**Resume after a break or `/clear`:**
```
Read CLAUDE.md, docs/MASTER-SPEC.md, docs/session-handoff.md and docs/implementation-status.md.
Run the full test suite, summarize where we are in 5 lines, then continue with the next
incomplete milestone. Don't redo completed work.
```

**Live Claude evaluation** (after I put a key in `.env`):
```
I have set ANTHROPIC_API_KEY in .env. Run arm C on the heldout split with --budget-usd 5,
repeat 10 selected cases 3 times, and update the evaluation and business-value reports with
the actual numbers. Keep mock and live results in separate sections.
```

**Tool exercise:**
```
Run the Part H exercise for <tool>. First verify its official identity and current setup
docs, then tell me what accounts or access you need from me (batched). If unavailable,
record exact manual steps and mark it Blocked. Record times, cost, evidence and attribution.
```

**Website page:**
```
The website repo is at <path>. Inspect how the existing 8 project pages/cards are built.
Prepare project #9 from portfolio/project-metadata.json and the case study, following those
conventions exactly. Real screenshots only; leave repo and demo links empty unless I give
real URLs. Don't deploy or push.
```

**Final verification:**
```
Do a clean-install check: clone this repo into a temp directory, follow only the README
quickstart, run all tests, the offline evaluation, Playwright, and the starter-kit smoke test,
and regenerate screenshots. Then produce the Part N.2 final report with every item classified.
```

### D.4 Working tips
- Use **plan mode** (Shift+Tab) at the start of Milestones 6, 8, 10 and 11, and approve the plan before code is written.
- Run **`/clear`** between milestones; the handoff file carries the state.
- After each milestone, read the diff and run the demo yourself. Your interview answers depend on understanding why the approval hash, reconciliation, and loop stop conditions exist.
- Expect many sessions over several weeks. Milestones 6, 8, 10 and 11 take the longest.

---

## APPENDIX E: Enterprise AI practices (additional mandatory requirements)

These fill gaps commonly expected in enterprise AI delivery. Apply the Part 0 honesty rules: assess and document, implement where feasible, and **never claim regulatory compliance**. Add each item to the requirements matrix.

### E1. Responsible AI and governance
- **AI system card** (`docs/ai-system-card.md`):
  - Intended use and prohibited uses.
  - Users and affected people (members who never see the system).
  - Model and provider, data used.
  - Known failure modes, evaluation summary, human oversight design.
  - Limitations and contact owner.
- **AI use-case register entry and impact assessment:**
  - Risk tier, potential harms (wrong denial of earned points, unequal treatment), mitigations, residual risk owner.
  - Mark the assessment "draft, not reviewed by a governance board."
- **Regulatory applicability assessment** (`docs/regulatory-assessment.md`), as documentation only and not legal advice:
  - Which obligations *might* apply to a real deployment: EU AI Act risk classification, GDPR/UK GDPR, CCPA/CPRA, consumer-protection rules for loyalty programs.
  - Record what a real customer's legal and privacy team must decide.
- **Fairness and consistency evaluation:**
  - Add benchmark slices by member tier, home country/region, booking channel, request language, and request writing style (terse, verbose, non-native).
  - Report whether outcomes or escalation rates differ across slices for equivalent facts.
  - Use counterfactual pairs: identical facts with only the name, language, or tier changed must produce the same deterministic outcome and an equivalent explanation.
- **Transparency in the UI:**
  - Label AI-generated text as AI-generated.
  - Show which content is deterministic (eligibility, points) and which is model-written (summary, explanation).

### E2. Human factors and automation bias
- Design to prevent rubber-stamping:
  - Supervisors see the evidence and the deterministic result before the AI summary.
  - Approval requires reviewing the cited evidence.
  - A rejection or override requires a reason.
- Measure automation bias in UAT and evaluation by seeding a small number of deliberately wrong AI recommendations. Track how often reviewers approve them. Report this honestly.
- Track reviewer workload and time per review, and the override rate per reviewer and per scenario.

### E3. Data protection operations
- **Data subject requests:** implement and test a synthetic "access my data" export and an "erase my data" workflow covering cases, evidence, derived summaries, caches, evaluation copies, and logs. Document which records must be retained (audit, financial adjustments) and why. Document backup limitations.
- **Legal hold:** a flag that suspends retention deletion for specific cases, with audit.
- **Data residency and transfer:** document where each data category is stored and processed (database region, model provider region, telemetry destination). Make the provider region configurable in the approved-deployment profile.
- **PII handling:** detect and redact unnecessary PII (payment card numbers, passport numbers, phone numbers, emails) in free-text requests before model calls and in logs. Test with synthetic examples. Document the limits of pattern-based detection.

### E4. Enterprise model access patterns
- **Enterprise model endpoint adapter:** add an option for the provider interface to use Claude via an enterprise cloud endpoint (for example, Amazon Bedrock in the AWS path). Verify the current model availability, regions, and SDK in official docs. Configure only; mark it Blocked without access. Document why enterprises choose this: existing cloud agreements, IAM, VPC endpoints, regional processing, consolidated billing.
- **Provider contract checklist** (documentation, verified from official sources where possible, otherwise "to be confirmed by vendor management"):
  - Data retention and zero-retention options.
  - Training-use terms.
  - Data processing agreement.
  - Regional processing.
  - Rate limits and quotas.
  - SLA.
  - Model deprecation policy.
  - IP terms.
- **Model lifecycle:**
  - Pin exact model IDs.
  - Track provider deprecation dates.
  - A documented model-upgrade procedure: regression benchmark on the held-out set, shadow comparison, then staged switch, with the known-good config kept for rollback.
  - A test proving an unknown or retired model ID fails safely to manual mode rather than to another provider.
- **AI gateway pattern (documented, optional implementation):** a single internal egress point for model calls with key management, per-team quotas, logging, redaction, and routing. Explain when an enterprise needs one versus this app's in-process provider adapter.
- **Cost controls:**
  - Use prompt caching where the provider supports it, and measure the effect.
  - Choose a smaller or cheaper model for simple steps only if the benchmark shows no quality loss.
  - Per-team and per-case cost attribution (chargeback/showback tags).

### E5. Production AI quality monitoring
- **Online quality sampling:** a configurable percentage of completed cases is queued for human QA review against the rubric. Record the results separately from offline evaluation.
- **Drift signals:** track changes over time in escalation rate, override rate, validation-failure rate, citation-failure rate, tool-error rate, token usage per case, and request-category mix. Alert on configurable thresholds.
- **AI incident register:** a separate category for AI-specific incidents (wrong recommendation approved, citation to a wrong policy, injection attempt observed), with severity and corrective action.
- **Feedback-to-dataset pipeline:** reviewed production disagreements (synthetic in this project) can be promoted into the regression dataset only after labeling review. Never automatically.
- **Canary for prompt and model versions:** route a configurable share of investigations to a candidate prompt or model in shadow or canary mode. Compare against the current version before promotion.

### E6. Enterprise identity and access lifecycle
- **Delegated authority:** the AI investigation runs with the requesting user's permissions (on-behalf-of), never with a broad service-account scope. Tests prove the agent cannot read records the user cannot read.
- **User provisioning:** document SCIM-based provisioning and deprovisioning with an enterprise IdP. If the local OIDC provider supports it, demonstrate that deprovisioning revokes access.
- **Group-to-role mapping** from IdP claims, configurable per customer.
- **Break-glass access:** a documented emergency admin procedure with time limits, mandatory reason, alerting, and audit review. No standing shared admin account.
- **Periodic access review report:** an export of users, roles, and last activity for reviewers.

### E7. Enterprise integration realism
- **Systems of record:** document how adapters would map to typical enterprise systems: CRM/case management (for example Salesforce Service Cloud, ServiceNow, Zendesk), loyalty platform, property management or reservation system, and data warehouse. Documentation-only unless authorized sandbox access exists; never claim integration.
- **Embedding the assistant in the agent's existing tool:** document the option of surfacing recommendations inside the CRM agent workspace rather than a separate console, and the tradeoffs.
- **Event-driven option:** document webhook or change-data-capture triggers (case created → investigation queued) versus polling. Implement a signed-webhook intake on the mock API if time allows.
- **SIEM and audit export:** export security and audit events in a structured format suitable for a SIEM. Document the field mapping.
- **Analytics export:** a privacy-filtered daily export of operational metrics for a BI tool or warehouse, with no free text and no PII.

### E8. Operating model and change management
- **Change approval:** prompt, policy, model, and tool changes go through a recorded change request linking evaluation evidence, a reviewer, and a rollback plan. A template is enough; a simulated approver must be labeled simulated.
- **RACI for AI operations:** who owns prompt changes, evaluation datasets, model upgrades, QA sampling, AI incidents, and cost budgets after handover.
- **Support tiers:** L1 (support supervisors), L2 (application team), L3 (FDE/engineering, provider), with escalation paths and response targets labeled "proposed."
- **Business continuity:** document behavior during an extended provider outage (manual arm B mode), plus a multi-region and DR approach for the approved deployment. Documentation-only and clearly unverified.
- **Communication plan:** how agents and supervisors are told about AI changes, known limitations, and how to report bad recommendations.

### E9. Additional evaluation and benchmark slices
- Multilingual and non-native-English requests (synthetic). Report the quality per language, or document the product as English-only with escalation for others.
- Long, messy, multi-issue requests, and requests mixing a missing-points claim with an out-of-scope ask (refund, complaint). The correct behavior is to handle the in-scope part and route the rest.
- Adversarial cost tests ("denial of wallet"): requests designed to trigger maximum tool calls or tokens. Budget stops must hold.
- Consistency: identical case submitted twice produces the same deterministic outcome, and the explanation does not contradict it.

### E10. Portfolio additions
- Add the AI system card, fairness slice results, automation-bias findings, and the model-upgrade procedure to the portfolio evidence. These are strong enterprise interview topics.
- Add interview talking points on: why eligibility is not delegated to the model, how on-behalf-of authorization limits agent access, how the model-upgrade regression process works, and what the fairness and automation-bias results showed (including unfavorable results).

**Milestone placement:**
- E1 card, E2 UI design, E3 PII redaction, and E6 delegated authority are built with Milestones 8–9.
- E1 fairness slices, E2 bias measurement, and E9 go into Milestone 10.
- E4, E5, E7 and E8 go into Milestones 12–13 and 18.
- E10 goes into Milestone 19.

---

## APPENDIX F: Legacy problem design and end-to-end business-case proof (mandatory)

### F1. Purpose and honesty boundary
In a real engagement, legacy problems are discovered from customer data. Here there is no real customer, so the synthetic legacy environment is **deliberately modeled on common, realistic failure patterns** in loyalty support operations. This is legitimate only if all of the following hold:
1. The defect catalog (F3) and hypotheses (F5) are written and **committed before arms B and C are built or benchmarked** (pre-registration). Git history is the evidence.
2. The defects are realistic operational problems, not sabotage. No broken authentication, no random wrong rules, no deliberately slow code.
3. The catalog includes defects that only non-AI fixes solve, defects AI may help with, defects **no arm can fix**, and cases where legacy is already correct.
4. Every simulated system, history, dissatisfaction signal, and result is labeled **SYNTHETIC**.
5. The conclusion follows the measurements, even if AI does not win. "We measured and chose the cheaper non-AI fix" is a valid and strong FDE outcome.

**Wording rules for the portfolio:**
- **Permitted:** *"In a synthetic environment modeled on common loyalty-support failure patterns, the legacy workflow reached the correct final outcome in N of M held-out cases; the improved conventional workflow reached X; the AI-assisted workflow reached Y, with Z false approvals."*
- **Forbidden:** "customers were dissatisfied," "saved $X," "improved CSAT," or any claim implying real users or a real business.

### F2. Synthetic legacy operating history (the FDE's day-one data)
Generate a configurable period (default 12 months) of synthetic historical operations for the legacy system, using a fixed seed and documented, configurable parameters:
- Case volume per week, with seasonality (holiday peaks).
- Handling-time distributions per scenario type (assumed parameters).
- **Outcomes:**
  - Correct.
  - False denial (under-credit).
  - False approval (over-credit or points liability leakage).
  - Duplicate credit.
  - Escalated.
  - Reopened.
  - Repeat contact.
- **Service levels:** SLA targets and breaches, plus backlog over time.
- **Event log:** a case event log (created, searched, info requested, escalated, approved, adjusted, reopened) suitable for process-mining-style analysis.
- **Member-side text:** synthetic complaint and follow-up messages, and agent case notes of uneven quality.
- **Manual adjustment log**, including the seeded duplicate-credit incidents.
- **Synthetic post-case survey scores and comments.** These are generated by an explicit, documented formula: scores drop with false denials, repeat contacts, reopen events, and long resolution times. Label them **"modeled satisfaction proxy: demonstrates the analysis method, not real sentiment."**

### F3. Pre-registered legacy defect catalog (`docs/legacy-defect-catalog.md`)
Columns:
- ID.
- Defect.
- Realistic cause.
- How it is seeded.
- Frequency.
- Affected scenarios.
- Expected member impact.
- Expected business impact.
- Intervention class (data fix / configuration fix / integration fix / UI fix / training/process / AI-assisted / none possible).
- Detection method.
- Which arm is expected to fix it.

The catalog includes at least the following.

**Data quality:**
- Duplicate member profiles.
- Stays attached to an old or merged member number.
- Missing booking channel.
- Timezone-shifted checkout timestamps.
- Partner/OTA bookings with a different confirmation format.
- Delayed ledger postings.
- Reversed and re-posted transactions.

**Configuration and process:**
- Legacy rules still using a superseded waiting period for some properties.
- Policy updated but keyword index stale.
- Manual adjustment without a duplicate check (two agents credit the same stay).
- No approval binding (approval given on an older evidence version).

**Search and UI friction:**
- Keyword search misses synonyms ("didn't get my points" vs. "missing credit").
- Member lookup requires an exact match.
- Evidence is spread across several screens.
- No view of the policy version by stay date.

**Unstructured input (where AI may add value):**
- Free-text requests mentioning several stays.
- Wrong or partial confirmation numbers.
- Nicknames and name-format differences.
- Dates in mixed formats.
- In-scope claims mixed with complaints or out-of-scope asks.
- Policy exceptions buried in long policy text.
- Evidence contained only in a synthetic folio or receipt text attached to the case.
- Non-English requests.

**Not fixable by any arm:**
- Genuinely missing upstream records.
- Conflicting records that need property confirmation.

The correct outcome for these is escalation or clarification.

**Control cases:** straightforward cases the legacy workflow already handles correctly.

### F4. Business KPI tree and financial model
- **`docs/kpi-tree.md`** connects four layers:
  1. **Business goals:** member trust and experience, cost to serve, points-liability control, auditability.
  2. **Operational KPIs:** first-contact resolution, time to resolution, repeat contacts, reopen rate, SLA attainment, backlog.
  3. **Quality KPIs:** final-outcome accuracy, false denials, false approvals, duplicate credits, evidence completeness, correct escalation.
  4. **System metrics:** latency, failures, cost per case.
- **Financial model** (`evaluations/financial_model.py`).
  - **Inputs** are configurable, labeled assumptions:
    - Agent cost per hour.
    - Points-liability value per point.
    - Monthly case volume.
    - Model cost per case.
    - Infrastructure and maintenance effort.
  - **Outputs:**
    - Over-credit leakage.
    - Under-credit member-harm proxy.
    - Handling cost.
    - Incremental AI cost.
    - Cost per correctly resolved case.
    - Break-even volume.
  - **Sensitivity analysis** over the key assumptions.
  - Every output is labeled **"estimate under stated assumptions."**

### F5. Pre-registered hypotheses (`docs/hypotheses.md`)
These are committed before any arm-C benchmark run. Each hypothesis states its metric, dataset slice, threshold, and decision rule. Each is reported as **supported / not supported / inconclusive**.
- **H1:** B improves final-outcome accuracy over A on held-out cases (non-AI fixes matter).
- **H2:** C improves correct-action rate over B by at least the threshold, **without increasing false approvals**.
- **H3:** C reduces false denials specifically on unstructured-input scenarios.
- **H4:** C improves missing-information detection and reduces unnecessary information requests and repeat contacts in the simulated member journey (F6).
- **H5:** C's cost per correctly resolved case stays within the limit, and its latency stays within the SLO.
- **H6:** No arm has any unauthorized action or duplicate credit. This is a hard gate.
- **H7:** C reduces human handling time per correct resolution. Tested only if real participants run the timing protocol; otherwise reported as **not tested**.

### F6. Simulated member (customer) journey
Model the member side of each case for every arm:
- The initial request.
- Each information request from support.
- Follow-ups while unresolved.
- Reopen if the outcome was wrong.
- Simulated processing delays.

Compute per arm:
- Contacts per case.
- Simulated days to resolution.
- Whether the member ended with the correct points.
- Modeled satisfaction proxy (the F2 formula).

Label everything as **simulated**. Real satisfaction is measured only through the pilot survey with real participants.

### F7. End-to-end proof chain (primary success definition)
For every held-out case and every arm, record the chain:

request understood → correct evidence found → correct policy version → correct eligibility → correct action proposed → approval decision → execution → **final ledger state correct** → member-journey outcome → KPI contribution.

How this is scored:
- **Primary business metric: final ledger-state accuracy.** The simulated final points ledger is compared against the ground-truth expected ledger. A case counts as successful **only** if the final ledger and case outcome are correct with no duplicate.
- **Failure location:** report where in the chain each failure occurred, per arm (a failure funnel). This shows *where* AI helps or hurts.
- **Simulated supervisor:** for automated benchmarking, the supervisor follows a documented deterministic review policy. It also runs a variant with a configurable automation-bias rate (links to E2). Label it simulated. Real reviewer behavior comes only from UAT participants.

### F8. Legacy discovery deliverables (before building B and C)
- **Day-one discovery analysis** (notebook or report plus a dashboard page) on the synthetic history:
  - A Pareto chart of the top failure drivers.
  - The modeled cost of failures.
  - Where handling time goes.
  - Reopen and rework loops from the event log.
  - SLA and backlog trends.
- **A one-page problem statement** with the quantified synthetic baseline.
- **Opportunity sizing:** each defect mapped to an intervention, as an impact vs. effort matrix, with a **predicted** improvement per arm.
- **After benchmarking:** **predicted vs. actual** improvement per intervention. Explain the differences.

### F9. Bias guards
- Arm-C development never sees the held-out split or generator metadata.
- The same defects are present for all arms.
- Arm B receives fair fixes for every non-AI-addressable defect.
- Report every slice where B or A beats C.
- If an independent reviewer is available, they review the defect catalog. Otherwise record "not independently reviewed."
- Any change to the catalog or hypotheses after results are seen is logged with a reason and treated as a new experiment.

**Milestone placement:**
- F1–F5 and F8 (discovery analysis) go into Milestones 2–3 and must be committed before Milestone 7.
- F6 and F7 are implemented in Milestone 10.
- F8's predicted-vs-actual goes into Milestone 10 and the case study (Milestone 19).

---

## APPENDIX G: Tool roles from the source video (mandatory for the Part H learning track)

The video describes a creator's personal workflow, and parts of it are **sponsored** (Egolite). Treat its claims as **hypotheses to verify and measure, not facts**. Each tool's assigned exercise below reflects the role the video gives it. Part H rules (verification, attribution, no customer data, Blocked when unavailable) still apply.

| Tool | Role described in the video | Exercise in this project | Verification and caution |
|---|---|---|---|
| Claude Code | Everyday driver: fast answers, document analysis, scripting, brainstorming a client approach; MCP servers connected so it knows your files and tools | Primary implementer. Also connect this project's MCP server (G.3) to Claude Code and use it to analyze the synthetic discovery history (F8) and draft a client-approach brief | Record which work it did. Distinct from the Claude API runtime |
| Egolite (sponsor) | Gives Claude its own browser workspace separate from Chrome; may use existing sessions; runs one JavaScript snippet per pass; free; macOS only; data stays local | Pre-client-call research on **public** information or a **local synthetic site** (for example, competitor loyalty-program terms), producing a sourced research summary | Verify identity, install, and OS first. Sponsor claims about speed, token savings, and privacy stay **unverified unless measured**. **Never use logged-in sessions to customer, company, or personal accounts.** Blocked if no macOS |
| Mira | Personal AI agent in Telegram; async, always on call when away from the desk | After verifying the exact product: request a status summary of `implementation-status.md` (synthetic project info only) and receive milestone notifications | If unverifiable, ask whether to do a generic Telegram exercise instead. No secrets, customer data, or deploy authority |
| Codex | Complex, production-grade code; slower and costlier but more thoroughly validated; reasons through edge cases | Independent review or second implementation of the **reconciliation and idempotency module**, plus extra edge-case tests. Compare with Claude Code's version on defects found, time to verified result, and cost | Comparable bounded task; record task order and familiarity |
| Cursor | Primary editor for serious, multi-file work; multi-model and local-model support | My personal exercise: run the same bounded change with two models inside Cursor (and a local model if hardware allows), then run tests and review the diff | Use the current Cursor rules mechanism, shared with CLAUDE.md/AGENTS.md |
| CodeRabbit | Automated review on every pull request; treats AI output like human output | After authorized repo-level installation, enable it on every PR. Track findings by category over the project and how each was resolved | Tests and human review remain independent |
| Supabase | Default backend: database, auth, row-level security, cloud/edge functions, vector storage; schema easy for AI to reason about | Supabase-hosted Postgres and Auth profile. **pgvector is used only in the retrieval comparison experiment** (full-text vs. hybrid) and adopted only if measured better. Optional edge-function exercise (for example, signed webhook intake) | RLS caveat (C.5). Alembic still owns the schema |
| Vercel + bolt.new | Vercel for fast Node/TypeScript deploys; bolt.new turns a brief into a clickable prototype quickly (video says under 20 minutes) | Write the client-demo brief, generate the prototype in bolt.new, **time it** (measured vs. claimed), review the code, integrate it as the React frontend, and deploy to Vercel when authorized | Never fabricate the prototype. Backend stays on AWS |
| Monday.com | Project ops with agents: reminders, automated status updates, workflow triggers | With authorized access, a board for milestones, requirements, and bugs, updated by one automation from CI or milestone results, plus one reminder or trigger | Otherwise provide an import file. No invites or messages |
| Miro | Visual thinking and collaboration: architecture diagrams, client walkthroughs, workflow mapping with non-technical stakeholders | Board with current vs. proposed workflow, defect Pareto (F8), architecture, trust boundaries, and agent loop. Run a **simulated stakeholder walkthrough** script and write the decisions back into `docs/decisions.md` | Simulated participants labeled. Create the board only with access |
| Kimi, GLM, Qwen | Long-running or credit-intensive tasks where frontier quality isn't needed | Implement a documented **model-routing policy**: Claude stays default for investigation. Test whether an open-weight model meets the threshold for credit-heavy offline tasks, such as generating paraphrased request text for the stress set (labels still come from facts, never from the model) or batch-summarizing evaluation failures. Optionally run the held-out investigation benchmark on one of them | Verify the exact release, license, and hosting. Never route data to an unapproved provider. Report quality, cost, and latency honestly |
| Invoco | Voice-to-text productivity on Mac | Dictate a discovery note and a requirement. Measure transcription errors and correction time | Verify product and OS. Never a runtime dependency |

**Stack principle from the video, applied and tested.** The video's recommended starting point is one daily agent, one capability layer, one review layer, and one managed backend, with specialized models and automations added only when the workflow needs them. Add a **"minimal stack vs. full stack"** section to `docs/fde-tool-map.md`. Based on the measured exercises, give a **keep / drop / undecided** recommendation for each tool, with evidence. Don't keep a tool just because the video uses it.

**Milestone placement:** Appendix G exercises run in Milestone 15. Exceptions: Miro discovery boards go with Milestone 2 if access exists, and the Codex reconciliation review goes with Milestone 6 or 13.

---

## APPENDIX H: Document and vision extraction with review routing (Tier 2)

### H1. Synthetic supporting documents
- Generate supporting documents from the synthetic records and attach them to cases:
  - Folio PDFs in several layouts.
  - Receipt images with realistic noise: scan blur, rotation, crop, low contrast.
  - Partner/OTA booking-confirmation emails.
- Some documents disagree with the system of record (wrong dates, different confirmation format). Some contain embedded injection text.
- Each document's ground-truth fields come from the generator.

### H2. Extraction service
- **Fields:** confirmation number, property, arrival and departure dates, rate, total, member name, member number. These go into a typed schema.
- **Two methods:**
  - **Non-AI baseline:** OCR plus template/regex rules.
  - **Model-based vision extraction** through the provider interface. The offline mock returns deterministic fixture outputs, clearly labeled.
- **Field confidence comes from verifiable signals only:**
  - Format validation.
  - Cross-check against the system of record.
  - Agreement between the two methods.

  It never comes from model self-reported confidence. No probability-style percentages are shown.
- **Review routing:** low-confidence, mismatched, or conflicting fields are routed to human review. Extracted values are **evidence only**. They never overwrite system-of-record data and never bypass approval.

### H3. Evaluation
- Field-level exact match, precision, and recall per field and per document variant (clean vs. noisy layouts).
- Human-review rate.
- Cost and latency per document.
- **Downstream effect:** how many otherwise unresolvable cases become correctly resolved, measured by final-ledger accuracy (Appendix F7) with and without extraction.

### H4. Security
- File-ingestion controls (C.7): type and size limits, safe parsing, no active content.
- PII handling (Appendix E3) and retention.
- Embedded-injection tests that assert on business effects.

### H5. Portfolio wording
Present this as the same document-processing *pattern* used in enterprise work. **Never reuse employer numbers** as project results.

**Milestone placement:**
- Document generation: Milestone 3.
- Extraction: Milestone 8.
- Evaluation: Milestone 10.

---

## APPENDIX I: Classical ML and small-model baseline (Tier 2)

### I1. Task
Classify incoming requests and route them. Classes:
- Missing points.
- Out of scope.
- Complaint only.
- Multi-issue.
- Non-English.
- Suspected injection or abuse.

### I2. Methods compared on the same grouped splits
1. Rules and keywords (the legacy approach).
2. TF-IDF + logistic regression (scikit-learn).
3. LLM zero-shot and few-shot through the provider interface.
4. Optional: an embedding model plus a light classifier, and/or a small open model fine-tuned with a parameter-efficient method.

   Run option 4 only if hardware or budget allows. Otherwise mark it Blocked with exact prerequisites.

### I3. ML engineering practice
- Reproducible, seeded training script.
- Versioned model artifacts.
- Grouped train, validation, and test splits.
- Class-imbalance handling.
- Confusion matrix and per-class metrics.
- **Calibration measured with a reliability curve.** A calibrated probability may be displayed **only** for a classifier whose calibration was measured on held-out data.
- Drift check on the stress set.
- A model card for the chosen classifier.
- Cost and latency per 1,000 requests.

### I4. Decision rule
- Choose the routing method by accuracy, cost, and latency against pre-set thresholds.
- If the classical model is good enough, use it and say so. "A $0 model beat the LLM for routing" is a strong FDE result.
- Training text is synthetic. LLM-generated paraphrases are allowed, but **labels always come from scenario facts**, never from a model.

**Milestone placement:**
- Training and selection: Milestone 8.
- Benchmark reporting: Milestone 10.

---

## APPENDIX J: Domain-agnostic engagement method (Tier 4)

### J1. The method
`docs/engagement-method.md` describes the engagement in domain-neutral steps, each mapped to the stage 9 artifact that instantiates it:

| Domain-neutral step | Stage 9 artifact |
|---|---|
| Discovery | Part A plus the stage 0 addendum |
| Baseline | Appendix F |
| Defect catalog | Appendix F3 |
| Deterministic core | B.7 |
| Bounded AI layer | B.9 |
| Write-path integrity | B.10 |
| Evals and benchmark | Part E |
| Security | Part C |
| Rollout | F.3 and Part I |
| Handover | Part I |

### J2. The pattern
- Name it: **"evidence-based adjustment with human approval."**
- It generalizes to:
  - Billing credit disputes.
  - Insurance claim corrections.
  - Refunds.
  - Payroll corrections.
  - Chargebacks.
  - Warranty claims.
- Document what **changes** per domain:
  - Rules.
  - Systems of record.
  - Approval authority and limits.
  - Regulations.
  - Data access.
  - Cost asymmetry between false approvals and false denials.
- Document what **stays**:
  - Harness.
  - Approval binding.
  - Idempotency and reconciliation.
  - Evaluation and benchmark method.
  - Security patterns.

### J3. Proof on a second mini-domain
- Use the starter-kit scaffold (Part J) to generate a fictional **"telecom billing credit dispute"** mini-project with:
  - Its own small rule set.
  - A mock billing API.
  - 15 labeled cases.
  - A mini A/B/C benchmark.
- Run its smoke test and mini benchmark.
- Record the time taken, what was reused unchanged, and what had to be redesigned.
- Label it honestly as a method demonstration, not a product.

### J4. Day-one intake checklist
`docs/domain-intake-checklist.md` lists the questions to ask on day one in any domain:
- Systems of record.
- Money-like or irreversible actions.
- Approval authority.
- Regulations.
- Data access path.
- Success metric.
- Cost of each error type.
- Existing baseline data.
- Who owns the result after handover.

### J5. Explicit statement
The method and infrastructure transfer. Discovery, rules, data access, validation, and approvals must be redone for every customer. Prototype speed is not production speed.

**Milestone placement:** Milestone 17.

---

## APPENDIX L: Final enterprise additions

### L1. Live public demo link (Tier 2, near Milestone 12)
Every published stage on vamsialla.com has a live app, so Stage 9 should too.
- **Prepare:** a low-cost hosted deployment of the **public demo mode** (C.8).
  - Synthetic data only.
  - Mock AI by default, or live AI with a hard spending cap.
  - Request limits.
  - No shared admin account.
  - Scheduled demo reset.
- **Before anything is created,** present me with:
  - Two or three hosting options with monthly cost estimates, sourced from current official pricing.
  - Teardown steps.
- **Deploy only after I approve the option and budget.** Then verify the live URL with the Playwright happy path and add "Live app →" to the portfolio card, using the site's "wake up" note style if on free or sleeping hosting.
- Until approved, the card shows no live link.

### L2. GenAI telemetry conventions (Milestone 12)
- Check the current OpenTelemetry semantic conventions for generative-AI and LLM calls, and their stability status.
- If they're usable, instrument model calls with them: model, token usage, latency, finish/stop reason. Never include prompt or response content by default.
- Record the version and stability status in `docs/decisions.md`. If the conventions are still experimental, say so and keep the attribute names isolated in one module for easy migration.

### L3. AI observability tooling decision (Milestone 12)
- In `docs/fde-tool-map.md`, add a short evaluation of dedicated LLM observability and eval tools (for example Langfuse, Arize Phoenix, LangSmith): what they add over this project's OpenTelemetry tracing and own eval runner, plus data destinations, hosting options, and cost.
- Optionally run a small trial with one self-hostable option on synthetic traces, only if it needs no paid account.
- Conclude with **adopt / not needed / revisit at scale**, with reasons. Label it documentation-only if no trial ran.

---

## APPENDIX K: Credentials, keys, and account access (mandatory)

### K1. Rules
- **I supply values only through a local `.env`** (git-ignored) or a secret manager. **Never** ask me to paste a key, token, or password into chat. **Never** write real values into any committed file, log, screenshot, test fixture, or prompt.
- **Do not open, print, or `cat` the `.env` file.** Check readiness only with `python -m app.preflight`. It reports each variable as `set` / `missing` / `invalid format`, never the value. I may add Claude Code permission deny rules for reading `.env`; respect them.
- **Scoped tokens, never account passwords.**
  - Use fine-grained, single-repo, least-scope tokens.
  - AWS uses SSO/profile credentials, not long-lived access keys.
  - Recommend that I set spending limits in each provider console as well as in the app budgets.
- **Missing value:** the feature runs in mock/offline mode, or its exercise is marked **Blocked: needs `<VAR>`**. Never fail the core app because an optional key is missing.
- **Browser-login tools** (bolt.new, Cursor, Egolite, Invoco, Mira, CodeRabbit install, first Miro/Monday setup) need my one-time manual login. Give me exact steps, then continue other work. Never use my browser sessions or saved passwords.
- **Verify names:** check every variable name marked `(verify)` against current official vendor docs. Correct `.env.example` and record the source.

### K2. Deliverables
1. **`.env.example`:** keep the template supplied with this spec (core, Claude API, Bedrock, Kimi/GLM/Qwen, Keycloak, Supabase, GitHub, Vercel, Monday, Miro, Telegram, observability, feature flags). Extend it as features are added, with comments only and no values.
2. **`.gitignore`:** includes `.env`, `.env.*` (except `.env.example`), and any key files.
3. **`.claude/settings.json`:** deny rules for reading `.env` files. Verify the current permission syntax in the Claude Code docs.
4. **`docs/accounts-setup.md`.** For each tool:
   - Sign-up link (official only).
   - Free-tier limits relevant here.
   - How to create the minimal-scope token.
   - Which `.env` variable it fills.
   - How to set a spending limit.
   - How to revoke it.
5. **Preflight readiness report:** which features and exercises are unlocked by the currently set variables.
6. **Secret scanning (gitleaks) in CI and as a pre-commit hook.** A test fails if any value from `.env` appears in tracked files.
7. **Rotation:** a documented procedure, exercised once with a test credential (Part K exercise).

**Milestone placement:**
- `.env.example`, `.gitignore`, deny rules, and preflight: Milestone 1.
- `accounts-setup.md`: Milestone 1, then extended as tools are reached.
