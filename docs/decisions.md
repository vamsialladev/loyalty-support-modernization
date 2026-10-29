# Decisions (ADR style)

Each decision records context, decision, tradeoff and result. From 2026-10-28 (project purpose) new ADRs also
record the **options considered** and **what would change this decision**, so a new engineer can see how the
choice was made, not only what it was. ADR-0001 to ADR-0010 are the binding resolutions
from spec Part 0.6. Later ADRs are made during the build. A decision is changed only by a new ADR that supersedes it.

## ADR-0001: Claude Code is the primary implementer
- **Context:** the source drafts named several coding assistants (spec 0.6, Part H).
- **Decision:** Claude Code builds this repository. Codex and Cursor run as separate, attributed exercises.
- **Tradeoff:** one implementer keeps the codebase consistent; comparisons between assistants happen only on
  bounded, comparable tasks.
- **Result:** in effect from Milestone 1. Never attribute one tool's work to another.

## ADR-0002: PostgreSQL 16; Alembic owns the application schema
- **Context:** Supabase offers its own migration tooling; two owners of one schema drift apart.
- **Decision:** Alembic owns every application migration. Supabase is a managed Postgres host (hosted profile) and a
  local CLI option. Supabase migrations never touch the application schema.
- **Tradeoff:** no Supabase-dashboard schema edits; one migration path to review.
- **Result:** applies from Milestone 4.

## ADR-0003: one IdentityProvider port, three adapters, one active
- **Decision:** adapters for local demo auth (offline default), local OIDC (Keycloak in Compose) and Supabase Auth.
  Exactly one is active per deployment.
- **Tradeoff:** an extra port layer; in return no two competing auth systems.
- **Result:** applies from Milestone 9 (Supabase Auth in Milestone 15).

## ADR-0004: server-rendered console first; React only from a real bolt.new prototype
- **Decision:** Jinja2 + HTMX + CSS console first; it is the always-working UI and fallback. The React/TypeScript
  frontend starts from a real bolt.new prototype and uses the same API and AG-UI events. Without bolt.new access it
  stays "Blocked: bolt.new access".
- **Tradeoff:** two frontends to keep in step; the server-rendered one never depends on a JavaScript build.
- **Result:** applies from Milestone 5. No fabricated bolt.new artifact.

## ADR-0005: Docker Compose first; AWS for API/worker; Vercel only for the React frontend
- **Decision:** local Compose first. AWS (ECS Fargate + RDS, or Supabase-hosted Postgres) for API, worker and mock
  API. Vercel only for the compatible React frontend.
- **Tradeoff:** a FastAPI + worker + Postgres stack cannot use the free Streamlit hosting the other stages use
  (`docs/continuity.md` §12). Hosting options and costs go to the owner before anything is created (Appendix L1).
- **Result:** applies from Milestone 4 (Compose) and Milestone 12 (IaC, validate only).
- **What would change this decision:** a client mandating a different cloud or a fully managed platform; or the
  M12 hosting options showing a cheaper option that still runs the worker and Postgres safely.

## ADR-0006: live model through an application-owned provider interface; default Claude Haiku 5.5
- **Context:** Claude Code (dev tool) and the Claude API (runtime) are different access types (spec B.2). Every
  published stage uses Claude Haiku 5.5 (`docs/continuity.md` §11).
- **Decision:** runtime model calls go through the provider interface. Offline mock provider by default. The live
  default is Claude Haiku 5.5 (model ID `claude-haiku-5-5`, to be re-verified in official docs at Milestone 8).
  One alternative provider (Kimi, GLM or Qwen) only behind the same interface, with access, by explicit selection.
- **Tradeoff:** an interface to maintain; in return no SDK in domain code and no silent provider switch.
- **Result:** applies from Milestone 8.
- **What would change this decision:** Haiku 5.5 failing the held-out thresholds while a larger model passes them
  within the cost limit (H5); a client requiring a specific provider, region or enterprise endpoint.

## ADR-0007: at least 60 labelled evaluation cases
- **Decision:** ≥60 labelled synthetic cases (supersedes the earlier 40), split dev / validation / held-out / stress.
- **Result:** applies from Milestone 3.

## ADR-0008: Postgres full-text search is the retrieval baseline
- **Decision:** embeddings, hybrid search or reranking only after a controlled comparison shows a benefit.
- **Tradeoff:** stage 1 needed hybrid search for meaning-only questions; Stage 9 measures before adopting it.
- **Result:** applies from Milestone 6.
- **What would change this decision:** the M10 retrieval comparison showing citation or eligibility errors that a
  hybrid variant fixes on held-out cases, at acceptable cost.

## ADR-0009: plain Python state machine for orchestration
- **Decision:** no graph framework or extra agents without a demonstrated, documented benefit.
- **Result:** applies from Milestones 6 and 8.

## ADR-0010: priority order
- **Decision:** core correctness first; then MCP → A2A → AG-UI; then optional labs and tool exercises. Never expand
  optional tooling while core correctness is broken.
- **Result:** enforced through the scope tiers in `docs/requirements-matrix.md`.

## ADR-0011: reuse the existing hotel group and its Guest Rewards program
- **Context:** the spec says to define a loyalty program only if none exists. Stages 1 and 2 already publish the
  "Guest Rewards Loyalty Program" (Silver / Gold / Platinum, 10 points per US dollar on the room rate). The site never
  names the hotel group; stage 7 calls it tenant `hg-demo`.
- **Decision:** Stage 9 keeps the group unnamed, uses customer ID `hg-demo`, properties `beach-resort` and
  `mountain-lodge`, member numbers `GR-#####`, booking IDs `BR-####` / `ML-####`, and the Guest Rewards tiers and
  earning rule. Missing-points rules the program does not define (waiting period, eligible channels, approval
  limits, request process) are added as new versioned fictional policy documents that do not contradict it.
- **Tradeoff:** Stage 9 inherits the earning rule's simplicity; richer rules arrive as dated policy versions.
- **Result:** recorded in `docs/continuity.md` §3–4.

## ADR-0012: Cedarpoint Inns is a new, separate fictional customer
- **Context:** stage 7 has a second tenant, `hg-other` (`city-hotel`), used only to prove tenant isolation. The
  spec names Cedarpoint Inns as Stage 9's second customer, with its own profile and database.
- **Decision:** Cedarpoint Inns is new. It is not `hg-other`, not a tenant row, and runs as a separate Compose project
  with its own database (spec B.4, Appendix B).
- **Tradeoff:** a little duplication of infrastructure config; in return no implied multitenancy claim.
- **Result:** applies from Milestone 14.

## ADR-0013: branch `main`; Milestone 1 committed directly; branches and PRs once a remote exists
- **Context:** the repo was initialised on `master` with three spec commits and no remote. The portfolio uses
  `main`, and a brand-new repo gets its first commits on `main`, then PRs.
- **Decision:** renamed `master` to `main` (local, reversible). Milestone 1 is committed on `main`. Once the owner
  approves creating the GitHub repository, later milestones go through branches and PRs.
- **Result:** done 2026-10-28.

## ADR-0014: preflight profiles and output
- **Context:** spec B.2 lists six operating profiles; `.env.example` lists `portfolio | discovery | staging |
  approved` for `APP_PROFILE`.
- **Decision:** `python -m app.preflight --profile <p>` accepts `portfolio`, `live-model`, `discovery`, `staging`,
  `approved` and `enterprise-identity`. `live-model` and `enterprise-identity` are overlays on `portfolio`. Each
  variable is reported as `set`, `missing` or `invalid format`, with its source (`environment` or `.env`), never
  its value. Process environment overrides `.env`. A selected provider without its key is "not ready", never a
  silent fall back to mock. Exit code 0 = ready, 1 = not ready, 2 = usage error. `APP_PROFILE` gets the two
  overlay values too.
- **Tradeoff:** format checks are shallow (prefixes, URL shapes, numbers, enums); they catch typos, not revoked
  keys. A live key check is a separate, explicit smoke test (Milestone 8).
- **Result:** implemented and tested in Milestone 1.

## ADR-0015: uv, Python 3.12, committed lockfile
- **Decision:** `uv` manages dependencies; `uv.lock` is committed; `requires-python = ">=3.12,<3.13"`. Direct
  dependencies use compatible-release lower bounds written by `uv add`; the lockfile pins exact versions.
- **Result:** Milestone 1 (`python-dotenv`; dev: `pytest`, `ruff`, `mypy`).

## ADR-0016: Appendix F defect catalog and hypotheses are written in Milestone 2
- **Context:** the spec's "Begin now" list puts the defect catalog and hypotheses right after the tracking files;
  Appendix F's placement says Milestones 2–3, committed before Milestone 7. The owner asked for a plan-mode check
  before each milestone.
- **Decision:** write and commit them in Milestone 2, alongside the discovery package they depend on, and in any
  case before any arm-B or arm-C code exists. Git history is the pre-registration evidence.
- **Result:** done 2026-10-28. Catalog and hypotheses approved by the owner and committed as the
  pre-registration commit, before any arm-B or arm-C code.

## ADR-0017: "Planned (M#)" status for requirements no milestone has reached
- **Context:** the Part 0.4 labels describe built or blocked work; most rows start before any work exists.
- **Decision:** use `Planned (M#)` until a milestone reaches the row, then a Part 0.4 label. Completion scores
  count only "Implemented and verified" and "Not applicable".
- **Result:** in `docs/requirements-matrix.md`, counted by `scripts/matrix_scores.py`.

## ADR-0018: an "A as-is" variant shows what the safe write path alone prevents
- **Context:** spec B.8 requires identical safeguards in every arm, so legacy defects D10 (no duplicate check) and
  D11 (no approval binding) cannot occur in arms A, B or C. Without a comparison, the write path's value would be
  invisible in the benchmark.
- **Decision (owner, 2026-10-28):** add an "A as-is" variant: arm A's scripted agent with the same authorization but
  the legacy write path (no approval hash, no ledger re-check, no cross-case duplicate check, a fresh idempotency
  key per attempt). Reported separately next to arm A, excluded from H1–H6, run only inside the benchmark runner on a
  disposable database, unreachable from the console, API or any profile (test in Milestone 10).
- **Tradeoff:** one more code path to keep isolated; in return the benchmark measures the write path's effect on its
  own, credited to neither B nor C.
- **Result:** pre-registered in `docs/legacy-defect-catalog.md` §2b and `docs/hypotheses.md` §3a.

## ADR-0019: what AI does and what stays deterministic (spec A.3)
- **Context:** stage 0 rejected AI-decided refunds; the sponsor's stop condition is points moving without a supervisor.
- **Decision:** AI (arm C) interprets requests, chooses read-only tools within an allowlist, summarises evidence,
  finds policy text and explains with citations, flags missing information and drafts recommendations. Eligibility,
  points, permissions, approvals and execution are deterministic Python.
- **Tradeoff:** the AI can't fix a wrong rule; in return a wrong or manipulated model output can't move points.
- **Result:** applies to all arms (`docs/product-requirements.md` §3).
- **What would change this decision:** nothing in this engagement. Moving eligibility or amounts to a model would
  need a different risk appetite from the sponsor, audit and security, and evidence that a model is more accurate
  than written rules; neither exists.

## ADR-0020: build vs buy
- **Decision:** build the investigation workflow and benchmark (the point of the project is to measure them);
  reuse maintained components for everything generic: Postgres, FastAPI, Alembic, Keycloak, the official model and
  protocol SDKs. No case-management product is bought for the simulation.
- **Tradeoff:** more code owned; in a real engagement, embedding in the client's CRM is the likely route (ENT-29).

## ADR-0021: managed vs self-hosted
- **Decision:** self-hosted in Docker Compose for development and the benchmark; managed Postgres and container
  hosting only for an approved hosted profile (ADR-0005). The model is a managed API (no self-hosted model unless the
  open-model exercise justifies one).
- **Tradeoff:** local setup takes Docker; in return no paid resources without approval.

## ADR-0022: integration through versioned REST contracts with adapters
- **Decision:** the app talks to the (mock) loyalty platform and PMS through versioned OpenAPI contracts and adapter
  interfaces; no direct database access to systems of record; adjustments only through the adjustment API with an
  idempotency key. Event-driven triggers are documented options (ENT-30), not the core.
- **Tradeoff:** polling and request/response only; in return real systems can replace the mocks adapter by adapter.
- **What would change this decision:** the client's systems exposing only events or files (then an event or batch
  adapter behind the same interface), or volumes where polling becomes the bottleneck.

## ADR-0023: REST for the core; MCP as an optional read-only interface
- **Decision:** the core app uses REST internally. An MCP server exposing read-only loyalty tools is built in
  Milestone 11 for other AI clients, following stage 7's conventions (role decides tools and fields, every call
  audited). MCP never exposes adjustment execution.
- **Tradeoff:** two interfaces to the same services; MCP adds value only for external AI clients.

## ADR-0024: full-text search before embeddings
- **Decision:** confirms ADR-0008 for the A.3 list: Postgres FTS with stemming and a synonym list (arm B); an
  embedding or hybrid variant only as a separate, measured experiment.

## ADR-0025: one bounded agent, no orchestration of several agents
- **Decision:** a single bounded agent loop (plain state machine, ADR-0009). The A2A coordinator/specialist pair in
  Milestone 11 is a protocol lab, not the core workflow.
- **Tradeoff:** less parallelism; in return every step is testable and stop conditions are explicit.

## ADR-0026: data processing boundaries
- **Decision:** member and stay data stay in the app's Postgres and the mock API. The model provider receives only
  the minimised, redacted context for the current case (no card, passport or full contact data); nothing else is sent
  to any external service. Logs and traces never carry prompt or response content by default. Evaluation datasets
  are synthetic.
- **Tradeoff:** the model sometimes lacks context; it then asks or escalates.

## ADR-0027: operational ownership after handover
- **Decision:** as in `docs/governance.md`: the administrator owns policies and rule configuration, the sponsor owns
  rollout gates and business thresholds, IT owns integrations and hosting, security owns exceptions and incidents.
  Prompt and model changes go through the change request with regression evidence.
- **Result:** RACI in `docs/governance.md` §2.

## Decision guide: when these would be worth it (spec A.3)

| Option | Worth it when | Not worth it when | In this project |
|---|---|---|---|
| Managed backend (e.g. Supabase) | Small team, standard Postgres + auth, no strict network rules | Client mandates its own cloud and IdP; complex row-level rules must be proven at the app layer anyway | Optional profile (M15); Alembic still owns the schema |
| Visual prototyping (e.g. bolt.new) | Early client walkthroughs; testing a UI idea in hours | The UI must meet accessibility, CSP and security review as-is | React frontend only from a real prototype (M15) |
| External code review (e.g. CodeRabbit) | Many PRs, several contributors, AI-written code | One author, tiny change volume | Exercise on this repo only, with the owner's OK (M15) |
| Workflow automation platform | Many simple integrations owned by non-engineers | Money-like actions needing idempotency, approval binding and reconciliation | Documentation only; Stage 10 territory |
| Self-hosted model | Data must not leave the client network; steady high volume; acceptable quality on the held-out set | Low volume; quality below threshold; no ops capacity for GPUs | Only if the open-model exercise meets the threshold (M15) |

## ADR-0028: a deterministic, pure-Python generator with derived random streams
- **Context:** every later number depends on the synthetic data; it must be reproducible on any machine (spec B.5,
  Appendix C: same seed, same checksum).
- **Options considered:** (a) Faker plus pandas; (b) a one-off script with one global random seed; (c) a small
  package with one master seed and a separate stream per component.
- **Decision:** (c). `rng(seed, "component", ...)` derives a stream per component, so adding a scenario never shifts
  another's output. Name lists and phrase banks live in the repo; no external dataset or service.
- **Trade-off:** less "realistic-looking" variety than Faker; in return outputs never change when a library updates.
- **Result:** `seed_data/generator/`; reproducibility tested against the committed manifest.
- **What would change this decision:** needing millions of rows (then a vectorised generator), or an approved public
  dataset to blend in (`docs/data-sources.md`).

## ADR-0029: labels by construction, checked by an independent reference labeler
- **Context:** labels decide every benchmark number. The same author writes the generator, the rules and (later) the
  arms, so a shared bug could make an arm look right (spec E.1: the evaluated system is never the sole labeler).
- **Options considered:** (a) hand-label cases; (b) compute labels with the app's own eligibility engine; (c) each
  scenario builder declares its intended outcome, and a separate labeler recomputes the label from the stored facts
  and the written policy; generation fails on any disagreement.
- **Decision:** (c). `evaluations/labeler.py` imports nothing from the generator or the app and reads policy
  parameters from the policy files' front matter. The app's engine (Milestone 6) will be written separately again.
- **Trade-off:** three implementations of the rules to keep in step; that redundancy is the point.
- **Result:** on its first full run the cross-check caught a builder error: a multi-stay case (DV-078) totalled 24,809
  points, above the 20,000-point supervisor limit, so the policy says escalate; the builder had said adjust. The
  builder was fixed; the labeler was right.
- **What would change this decision:** a real customer's labelled cases (then those labels win, and the labeler
  becomes a consistency check).

## ADR-0030: commit benchmark cases and labels; regenerate the bulk data
- **Context:** held-out must not drift if the generator changes; the world, history and documents are large and
  reproducible. Owner's decision Q1 (2026-10-28).
- **Options considered:** commit everything; commit cases, labels and the manifest only; commit nothing generated.
- **Decision:** commit `benchmarks/datasets/v1/` (inputs, labels, composition, manifest) and the label-review sheet;
  `seed_data/v1/` (world, history, documents) is git-ignored and regenerated; its checksums are in the manifest.
- **Trade-off:** a fresh clone must run `make data` before Milestone 4 can load the mock API.
- **What would change this decision:** generation becoming slow enough that a fresh clone takes too long (then commit
  the world too), or a dataset licence that forbids redistribution.

## ADR-0031: a separate counterfactual fairness set
- **Context:** spec E1 asks for counterfactual pairs; the pre-registered composition (240 cases) has no room.
  Owner's decision Q2.
- **Decision:** 20 pairs (40 cases) in `fairness.jsonl`: 16 counterfactual pairs (name, language or tier changed;
  identical stay facts) and 4 consistency pairs (only IDs differ). Reported separately; changes no split or threshold;
  logged in the catalog's change log.
- **What would change this decision:** fairness slices in the main splits proving large enough on their own.

## ADR-0032: request text from deterministic templates
- **Context:** paraphrases and other languages are needed (B.5, E9); labels must come from facts. Owner's decision Q3.
- **Options considered:** model-written paraphrases now (key, cost, storage); templates in the repo.
- **Decision:** templates (12 English paraphrase families split by dataset, four styles, Spanish, French, Portuguese and
  German written by Claude Code, not checked by a native speaker). A model-written slice comes in Milestone 15
  (EVAL-06), reported separately, so template wording can't flatter any arm.
- **What would change this decision:** evidence in Milestone 10 that results on template text and model-written text
  differ materially.

## ADR-0033: per-customer field-mapping files over a canonical model
- **Context:** the purpose asks that synthetic data shapes can be replaced by a real customer's shapes.
- **Decision:** canonical, customer-neutral records (`seed_data/generator/models.py`) plus
  `config/customers/<id>.yaml` mapping canonical fields to the customer's upstream names, channels and source codes.
  A real export is mapped the other way by an adapter (`docs/real-system-swap-guide.md`).
- **What would change this decision:** a customer whose data can't be expressed in the canonical model (then the
  model gets a new, versioned field, never a fork).

## ADR-0034: day-one analysis as a report now, a dashboard page with the console
- **Context:** F8 asks for an analysis and a dashboard page before Milestone 7; the console doesn't exist yet. Owner's
  decision Q4.
- **Decision:** `evaluations/discovery_analysis.py` writes `docs/day-one-discovery.md`, `docs/problem-statement.md`,
  charts and the executive-brief block from the history; the dashboard page joins the console in Milestone 7.
- **What would change this decision:** a stakeholder walkthrough needing interactive filtering before Milestone 7.
