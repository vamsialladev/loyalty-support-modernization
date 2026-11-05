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

## ADR-0035: the mock API speaks the customer's field names; the app's adapter maps them
- **Context:** the purpose asks that every mock can be swapped for the real system. Owner's decision Q1 (M4 plan).
- **Options considered:** (a) mock returns canonical names, adapter passes them through; (b) mock returns the
  customer's upstream names from `config/customers/hg-demo.yaml`, adapter maps them to canonical records.
- **Decision:** (b). One small module, `customer_shapes`, does the mapping in both directions from the same file
  (field names, enum codes such as `ACTIVE`/`CHECKED_OUT`, dollars to cents), so the mock and the adapter can't drift.
- **Trade-off:** more code than (a); in return the mapping path a real loyalty platform needs is exercised now, and a
  contract test checks that the OpenAPI field names equal the mapping file.
- **What would change this decision:** a real customer API whose responses need more than renames, codes and unit
  conversions (nested objects, other paging styles): that customer then gets its own adapter, not a bigger mapper.

## ADR-0036: one PostgreSQL server, separate roles and databases
- **Context:** the app and the mock customer systems stand for systems with different owners. Owner's decision Q4.
- **Options considered:** one server with one role; one server with a role and database each; two servers.
- **Decision:** one `postgres:16.15-alpine` container; roles `loyalty_app` (owns `loyalty`) and `mock_api` (owns
  `mock_customer_api` and `mock_customer_api_test`); `CONNECT` revoked from `PUBLIC`, so neither role can open the
  other's database. The admin role (`POSTGRES_USER`) is used only by the init script.
- **Trade-off:** two more local passwords (`APP_DB_PASSWORD`, `MOCK_API_DB_PASSWORD`); the owner's existing values
  stay untouched (`scripts/update-local-env.ps1` adds only missing ones).
- **Result:** the compose check proves `loyalty_app` is refused by the mock database.
- **What would change this decision:** a hosted deployment (separate managed instances per system), or load where
  the two databases compete for one server.

## ADR-0037: a simulated clock (`X-Sim-Time`) instead of reseeding per case
- **Context:** each benchmark case must see the world as it was at its `received_at_utc`. Owner's decision Q2.
- **Options considered:** reseed a snapshot per case; a request header that filters by time.
- **Decision:** reads honour `X-Sim-Time`: ledger entries posted later and queue items not yet queued are invisible;
  adjustments are stamped with that time. Accepted only when `MOCK_API_SIM_CLOCK=true` (a typed error otherwise);
  preflight refuses it with `PUBLIC_DEMO_MODE` and in hosted profiles.
- **Trade-off:** stays and member profiles are not time-versioned (their state is as of the claim by construction).
- **What would change this decision:** scenarios where member or stay records themselves change over time.

## ADR-0038: deterministic failure injection by header and seeded rules
- **Context:** spec B.3 lists the failures to handle; tests and the benchmark must reproduce them on demand.
- **Decision:** `X-Mock-Fault` (auth_failure, rate_limited, timeout, unavailable, malformed, schema_v1_1, duplicate,
  partial, commit_then_lost, plus the test-only crash_before_commit) and an opt-in rule file matching IDs by suffix.
  Both only when `MOCK_API_FAULTS=true`. A timeout is a server-side delay longer than the client timeout, not a hang.
- **Trade-off:** rule counters (`times`) live in memory and reset on restart; data is durable, faults are not.
- **What would change this decision:** faults that must survive restarts or span requests (then a fault table).

## ADR-0039: one transaction for an adjustment and its idempotency record; the platform enforces only the key
- **Context:** spec B.3 requires the operation and its idempotency record to persist atomically; Milestone 6's
  reconciliation depends on a status lookup by key.
- **Options considered:** idempotency in a cache or middleware; in the same database transaction.
- **Decision:** insert the idempotency record (primary key = the key), the ledger entry and the adjustment, store the
  response, commit: one transaction. Same key and same body replays the stored response; same key and a different
  body is 409; a concurrent duplicate loses on the primary key and replays the winner. Different keys for the same
  stay both apply: stopping that is the app's job (M6), and it is what lets the A as-is variant double-credit.
- **Result:** real-Postgres tests: a failure before commit writes nothing; 20 concurrent requests with one key give
  exactly one adjustment and one ledger entry.
- **What would change this decision:** a real platform with different idempotency rules (key expiry, scope per
  client): its adapter then documents and tests those rules.

## ADR-0040: seed data mounted read-only; images carry service code only
- **Context:** labels and generator metadata must never reach a service. Owner's decision Q3.
- **Decision:** `seed_data/v1` is generated on the host and mounted read-only into the mock API container. Images copy
  only `customer_shapes/`, `config/customers/`, their own package and migrations. `.dockerignore` excludes
  `benchmarks/`, `evaluations/`, `seed_data/`, `docs/`, `tests/` and `.env*`; a test checks the Dockerfiles and the
  compose check inspects the built images. Containers run as UID 10001 with read-only root file systems.
- **What would change this decision:** a hosted demo, where the dataset must ship with the deployment (then a separate
  data image or a one-off seed job, still without labels).

## ADR-0041: dependency groups per image
- **Context:** TD-05: generator libraries (reportlab, Pillow, matplotlib) would bloat the service images.
- **Decision:** core dependencies (pydantic, PyYAML, httpx, python-dotenv, tzdata); group `api` (FastAPI, uvicorn,
  SQLAlchemy, psycopg, Alembic); group `data` (generator and analysis); group `dev`. Locally `uv sync` installs all;
  images run `uv sync --frozen --no-default-groups --group api`.
- **What would change this decision:** the app and the mock API needing different dependency sets.

## ADR-0042: problem+json errors, cursor pagination, and an adapter that never guesses
- **Context:** the app must handle every failure the same way, whatever system sits behind the port.
- **Decision:** the mock returns RFC 9457 `application/problem+json` (`code`, `correlation_id`, `Retry-After`) and
  cursor pagination (max 100). The adapter turns everything into typed errors; retries only 429, 503 and read
  timeouts (bounded, honouring `Retry-After`); never retries a write after a timeout or 5xx (`UncertainOutcome`, so
  the caller reconciles first); raises `PartialResult` rather than returning half a ledger; raises `SchemaMismatch` on
  a renamed field while tolerating new ones.
- **What would change this decision:** a customer API with a different error or paging style: its adapter maps that
  style to the same typed errors.

## ADR-0043: arm A's limits live in a legacy layer over a full-capability port
- **Context:** spec B.8 wants a credible legacy workflow whose limits are real, not sabotage, and the owner's
  Milestone 5 brief allows limits only from the pre-registered catalog. The limits must sit somewhere a reviewer can
  see each one and its defect ID.
- **Options considered:** (a) weaken the mock customer API (exact-only search, no posting queue); (b) a legacy layer
  in the app (`app/arms/legacy/`) over the unchanged port; (c) a separate legacy service.
- **Decision:** (b). The mock stays a capable customer system (it can follow merges, search partner confirmations and
  show the posting queue); the legacy screens use only what the legacy tool offered: exact member and stay lookups,
  stays only within the found profile, the first PMS record per confirmation, a ledger view that lists re-posts
  without their stay, no posting-queue screen, a keyword index frozen on 2026-03-15, a rules file that is out of date
  in the catalogued ways, keyword routing of "refund" to billing, and one stay per case. Each behaviour names its
  defect ID in code and in `docs/legacy-discovery.md`. Everything else is correct: points, claim window, approval
  limit, authentication and authorization.
- **Trade-off:** one more layer to read. In return arms B and C use the same port and data, so no arm gets better
  source records (spec B.8), and each fix in arm B is visible as a diff against this layer.
- **Result:** 26 rule tests and 14 screen tests pin each behaviour on synthetic records and on the seeded data.
- **What would change this decision:** a real customer's legacy tool to compare against; its observed behaviour
  would replace these modelled limits, logged as a new experiment (F9).

## ADR-0044: a thin shared write path in Milestone 5, completed in Milestone 6
- **Context:** arm A needs supervisor approval and a simulated adjustment now. The write path's design (approval
  binding, concurrency, reconciliation, durable jobs) is Milestone 6's plan-mode work. Owner's decisions D1 and D1b.
- **Options considered:** execute straight through the port with only separation of duties; build all of Milestone 6
  now; a thin version behind the interface Milestone 6 completes.
- **Decision:** the thin version (`app/services/write_path.py`, `WritePath` protocol): only a supervisor decides
  or executes, never on their own request; the idempotency key is derived from the approval's stored random ID; a
  cross-case duplicate check runs before submitting; an uncertain outcome moves the case to `Execution unknown` and
  a status lookup by key runs before anything else. The duplicate check looks at **adjustments only** (this app's,
  from any case, and upstream `ADJ` ledger entries for the stay). It never interprets postings, reversals, re-posts
  or the posting queue: otherwise the platform would quietly fix D06 and D07 for arm A, which the catalog
  pre-registered as arm B fixes. Milestone 6 decides eligibility revalidation (WP-07) as "re-run the same arm's own
  evaluator on fresh reads" and records it in its RFC.
- **Trade-off:** until Milestone 6 an approval is not bound to an evidence snapshot (D11 could occur in the console),
  concurrent executes are not locked, and execution runs inside the request. No benchmark runs before Milestone 10,
  so no result is affected. Tracked as TD-12 and TD-13.
- **Result:** tests show the requester and agents are refused, a second case for the same stay is refused and
  escalated, a ledger adjustment from elsewhere blocks execution, `commit_then_lost` is reconciled with one credit,
  and a failed lookup leaves the case unknown until a later check (the next execute reconciles first, never
  resubmits). Found while building: a key built from the approval's row number would repeat after an app database
  reset and get a 409 from the platform, so the key uses a random ID stored with the approval.
- **What would change this decision:** a real platform that deduplicates by business meaning, or Milestone 6's RFC
  choosing a different invalidation model.

## ADR-0045: local demo sign-in, server sessions and CSRF ahead of Milestone 9
- **Context:** the browser flow needs real roles, and arm A must not be insecure (spec B.8). Spec C.4 and SEC-07
  belong to Milestone 9. Owner's decision D2.
- **Options considered:** a role picker with no password; signed cookie sessions; server-side sessions behind the
  `IdentityProvider` port (ADR-0003).
- **Decision:** the local demo adapter (`app/adapters/local_demo_identity.py`): argon2id hashes (`argon2-cffi`),
  the same verification time for unknown usernames, server-side sessions storing only the token's SHA-256, 8-hour
  expiry, logout revokes, HttpOnly SameSite=Strict cookies (Secure in hosted profiles), a CSRF token per session on
  every POST and a double-submit token on the login form, role read from the user record on every request. Four
  demo accounts share `DEMO_USER_PASSWORD` from `.env`, generated by `scripts/update-local-env.ps1`, never printed;
  tests generate their own. Strict CSP (`script-src 'self'`, htmx vendored), `X-Frame-Options: DENY`, no stack
  traces in error pages.
- **Trade-off:** no login rate limit, lockout, recovery or deactivation screen yet (Milestone 9). A shared demo
  password is acceptable only for local synthetic data; the public demo (C.8) needs per-user accounts.
- **Result:** 16 HTTP tests (session needed, same refusal for unknown user and wrong password, CSRF, revocation,
  expiry, deactivation, a forged approve by the requester refused, a form "role" ignored, headers, escaping).
- **What would change this decision:** the OIDC profile in Milestone 9, which replaces the adapter, not the
  session or permission code behind it.

## ADR-0046: the app's business tables start in Milestone 5, with B.10 state names
- **Context:** the browser flow needs durable cases, evidence, approvals and an audit trail; spec B.12 bans in-memory
  state for critical work. Owner's decision D3.
- **Options considered:** wait for Milestone 6; start the tables now with the final state names.
- **Decision:** Alembic revision 0002 (`app/persistence/models.py`): users, sessions, cases (B.10 state names and a
  `version` column), case requests, case evidence (server-side snapshots), notes, adjustment requests, approvals,
  execution attempts and one case-event log for audit and instrumentation. Every B.10 state exists; the transition
  table allows what arm A uses and Milestone 6 completes it.
- **Trade-off:** Milestone 6 adds columns (binding hash, expiry), tables (jobs, idempotency records) and an
  append-only role; a migration rather than a fresh schema.
- **Result:** a test compares the migration with the table definitions (no drift) and downgrades it.
- **What would change this decision:** a Milestone 6 design that needs a different case model; it would supersede
  this with a new revision, not edit 0002.

## ADR-0047: the legacy keyword index is a committed file, frozen on 2026-03-15
- **Context:** D09 says the legacy index was built on 2026-03-15 and never rebuilt; D12 says search is exact-term.
  Postgres full-text search is arm B's improvement (Milestone 6).
- **Options considered:** Postgres FTS with stemming switched off; an in-memory index built at start-up; a committed
  JSON file built by a script.
- **Decision:** `scripts/build_legacy_index.py --as-of 2026-03-15` writes
  `app/arms/legacy/data/keyword-index-hg-demo-2026-03-15.json` with each source's SHA-256. Search requires every
  query word in a section (a short stopword list, no stemming, no synonyms). `--check` fails if the file is stale
  against the policy files, and a test runs it.
- **Trade-off:** a second retrieval path to keep, deliberately weaker than arm B's.
- **Result:** the index holds Missing Points Requests v1 and Earning v2 only; "missing points" finds §1 and §3;
  "didn't get my points", "retro credit" and "stay not counted" find nothing.
- **What would change this decision:** none expected; it reproduces a frozen legacy artifact on purpose.

## ADR-0048: a scripted legacy agent and a simulated supervisor, with no scoring before thresholds
- **Context:** Appendix B wants arm A benchmarked by a scripted agent labelled "scripted, not human timing"; spec
  E.3/E.6 want thresholds committed before any run; F7 wants a documented simulated supervisor.
- **Options considered:** drive the browser with Playwright; call the services directly; a separate simplified
  model of arm A.
- **Decision:** `benchmarks/agents/legacy_scripted.py` calls the same services as the browser with ordinary
  accounts (`scripted-agent`, `scripted-supervisor`) and the same permissions. Its reading policy is fixed in its
  docstring: form fields first, then exactly formatted IDs in the text, the sign-off name with the sender's email,
  one stay per case, the ledger expanded to cover checkout, "missing points" as the policy query; a non-English
  message gets a request for English; attachments are never read; nothing is guessed. The simulated supervisor
  approves only a checklist that passed every line. The demo loader opens one case per contact (D10) and reads only
  the request file. Milestone 5 runs it for mechanics only and records no accuracy anywhere.
- **Trade-off:** service calls measure the software path, not screen latency; real handling time needs the timing
  protocol with people (E.7).
- **Result:** every one of the 100 dev cases (102 contacts) ends in a resting state with no system error, no
  rejected adjustment and no label file opened. Two findings fixed while building: the first English check (three
  common English words) took terse English like "Missing points. Beach Resort, ..." for another language, which
  would have added an unregistered failure, so it now looks for unmistakable Spanish, French, Portuguese or German
  words (dev split only: all 3 non-English requests found, no English request flagged); and the simulated
  supervisor rejected every adjustment because the stored checklist lines were a tuple, not a list, until the
  checklist was stored as plain JSON.
- **What would change this decision:** Milestone 10 needing screen-level timings, which would add a Playwright
  driver next to this one, still labelled scripted.

## ADR-0049: Playwright through pytest, offline on SQLite and against the stack
- **Context:** Appendix C, Milestone 5: "Legacy arm A completes a case end to end in the browser". Owner's
  decision D5.
- **Options considered:** Playwright for Node; Playwright for Python with `pytest-playwright`; Selenium.
- **Decision:** Playwright for Python (`playwright` 1.64, `pytest-playwright` 0.10) in the dev group, Chromium
  installed once with `uv run playwright install chromium`. `tests/browser/test_legacy_e2e.py` starts the mock API
  and the app with uvicorn on SQLite copies (offline, part of `scripts\test.ps1`, skipped with a reason if Chromium
  is missing), or targets the Compose stack when `E2E_BASE_URL` is set (`scripts\compose_check.ps1 -Browser`, real
  Postgres). htmx 2.0.11 is vendored after matching the npm tarball's published SHA-512.
- **Trade-off:** a 150 MB browser download per machine; SQLite in the offline run (the stack run covers Postgres).
- **Result:** the agent works DV-001 through the four screens to a 14,840-point request; another supervisor approves
  and executes; the ledger shows exactly that adjustment; htmx loads under the CSP with no console errors. A second
  test shows the requester gets no Approve button and a forged POST with a valid CSRF token gets 403.
- **What would change this decision:** the React frontend (Milestone 15), which would add Node-based tests for that
  frontend only.

## ADR-0050: the legacy ledger view shows 90 days by default, with "Show older entries"
- **Context:** `docs/legacy-discovery.md` said the legacy tool "shows the posted ledger for the last 90 days". A hard
  cut-off would hide old postings, so already-credited claims filed late would look missing: a defect that is not
  in the pre-registered catalog. Owner's decision D4.
- **Options considered:** a hard 90-day view; 90 days with a working "Show older entries"; the full ledger always.
- **Decision:** 90 days by default plus "Show older entries". The checklist refuses a ledger view that starts after
  the stay's checkout date, so the window costs steps (D14-type friction) and never accuracy. The scripted agent
  expands the view whenever the default starts after checkout.
- **Trade-off:** one more click on older claims; it shows up in step counts only.
- **Result:** tests cover the window, the expansion and the refusal of a view that does not cover checkout.
- **What would change this decision:** none; it keeps arm A inside the pre-registered catalog.

## ADR-0052: upgrading an existing volume: a truthful readiness check, repeatable seed, named causes
- **Context:** the owner's stack, on a volume from Milestone 4, reported "loyalty-app-1 unhealthy" on `up`, then seed
  failed with `409 already_seeded`. A real Milestone 4 stack (commit `b238be7`) upgraded on a throwaway volume
  reproduced the seed failure but **not** the unhealthy one: the container's own start command had migrated to `0002`
  before any seed ran, so seed was not what fixed it. Docker no longer holds the owner's health events, so that
  run's cause is unproven; a cold start outlasting the health retries fits (it became healthy by itself, and the
  machine later had 722 MB of 32 GB free and took 63 minutes for a 4-minute test suite), but that is a hypothesis. The reproduction also found a real fault: `/readyz` said the database was "ok" at any revision.
- **Options considered:** make `/healthz` fail until migrated (a false "unhealthy" again, with no cause); a one-shot
  migration container; keep migrate-on-start and make every status truthful.
- **Decision:** keep migrate-on-start (a failed migration stops the container). `/readyz` compares the database with
  this code's Alembic head. Health checks get a 120 s `start_period`, so a slow start isn't a failure.
  `stack.ps1 -Action up` runs `scripts/stack_diagnose.py` afterwards, which names the cause from container state,
  health output, logs and `/readyz` (credentials masked), and migrates when the running app's database is behind.
  `app.seed` treats `already_seeded` as success, still migrating and creating demo accounts; other refusals still fail.
- **Trade-off:** one more script, and cause detection is pattern matching: an unknown failure falls back to the last
  log lines rather than a diagnosis.
- **Result:** unit tests per cause; the compose check now recreates the earlier state (revision 0001, mock data kept)
  and runs the owner's commands, including seeding twice.
- **What would change this decision:** a hosted deployment, where migrations belong in a release step with their own
  failure handling, not in container start (Milestone 12).
- **Update (2026-11-04, Milestone 6):** the unhealthy failure was seen happening for the first time, on the compose check
  at 99-100% CPU with 1.1 to 3.6 GB free: `mock-api` answered but its health check failed. The check starts Python inside
  a 3-second limit, now 10 seconds. This supports the slow-machine hypothesis for the owner's run; it doesn't prove it.

## ADR-0053: a private repository and a first CI workflow before Milestone 6
- **Context:** the owner approved creating `vamsialladev/loyalty-support-modernization` as private. No workflow existed
  (TD-02; the full CI is Milestone 12), so "enable CI" meant writing one. Milestone 6's concurrency work benefits from
  real-Postgres tests on every change.
- **Options considered:** push now with CI waiting for Milestone 12; a first workflow now, with the full pipeline left
  to Milestone 12.
- **Decision:** `.github/workflows/ci.yml`: ruff, format, mypy, the offline suite with the coverage gate and browser
  tests, the real-Postgres mock API tests, `pip-audit`, and gitleaks over the full history. Not included until
  Milestone 12: image builds, the compose check, SBOM, Trivy, lychee. From here on, work goes on branches with pull
  requests (ADR-0013). The repository stays private until the owner says otherwise.
- **Trade-off:** private repositories use the free Actions allowance, and GitHub secret scanning isn't available on a
  free private repository, which is why gitleaks runs in CI.
- **What would change this decision:** making the repository public, which turns on free secret scanning and push
  protection (steps in `docs/session-handoff.md`).

## ADR-0054: a close needs the evidence its code claims (TD-17)
- **Context:** the owner closed case A-000010 as `deny_claim_window` with no evidence attached, and the tool accepted it
  because the override path took any note. The stay was inside the 12-month window, so the denial was wrong. No
  catalog defect covers this, and spec B.8 rules out making arm A incompetent on purpose: it was a gap in the
  Milestone 5 build.
- **Options considered:** log the close and rely on review (the harm has already happened by then); remove overrides
  (real agents have reasons the rules don't cover, and spec E.2 counts overrides); check each code against what it
  claims.
- **Decision (approved by the owner, 2026-11-04):** in `cases.close_case`, on the server:
  - While the checklist says `incomplete_evidence`, every rule-based code is refused, whatever the note says:
    `no_adjustment_credited`, `wait_until`, `not_checked_out`, `deny_channel_ineligible`, `deny_claim_window`.
  - `deny_not_found` needs a logged search that found nothing. It looks at the first record still missing (member,
    then stay), and the **latest** search on that screen must have returned 0. A rejected input or an outage logs no
    search, so neither counts. With member and stay both attached, it is refused.
  - `deny_other` stays open, is always logged as an override, and needs a note of at least 20 characters after
    trimming.
  - The console offers only `deny_not_found` and `deny_other` while evidence is incomplete.
  - The scripted agent asks the member when it has nothing to search with, or several candidates, instead of denying.
- **Trade-off:** a length check can't judge a note, so `deny_other` can still close a case wrongly; those closes stay
  countable as overrides for review. A rule-based code against **complete** evidence is still an override with any
  non-empty note, because the owner's rule covers incomplete evidence only.
- **Result:** no catalog or hypothesis change, so no change-log entry. On the dev split, 0 of 102 scripted runs changed
  path. Existing rows are not rewritten: A-000010 stays closed as the audit record of the wrong denial.
- **What would change this decision:** override review (Milestone 7 metrics or UAT) showing `deny_other` is being used to
  get around the evidence rule, which would call for supervisor review of those closes.

## ADR-0051: how the "A as-is" variant will run (built in Milestone 10)
- **Context:** ADR-0018 pre-registered the variant; Milestone 5 builds the write path it replaces.
- **Options considered:** a configuration flag in the app; a separate implementation in the benchmark tooling.
- **Decision:** a separate `WritePath` implementation in `benchmarks/variants/a_as_is/` (Milestone 10): approval as
  a status flag, no duplicate check, no re-check, a fresh idempotency key per attempt, so a retry after
  `commit_then_lost` is a new request. The runner injects it into the scripted agent only against a disposable
  `loyalty_bench_*` database. Because a strictly sequential run lets the second D10 case see the first credit in the
  ledger, the runner interleaves D10 and S05 pairs (both investigated and approved before either executes), as two
  agents would. Reported next to arm A, excluded from H1–H6.
- **Trade-off:** the interleaving is a modelling choice; it is stated with the results.
- **Result:** a test now proves nothing in `app/` imports `benchmarks/`; Milestone 10 adds the test that no route,
  setting or profile can select the variant.
- **What would change this decision:** none planned; the variant exists only to measure what the write path prevents.

## ADR-0055: the Milestone 6 design and the owner's ten choices
- **Context:** Milestone 6 completes the write path (ADR-0044). The full reasoning, options and risks are in
  `docs/rfcs/RFC-0001-write-path-integrity.md`. The owner approved the plan on 2026-11-04.
- **Options considered:** per choice, in the RFC.
- **Decision (owner's choices):**
  - **D1:** execution always goes through the durable worker; the case page polls for status.
  - **D2:** an invalidated or expired approval returns the case to `Investigating`. It's never revived: a new request,
    approval and key follow. This replaces the Milestone 2 diagram's `Approved -> Pending approval`.
  - **D3:** the binding is HMAC-SHA256 with a key derived from `APP_SECRET_KEY`.
  - **D4:** split the database role now; the hash chain is deferred. The owner runs the `.env` and volume steps.
  - **D5:** an approval lasts 24 hours by wall clock, set per customer. This is an assumption, not a measurement.
  - **D6:** an agent or supervisor can reopen with a reason of at least 20 characters; only a supervisor if a credit was
    applied. Reopening grants no new power.
  - **D7:** a new administrator role controls the kill switch and publishing, and one administrator can publish. A
    read-only auditor role is added too.
  - **D8:** every arm's approval binds to the policy in force at checkout, chosen by the platform, even though arm A's
    checklist ignores it. D15 stays a defect in arm A's evaluator.
  - **D9:** changed evidence is detected at approve and execute; changed policy acts immediately.
  - **D10:** Milestone 6's branches may be pushed, opened as pull requests and merged with a merge commit when CI is
    green. This permission covers this milestone only.
  - **Also approved:** API-01 and API-02 move to Milestone 7, because item 6 of the spec's milestone order doesn't list
    an API and the console doesn't need one yet.
- **Trade-off:** per choice, in the RFC. The largest: the console's execute becomes asynchronous, and `.env` gains one
  password.
- **Result:** recorded as the work lands, in the later ADRs and `docs/verification-log.md`.
- **What would change this decision:** a real vendor's idempotency or lookup behaviour (the RFC's open questions), or a
  load test showing the queue on the primary database can't keep up (Milestone 12).

## ADR-0056: the eligibility engine has two clocks and is checked against the labeler on the dev split only
- **Context:** spec B.7 wants pure, typed, configurable rules. The reference labeler (`evaluations/labeler.py`, ADR-0029)
  computes ground truth from the same written policy, and a re-check before execution must see postings that landed after
  approval without changing whether the claim was on time.
- **Options considered:** share code between the engine and the labeler (less to write, but one bug would fool both);
  one "now" for every rule (simple, but a re-check months later would fail the claim window); read rule values from Python
  constants (they would drift from the policy files).
- **Decision:** `app/domain/eligibility.py` is written apart from the labeler, and a test proves neither imports the other.
  It takes `received_at_utc` (window, waiting period) and `as_of_utc` (which ledger and queue entries count). Rule values
  come from the policy version in force on the checkout date in the property's time zone, from `customer_config`. No
  policy, or more than one in force, returns `needs_escalation`: the engine never invents one. It adds
  `refresh_evidence` to the labeler's action vocabulary for stale evidence, which is a system state, not a case label.
  Arm A keeps its checklist (ADR-0044). The engine isn't called by the console until arm B (Milestone 7).
- **Trade-off:** two implementations of one policy to keep in step, which is the point. The differential test is limited
  to the dev split, so a mistake only held-out cases would reveal stays hidden until Milestone 10.
- **Result:** the two agree on every claimed stay and every case verdict in the dev split. The agreement was not taken on
  trust: 5 tests change one rule (waiting period, OTA, corporate rate, pending posting, earning rate) and require a
  disagreement. Every action in the labeler's vocabulary was reached except `request_info` at stay level, which the case
  verdict test covers. The validation, held-out and stress splits weren't opened.
- **What would change this decision:** a held-out disagreement in Milestone 10, which would be reported, not tuned away.

## ADR-0057: policies are stored per section, searched with an expression index, and published through checks
- **Context:** spec B.6 wants versions selected by business date, citations that open the exact excerpt, Postgres full-text
  search as the baseline and a controlled publishing workflow. Appendix B says chunks are stored with a `tsvector`.
- **Options considered:** a stored `tsvector` column (Appendix B's default); an expression GIN index; publishing without
  outcome checks, relying on review; running the golden outcomes through the labeler.
- **Decision:** one chunk per `##` section. A GIN **expression** index instead of a stored column: the search uses the same
  expression, and the model stays portable, so the migration-drift test keeps working on SQLite. This is a recorded
  change from Appendix B's default. Publishing checks the set of versions as it would stand: rule fields, the next
  version number, no gap or overlap in dates, and 14 hand-written dated outcomes in `config/policy-regression/`. A
  version that changes what an earlier date means is therefore refused until that file is changed in review. Two
  new roles: administrator (publishing) and auditor (read-only), with two demo accounts. Events with no case go to a
  new `system_events` table. The committed policy files are loaded at their stated status by the seed, and the
  images now carry `policies/`: fictional text, with no labels or personal data.
- **Trade-off:** the golden cases can't use the labeler, because the app may not import it (ADR-0029), so they are a
  third, small statement of the rules to keep in step. Front matter and prose aren't checked against each other.
- **Result:** tests cover selection on the change-over days, exact excerpts, drafts never applying, each refusal, escaping,
  and who can do what. On real Postgres: stemming, ranking, hostile query text, the plan using the index, and two
  administrators publishing one draft with exactly one success. Limits: `docs/retrieval.md`.
- **What would change this decision:** a controlled comparison in which hybrid search beats full-text (Milestone 15), or a
  real customer whose governance requires a second person to publish.

## ADR-0058: the app's database role is split, so the app can't rewrite audit history
- **Context:** spec B.10 wants an append-only database role and honest guarantees. `loyalty_app` owned the database and ran
  migrations, and an owner can always change its own tables. The close rules read `case_events`, so the app still needs
  to read it. An app holding migration rights in its environment would defeat the split.
- **Options considered:** a trigger (the owner can disable it, and the app was the owner); an ORM guard (protects nothing);
  a hash chain alone (whoever can rewrite the table can recompute it); splitting the role, chosen by the owner (D4).
- **Decision:** `loyalty_owner` owns the objects and runs migrations; `loyalty_app` runs the app and worker, with INSERT and
  SELECT on `case_events` and `system_events`, and no right to change `alembic_version`. A one-shot `migrate` service is the
  only service holding the owner's password, which replaces migrate-on-start from ADR-0052. `app-owner.sql` is one
  idempotent script used by a new volume, `stack.ps1 -Action up` on an old one, and CI. It takes the audit rights back at
  the end, because its grants cover every table. The state machine gains the transitions in ADR-0055, and reopening
  (`cases.reopen`) keeps the old events and copies the previous resolution into `case_reopened`.
- **What it guarantees:** the app role, or a compromise of it, can't update, delete or truncate audit events, alter or drop
  those tables, or change the schema. Tests prove this by connecting as the real role.
- **What it does not guarantee:** the owner role, a superuser and anyone with the backups can still rewrite history, and a
  test records that. It doesn't apply on offline SQLite. Timestamps come from the writer's clock. Approval and job rows stay
  mutable; events record their changes. **It isn't tamper-proof, and nothing here claims it is.**
- **Trade-off:** one more `.env` password and one upgrade step on existing volumes. `app.seed` no longer migrates a database
  that is behind, because the runtime role can't: `stack.ps1 -Action migrate` does.
- **Result:** real-Postgres tests as the runtime role; the compose check rebuilds the old single-role state and upgrades it.
  The close rules from ADR-0054 now also run on real Postgres.
- **What would change this decision:** a real customer needing evidence beyond this role, which would mean anchoring a hash
  chain outside the database, or a separate audit store.
