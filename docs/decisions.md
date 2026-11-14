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
- **Update (2026-11-05):** the upgrade failed on the owner's real Milestone 5 volume: `loyalty_app` lost `CONNECT`, because
  it had owned the database, so its only right was the owner's own, and the change of owner moved that. The compose check
  missed it because it faked the old state from a newer volume and checked table rights, not a login. `app-owner.sql` now
  grants `CONNECT` back; `scripts/upgrade_check_m5.ps1` builds a volume with the real Milestone 5 code and upgrades it, and
  runs in the compose check. CI repeats the Milestone 5 ownership on every pull request and asserts the state is faithful
  before upgrading it. **The lesson: a faked old state proves only what the fake contains; build it with the old code, and
  test by logging in.** `/readyz` now logs why, masked. A worker that can't reach the database reports unhealthy and backs off.
- **What would change this decision:** a real customer needing evidence beyond this role, which would mean anchoring a hash
  chain outside the database, or a separate audit store.

## ADR-0059: an approval is an HMAC over the exact action, and any change ends it
- **Context:** an approval was a status flag (D11, TD-12). Spec B.10 binds it to member, stay, amount, policy version,
  evidence snapshot, approver and expiry. The re-check must not quietly fix arm A's defects (ADR-0044). The owner chose a
  keyed hash (D3), a 24-hour expiry (D5), and detecting changed evidence at approve and execute (D9).
- **Options considered:** per choice in RFC-0001. For the evidence hash: every field the app holds (an unrelated stay's
  posting would end an approval); only the facts about this stay that the arm actually read (chosen).
- **Decision:** a request stores its evidence hash, the policy versions in force on the checkout date, and that date.
  Approving re-reads the evidence through the arm's own evaluator, then locks the case and compares under the lock; a
  change ends the request instead of approving it. The approval stores its expiry and an HMAC over 11 fields, with a key
  derived from `APP_SECRET_KEY`. Executing checks the HMAC and expiry first, then re-reads and compares again. Publishing
  ends affected requests in its own transaction. Ended requests stay as they are; the case goes to `Investigating`, and a
  new request gets a new approval and a new key. Each case's simulated read time, `sim_now_utc`, can only be moved by tests
  and the benchmark, which lets a re-check see a posting that landed after the claim.
- **Trade-off:** a re-check costs about 3 more reads at approve and at execute. Rotating `APP_SECRET_KEY` ends every open
  approval, which fails safe. The HMAC stops someone who can write to the database but lacks the secret; it doesn't stop
  someone who has both.
- **Result:** every bound field changes the binding; editing any of them in the database ends the approval with nothing
  submitted; pre-Milestone-6 approvals must be approved again; the expiry boundary holds; a planted late posting (D11)
  stops execution on the real mock API; an unrelated stay's posting doesn't. On real Postgres: publishing ends affected
  approvals atomically, a publish that fails part way changes nothing, and publish racing approve ends consistent. While
  writing that race test I found `decide` wrote without a lock after its reads, so a publish could be overwritten; it now
  locks and re-checks first.
- **What would change this decision:** a real platform pushing change events, which would allow ending approvals at once
  instead of at the next approve or execute (D9).

## ADR-0060: a durable job queue in Postgres, at least once, with leases on the database's clock
- **Context:** spec B.12 and Appendix B want leases, heartbeats, recovery, bounded retries, dead jobs, duplicate prevention,
  graceful shutdown and correlation IDs, with no in-memory work. Appendix B names `FOR UPDATE SKIP LOCKED`. The owner chose
  to route all execution through it (D1).
- **Options considered:** an external queue (a second system to keep consistent with Postgres, which needs an outbox: Stage
  10); a task library (a dependency hiding the very behaviour this stage must prove); a table in the app's own database.
- **Decision:** the `jobs` table and `app/services/jobs.py`. It enqueues in the caller's transaction, so a job commits or
  rolls back with the state change that needs it. A partial unique index allows one active job per kind and case. Leases
  use the database's clock, so workers with different clocks agree. Each claim gets a new token, so a worker that lost its
  lease can record nothing. Attempts are counted at claim, so a crash uses one. After `max_attempts` a job goes dead and
  stays visible, until a person requeues it with `python -m app.worker --requeue`. `Defer` waits without using an attempt.
  A signal stops claiming and lets the job in hand finish, and `stop_grace_period` allows for that. A hard kill is recovered
  through the lease.
- **Failure semantics:** **at least once.** A job can run twice, because a worker can die after doing the work and before
  recording it. So every handler must be safe to repeat. This queue doesn't provide exactly-once effects and doesn't claim
  to; the write path gets its safety from the state machine and the idempotency key.
- **Trade-off:** the queue shares the primary database, so its limit is that database's write capacity (estimates in
  `docs/scaling-and-limits.md`, measured in Milestone 12). Workers poll once a second, so a job can wait about a second.
  Timestamps are text, compared as text, which works only because they all have one format. Dead jobs are listed by a
  command, with alerts in Milestone 12.
- **Result:** on SQLite with a test clock: order, due times, backoff, bounds, `Defer`, lost-lease writes refused. On real
  Postgres as the runtime role: 8 workers claim 50 jobs each exactly once, `SKIP LOCKED` doesn't wait, 20 concurrent enqueues
  add one, a real process killed mid-job is recovered, a heartbeat keeps a slow job. The compose check sends a real SIGTERM
  and checks exit code 0. Found while building: the SQLite driver's savepoints released as commits, so a rollback didn't
  undo a job; the engine now uses SQLAlchemy's documented recipe.
- **What would change this decision:** a load test showing the queue limits the primary database (Milestone 12), or a need for
  fan-out across services (Stage 10).

## ADR-0061: execution goes through the worker in four steps, with one live credit per stay and a kill switch
- **Context:** the thin write path (ADR-0044) ran in the web request, with no lock across executes (TD-13). RFC-0001 lists
  seven faults to fix. The owner chose execution through the worker (D1) and a database-backed switch (D7).
- **Options considered:** per topic in RFC-0001. For stopping two approvals racing on one stay: a re-check under the lock
  alone (a bug in the check means two credits); a partial unique index behind the check (chosen). For the switch: an
  environment variable (needs a restart, and web and worker could disagree); a database row (chosen).
- **Decision:** `execute` has four steps, and no lock is held across a call to a customer system. (1) Reads: the stored
  approval, the duplicate check, the arm's re-check. (2) Claim: lock the case, re-check, record the attempt and `Executing`,
  commit. From here, a process death means an unknown outcome. (3) A last look at the switch, then submit with the key. (4)
  Lock and record. The console only queues the job. A job finding a case in `Executing`, or flagged recovered, moves it to
  `Execution unknown` and reconciles: it never resubmits. Outcomes follow RFC-0001's table: an unreadable `200` counts as
  may-have-applied (fault 1); a `409` or a different record escalates and keeps the stay blocked (faults 2, 3); "not found"
  needs 2 lookups and a settle window, an assumed 60 seconds (fault 4). After a confirmed absence the job retries with the
  same key, up to 3 submissions per approval, then leaves it `Approved` for a person. The sweep queues stranded cases but
  never restarts a dead job. The scripted agent still calls `execute` directly: same code, no worker process.
- **What the kill switch guarantees:** once turning it off has committed, no new claim passes. Queued jobs wait, using no
  attempts. Reads and reconciliation keep working. If the row is missing, adjustments stop. **What it doesn't:** a worker past
  its last check can land a submission, at most one per worker. The test measures this rather than assuming none.
- **Trade-off:** the page polls, and adds about a second of queue wait. A posting landing between the re-check and the submit
  isn't caught, and a real platform's late arrival after the settle window could still produce a second credit under a new key
  (RFC-0001, risks). Exactly-once needs the platform's cooperation, and this doesn't pretend otherwise.
- **Result:** on real Postgres and over the real adapter: 10 concurrent executes credit once; two approvals racing for a stay
  credit once, even with the duplicate check switched off; timeout-after-commit reconciles with one credit and no resubmit; a
  failure before the upstream commit leaves nothing and the same key then applies once; a real process killed before and
  after the submit recovers with one credit; 6 jobs and 3 workers with the switch thrown mid-run end with each stay credited
  exactly once. **Found by the first real-Postgres run, invisible on SQLite:** `record()` deadlocked 11 of 12 threads, because
  an insert referencing a case holds a key-share lock that `FOR UPDATE` conflicts with (now `FOR NO KEY UPDATE`), and the unique
  index's refusal surfaced during a flush, outside the `try` (widened).
- **What would change this decision:** a real platform's measured lookup lag and key retention (swap guide), or a load test.

## ADR-0062: Milestone 7's three choices, and the owner's standing instructions
- **Context:** Milestone 7 builds arm B. Three design points needed the owner's call, and they touch fairness: the mock API has
  no name search, policy section 6 sets the supervisor limit per case, and the app may not read discovery data. On 2026-11-05
  the owner approved the recommended choices, "as long as they don't weaken safety or the benchmark's fairness", and gave
  standing instructions for Milestones 7-20 (`CLAUDE.md`).
- **Options considered and decisions:**
  - **Name search.** Without it a mistyped member number can't produce candidates, so D13 and D18 couldn't get their fair fix
    (F9). Options: fuzzy matching only over email and phone; an additive `lastName` filter on the mock API's member search.
    **Chosen: the additive filter, contract 1.1.0.** Arm A's screens don't call it, so its D13 and D18 stay. A candidate still
    needs two matching identifiers before it counts as the member, so a name match alone never moves points.
  - **Per-case supervisor limit.** A case per stay would be simplest, but splitting a request could slip under the 20,000
    point limit. Options: several credits inside one case (changes the proven write path); one case per stay, linked as a
    group. **Chosen: one case per stay, with `group_ref`,** and the limit is checked on the group's total when any request in
    it is made. The write path doesn't change. A group over the limit escalates as a whole.
  - **Day-one page.** The app can't import the analysis or read the history. **Chosen: `discovery_analysis` exports aggregate counts
    and charts into `app/web/static/day-one/`; a test checks they trace to the committed report.** No per-case rows and no labels.
    Supervisors, administrators and auditors can open it; agents don't need it for casework.
- **Trade-off:** the group limit adds one rule outside the write path, so it needs its own concurrency test: two agents in one
  group at once mustn't both pass. The name filter is a contract change a real vendor might not offer (swap guide).
- **Result:** recorded as Milestone 7 lands.
- **What would change this decision:** a real platform with no name search (then D13 and D18 fall back to asking), or a customer
  whose limit is per stay.

## ADR-0063: A fence around arm A, recorded before arm B
- **Context:** Arm B's fixes touch shared code (`cases.py`, the mock API, the port). Any change that leaks into arm A would
  move the baseline after pre-registration (F9), and a scored comparison at Milestone 10 wouldn't show why.
- **Options considered:** a code-review rule; hashes of arm A's source only; a behaviour snapshot only; both. Hashes miss a
  change in shared code. A snapshot misses a change that dev cases happen not to reach.
- **Decision:** both, in `tests/test_arm_a_fence.py`: SHA-256 of `app/arms/legacy/`, `config/legacy/` and the scripted agent, and
  what the scripted agent does with all 100 dev cases (path, status, resolution, steps, points). Recorded from commit `58edefc`,
  before any Milestone 7 code. It stores no score and reads no label.
- **Other choices here:** the name filter is `familyName`, the customer's own field name in the mock API's shape, not the
  `lastName` ADR-0062 mentions. Same filter, contract 1.1.0. The arm is fixed at intake, and arm B's routing is its own
  (`app/arms/conventional/signals.py`), so D20 stays in arm A.
- **Trade-off:** a deliberate fix to arm A must regenerate the file and log the reason in the catalog's change log. That's the point.
- **Result:** passes on arm A as it stood, and again after the plumbing PR (verification log, Milestone 7).
- **What would change this decision:** an owner-approved change to arm A, treated as a new experiment (F9).

## ADR-0064: How arm B is built
- **Context:** Arm B is the non-AI fix for every defect that doesn't need AI (F9), and the manual fallback. It must be good enough that
  any gain arm C shows is really AI's, and it must use the same write path as arm A.
- **Options considered:** (1) run the investigation inside the web request; (2) run it through the durable worker; (3) make the agent
  click through steps with better screens. Option 1 ties a page to several customer calls. Option 3 leaves D14 unfixed.
- **Decision:** option 2. `POST /cases/{id}/investigate` queues a job, unique per case, and the page polls. The job reads through the port,
  asks the eligibility engine, and stores one consolidated evidence snapshot and one `recommendations` row. Pure logic is in
  `app/arms/conventional/`; storage is in `app/services/conventional.py`; `ConventionalReview` re-runs the same code for the re-check.
- **Rules that protect safety and fairness:**
  - Agents can't type an amount. The only way to request a credit is the engine's own `adjust` result.
  - Closing against the engine needs a reason of at least 20 characters and is logged as an override, in `feedback` and in the event.
  - Two identifiers before a candidate counts as the member. A stay on someone else's profile stores and shows nothing about it.
  - A member's reply is stored as evidence. It can select records and fill a blank channel, and nothing else.
  - `scope_cleared` lets a person say they read a multi-issue or non-English message. It's logged, and it changes no amount.
  - Arm B's scripted agent never goes against the engine and reads no label.
- **Group limit (ADR-0062):** `request_adjustment` locks every case in the group in ID order, then checks the group's total. Over the limit,
  open requests are invalidated and the whole group escalates. A case with no group locks itself, so a double click makes one request.
- **Trade-off:** a worker must be running for arm B to work. If the job dies, the page says why and offers a retry. Arm B also makes more
  reads per case than arm A, including a name search on every investigation, which a real platform might rate-limit (swap guide).
- **Result:** per-defect tests on dev (`tests/test_arm_b_defects.py`), console and safety tests (`tests/test_arm_b_console.py`), real locks
  (`tests/test_arm_b_postgres.py`). No aggregate score was computed or recorded (ADR-0048).
- **What would change this decision:** a platform with a single consolidated claim-lookup call (fewer reads), or a customer who wants the
  agent to see the evidence before the engine's result, to reduce automation bias.

## ADR-0065: The JSON API is a thin layer over the same services
- **Context:** API-01 and API-02 moved here from Milestone 6. Machine identity isn't until Milestone 9, and a second set of rules in an API layer would be
  a second place for a permission to go wrong.
- **Options considered:** (1) a separate API with its own checks; (2) bearer tokens now; (3) the console's session, calling the same services.
- **Decision:** option 3. `/api/v1` calls `app.services`, with the session cookie and an `X-CSRF-Token` header for changes. Errors are RFC 9457 problem
  documents from a custom route class, so nothing in this router falls through to the console's HTML errors. Request bodies refuse unknown fields, so
  `points` in a body is an error. Lists use an opaque cursor. The contract is committed at `app/api/contracts/openapi-v1.json` and tested. Starting an
  investigation twice returns the same job. FastAPI 0.162 keeps included routers in a wrapper, so the contract is built from the router, not from `app.routes`.
- **Metrics and the day-one page:** counts only, with scripted runs kept apart from people, for supervisors, administrators and auditors. The day-one files sit
  outside `/static`, which needs no sign-in.
- **Trade-off:** no other system can call the API until Milestone 9 (TD-32). Arm A's manual evidence steps aren't in the API: arm A is the baseline, and
  nothing needs them there.
- **Result:** `tests/test_api.py`, `tests/test_metrics_and_day_one.py`. The contract test fails on any undeclared change.
- **What would change this decision:** a customer's gateway that requires a different auth scheme or error format.

## ADR-0066: Arm C is arm B plus a model that can't decide
- **Context:** Milestone 8 adds the AI layer. RFC-0002 holds the design. A model must add reading, and must never touch identity, eligibility, the amount, permissions, approval or execution.
- **Options considered:** replacing arm B's investigation with the loop; running arm B first and giving the loop what's left; summarizing only.
- **Decision:** arm B runs first, always, and is the fallback. The loop reads through five narrow tools and hands back a `Proposal` with no field for an amount. Code acts on only three things it says, each checked: which of the member's own stays the message means, that a person needn't read a multi-issue or non-English message first, and the text shown to staff. The engine then reads again. Arm C's re-check doesn't ask the model.
- **Model:** Claude Haiku 5.5, effort `low`, pinned and listed in `config/ai/hg-demo.yaml`. An unlisted or deprecated model fails safe to arm B's result. The app's web process has no key: only the worker calls the model.
- **Trade-off:** arm C always pays for arm B's reads and at least one model turn, so it can't be cheaper than arm B. A model that says the message needs no person gets past arm B's gate, with engine, supervisor and re-check still in place. A linked case doesn't run the model again, so it has no AI text.
- **Result:** every stop condition and injection test passes on scripted models (`tests/test_ai_loop.py`, `tests/test_arm_c.py`). **No real model has run:** the live smoke test is NOT RUN until the owner approves it.
- **What would change this decision:** Milestone 10 showing that the loop adds nothing over arm B on the defects it targets. Then ship arm B and drop the loop.

## ADR-0067: An exact confirmation number on the profile is an identifier, for arm B too
- **Context:** The catalog predicted that D18's married names need a model. Writing RFC-0002 showed they don't: its own detection method is "name differs, other identifiers match", and an exact email plus an exact confirmation number on that profile are two identifiers code can check. F9 says arm B gets a fair fix for everything that doesn't need AI.
- **Options considered:** leave it for arm C, as predicted (unfair: it would credit AI with something rules can do); let the model confirm identity (forbidden); add the identifier to the shared code.
- **Decision:** add it to `app/arms/conventional/identity.py`. Exact only: a near match isn't an identifier. It never counts alone, and someone whose only match is a quoted stay isn't shown as a candidate (S03).
- **Trade-off:** a number and a confirmation can both be known to someone else, so it's a little weaker than number plus email. The credit can only go to the profile that holds the stay, and a supervisor still approves.
- **Result:** dev's D18 cases reach the right member on arm B (`tests/test_arm_b_defects.py`). The catalog's prediction stands as written: if this holds at Milestone 10, it's a prediction missed in arm B's favour, and it's reported that way (F8).
- **What would change this decision:** a customer's identity policy that wants a personal identifier in every pair.

## ADR-0068: Documents are evidence only, and routing stays on rules
- **Context:** D22 needs a non-AI baseline before Milestone 10, or arm B is unfairly weak (TD-31). Appendix I asks whether a classifier beats rules for routing.
- **Decision (documents):** arm B reads a PDF's text layer and a plain email with rules; arm C can read images through the provider. A value can point at a stay and nothing more: it isn't an identifier, it never changes a record, and a document that disagrees with the record sends the case to a person when it's the only link. Type, size and content checks run before parsing. Standing is `matches`, `differs` or `format_only`, never a percentage.
- **Limit:** Tesseract isn't installed, so **OCR on images is blocked with that prerequisite.** The catalog says "clean folios via OCR"; these PDFs have a text layer, so the fair fix works without it. A scanned PDF has no text layer and goes to a person. The mock can't see, and says so by finding nothing.
- **Decision (routing):** the rule in `config/routing/thresholds.yaml` was committed first (`455fd0b`). Rules and TF-IDF + logistic regression both scored 1.0 macro-F1 on validation, so the gain is 0.0 and **rules stay.**
- **Why that isn't a win:** validation has one case in each minority class, and shares a phrase bank with dev. It can't tell the methods apart. The drift check found that neither recognises injection attempts (0 of 8), and safety doesn't rest on that. The dataset also has no out-of-scope-only or complaint-only requests, so those classes aren't measured (`docs/model-card-routing.md`).
- **Result:** `tests/test_extraction.py`, `tests/test_routing_baseline.py`. Closes TD-31. Field-level scoring is Milestone 10.
- **What would change this decision:** held-out or pilot data showing that rules miss real wording.

## ADR-0069: Security hardening: scope, identity, limits, and what we reused
- **Context:** Milestone 9. The console trusted that one deployment means one customer, had no rate limits, and had no enterprise sign-in or recovery.
- **Customer scope:** options were one database per customer (strongest, and simplest to reason about); row scope in the app; Postgres row-level security. **Chosen: row scope in the app, tested,** because a real deployment here runs one customer per stack and this is the second layer. **It found a real bug on the first run:** the approvals list showed every customer's requests. RLS can be added later: it isn't needed for what's tested.
- **OIDC:** options were Authlib, PyJWT plus our own flow, or a gateway in front. **Chosen: PyJWT for token checks, with a small authorization-code flow.** No cryptography of our own. Roles come from groups on every sign-in, and no mapped group means no access. An account deactivated here stays out. Verified against a real Keycloak in a real browser, 7 of 7 (`security/evidence/`).
- **Rate limits:** in the database rather than in process memory, so that every process shares them and a restart doesn't reset them. Costs a write per request; Milestone 12 measures that.
- **Machine tokens:** read-only by having no CSRF value, short-lived, stored as hashes, and shown as an auditor in the log.
- **Retention:** removes personal data and keeps the audit trail and credits. Backups aren't touched, and that's stated. Legal hold beats both retention and erasure.
- **Reuse (REUSE-08):** `hotel-ai-platform`'s input-blocking patterns and PII library: **not adopted.** Its model is to block at the door; here, an attack has nothing to act on, and spec C.7 says not to rely on a detector. A false block would also cost arm B a real claim. Its shared red-team corpus: **adopted,** copied at commit `3879d00`, and checked on business effects. Its own warning applies, because the cases were written beside its patterns.
- **Trade-off:** tests are the only thing enforcing scope, so a new query can forget it. The route-walking test covers access, but not what a query returns.
- **Result:** `tests/test_security_authz.py`, `tests/test_oidc.py`, `tests/test_red_team.py`, `tests/test_red_team_shared_corpus.py`; `security/` holds the rest.
- **What would change this decision:** more than one customer sharing a deployment for real. Then add RLS, and test it on the actual connection (spec C.5).

## ADR-0070: How the benchmark measures, and what happens after a stopped credit
- **Context:** Milestone 10. The pre-registered rules decide the verdicts. What's left is how to measure honestly.
- **Options considered:** running on the Compose stack, on disposable Postgres, or in one process on disposable SQLite. An LLM judge for explanations, or none. After the re-check stops a credit: scripts as written for every arm, a second look for every arm, or a second look for arm B alone.
- **Decision:** SQLite per run, with arms A and B confirmed case for case on real Postgres (`tests/test_benchmark_postgres.py`). No judge: explanation quality stays unmeasured. **Scripts as written, for every arm, as the owner decided.** Arm A's script follows its checklist and doesn't act like a careful person, and `docs/hypotheses.md` credits D11 to neither arm, so arm B doesn't get a step arm A doesn't. Verdicts come from code applying the pre-registered rules.
- **Fairness guards:** a freeze that hashes everything that can change an arm; held-out refuses to start otherwise. A hard cap in code, checked before each call. Mock can't decide H2 to H5. Every slice where A or B beats C is generated.
- **Trade-off:** every arm fails D11 on case success though its ledger is right. And the simulation has no person who works an escalation, so **arm B's handoffs count as un-credited: H3's verdict rests on that.** It stands, because that's the registered definition. If a person works every escalation correctly, H3 wouldn't be supported, and C's case success is 78 against B's 77 of 80.
- **Result:** H1, H2, H3, H5, H6 supported; H4 not supported; H7 not tested. Live spend $1.83 of $5. `benchmarks/reports/heldout/`.
- **A reading of the owner's stop condition:** the owner asked to stop on "a result that looks like a bug in scoring". A pre-freeze bug with a known cause and a test was fixed and flagged, since finding those is what dev is for. H3's dependence isn't a bug: the code follows the definition. It's reported at the top of every summary, for the owner to weigh.
- **What would change this decision:** a pilot with real people working escalations; a catalog or hypothesis change, logged as a new experiment (F9).

## ADR-0071: Protocols at the edge: MCP, A2A and AG-UI over the same services
- **Context:** Milestone 11 (spec Part G; `docs/rfcs/RFC-0004-protocols.md`). Three optional interfaces for callers outside our code: AI clients (MCP), another team's agent (A2A), a live frontend (AG-UI). ADR-0023 and ADR-0025 already say MCP is read-only and the A2A pair is a lab.
- **Options considered:** code inside `app/`, a `protocols/` package, or a separate repo. For caller identity: the M9 opaque machine tokens, a JWT issuer of our own, or Keycloak access tokens checked as a resource server. For A2A task state: the SDK's memory store, its SQL store, or our own table. For AG-UI: push events from the loop, or build them from stored rows.
- **Decision:** a `protocols/` package with a flag and a start command per protocol, calling the existing services. **Keycloak access tokens**, checked for issuer, audience, expiry and scope, mapped to the existing `Identity`, because MCP's authorization spec requires audience checks and protected-resource metadata, which opaque tokens can't give. An `a2a_tasks` table (migration `0011`). AG-UI events built from `ai_runs`, `ai_steps` and `case_events`. Pins: MCP 2026-07-28 (`mcp` 2.3), A2A 1.0 (`a2a-sdk` 1.3), AG-UI 1.0 (`ag-ui-protocol` 1.0), in an optional dependency group.
- **Trade-off:** two token types (opaque for REST, JWT for protocols) until REST moves to JWTs too. Keycloak must be running for the protocol services outside tests. AG-UI polls the database while a run is active rather than pushing.
- **Result (2026-11-12):** same-SDK tests pass for all three; tokens checked against a real Keycloak (9 of 9). Independent peers: the MCP Inspector CLI 2.14.0 passed (it negotiated 2025-11-25, so 2026-07-28 has same-SDK tests only); `@ag-ui/client` 1.0.4 passed 4 runs; the A2A TCK is verified with limitations (ADR-0072). Details: `docs/protocol-test-results.md`.
- **What would change this decision:** a client that already runs an API gateway issuing tokens (then the gateway is the issuer, and our verifier only changes configuration); AG-UI 1.1 adding stream resumption (then a reconnect could resume instead of re-watching); real volume where per-run polling costs too much (then a notify channel, Postgres `LISTEN`/`NOTIFY` first).

## ADR-0072: "Verified with limitations" for PROTO-04, the A2A TCK result
- **Context:** the A2A TCK (commit `70f6f73`) ran against the specialist on 2026-11-12: 45 of the 47 required (MUST)
  checks that ran pass. The 2 failures (DM-ART-001, DM-MSG-001) are TCK scenarios keyed on `messageId` prefixes, which
  the specialist rejects by design because it accepts only an evidence request. The TCK can't send tokens at that
  commit, so it didn't test authentication. The status labels had no way to say "verified, but with these limits".
- **Options considered:** "Implemented and verified" with the limits only in the text (a reader of the score sees a
  clean pass); "Implemented but unverified" until a TCK version sends tokens (understates 45 passing checks and our own
  auth tests); a qualified status that still counts as done but must carry its limits.
- **Decision (owner, 2026-11-12):** PROTO-04 is "Implemented and verified: with limitations". A row with that status
  must list its limitations (`**Limitations:**` in the Implementation cell, checked by `tests/test_matrix_scores.py`),
  and the score table names every such row. Wherever PROTO-04's status appears (the matrix, the test results, the
  Protocol Lab page, the status and handoff documents, the portfolio coverage map, and any later portfolio text), the
  three limits appear with it. Authentication is covered by `tests/test_a2a.py` and the real-Keycloak run instead.
- **Tradeoff:** one more status form to keep honest, against a score that would otherwise hide a partial result.
- **Result:** PROTO-04's row and every place its status appears; `scripts/matrix_scores.py` prints "Verified with
  limitations: PROTO-04" under the score table; `docs/known-limitations.md` carries the rule for portfolio text.
- **What would change this decision:** a TCK release that sends bearer tokens, or a way to run its scenario tests
  against a separate test agent. If both pass, PROTO-04 becomes plain "Implemented and verified".

## ADR-0073: One public issuer for host and containers, keys fetched by service name (TD-52)
- **Context:** the Milestone 11 protocol services had start commands but no Compose services. In Compose, Keycloak's
  issuer differed by who asked: a host client got `iss` = `http://127.0.0.1:8090/...`, a container
  `http://keycloak:8080/...`, so a token from one side failed the issuer check on the other (TD-52).
- **Options considered:** (1) a hostname both sides resolve, such as `host.docker.internal` (Docker Desktop adds it to
  the Windows hosts file, Linux CI doesn't, and it reaches a 127.0.0.1-bound port differently per platform); (2) put
  every client inside Compose (the owner's own tools and the interop peers run on the host); (3) one public issuer,
  Keycloak `--hostname=http://127.0.0.1:<port>` with `--hostname-backchannel-dynamic=true`, and a separate fetch URL
  for documents and keys.
- **Decision:** option 3. Tokens always name the public issuer. Containers fetch discovery and keys from
  `PROTOCOL_TOKEN_FETCH_URL` / `OIDC_FETCH_URL` (`http://keycloak:8080/realms/hotel`) and still check `iss` against
  the public issuer. Documents and keys come only from that one base (`app.outbound.check_url`), so a discovery
  document can't point us anywhere else. The shared code is `app/adapters/oidc_discovery.py`, which also pays TD-51:
  console sign-in and the protocol services now use one helper.
- **Tradeoff:** two URLs per provider to configure in containers, against one that silently differs by caller.
- **Result:** `scripts\labs_check.ps1` against a real Keycloak 26.4.2, 10 of 10: a token requested inside a container
  names the same issuer as one from the host, and MCP and A2A in containers accept both (verification log, M12).
  Found on the way: MCP's DNS-rebinding guard allowed the bind address (`0.0.0.0:8030` in a container), so every
  call got 421; it now allows the resource URL's host, with a test.
- **What would change this decision:** a real identity provider behind one TLS hostname that both sides resolve (a
  hosted deployment): then the fetch URLs stay empty.

## ADR-0074: Multi-stage images, a protocols target, and Compose profiles
- **Context:** spec F.2 asks for non-root containers with limits and the profiles demo, test, enterprise-identity and
  labs. The images had uv in the runtime layer and no healthcheck; there were no profiles.
- **Options considered:** separate Compose files per profile (the earlier `docker-compose.oidc.yml` way: more files,
  and `-f` combinations to remember); one file with `profiles:`; a separate Dockerfile for the protocol services.
- **Decision:** one Compose file with profiles; services without one are the default stack, so the quickstart is
  unchanged. `Dockerfile.app` has dependency stages (uv only there), a `protocols` target and the core `app` target
  last (the default). Every service drops all Linux capabilities and privilege escalation; only the Postgres
  containers add back the five their entrypoint needs. `test-db` keeps its data in memory. Keycloak refuses to start
  without its admin password at start time, because Compose interpolates every service even outside the active
  profiles, so a required variable there would have stopped the default stack (found by `docker compose config`).
- **Tradeoff:** a longer Compose file and Keycloak defined twice (`docker-compose.oidc.yml` stays for
  `scripts\oidc_check.ps1`), against one place to read the whole system.
- **Result:** `tests/test_compose.py` (profiles, hardening, image stages); the compose check also checks for no `uv`
  and no protocol code in the core images; `scripts\labs_check.ps1` runs the labs profile.
- **What would change this decision:** Kubernetes or a managed container service as the main target: then the
  profiles become separate deployments, and the image targets carry over as they are.

## ADR-0075: Environment files, and no default credentials in hosted profiles
- **Context:** spec F.2 asks for separate local, staging and production configurations, and production checks: no
  debug mode and no default credentials. Preflight already refused debug and local databases in hosted profiles.
- **Options considered:** one `.env` per environment with secrets in it (secrets in more files); settings only in
  the hosting platform (nothing to review in the repo); non-secret settings per environment in the repo, secrets only
  in the platform's store, and preflight checks on both.
- **Decision:** `config/environments/{local,staging,production}.env` hold non-secret settings only (a test refuses a
  secret name there). Hosted profiles (`staging`, `approved`) refuse any secret that is a known default, a template
  or test value, or shorter than 16 characters, by name only. `approved` refuses `DEMO_USER_PASSWORD` (no shared demo
  accounts). Production starts with adjustment execution off: rollout stage 4 is a decision, not a default (F.3).
- **Tradeoff:** a heuristic list of default values can miss a weak secret it doesn't know; length and the platform's
  own generation cover the rest.
- **Result:** `tests/test_preflight.py` (six refusals, a pass, the laptop exemption, the environment files).
- **What would change this decision:** a secrets manager that generates and rotates every value (AWS Secrets
  Manager in the Terraform path): then the check becomes "the value is a reference", not a string test.

## ADR-0076: CI runs once per change, and the same pipeline runs locally
- **Context:** the repository is private, and GitHub Free includes about 2,000 Linux minutes a month (shown as $12).
  On 2026-11-13 this repository had used about 1,572 minutes since 2026-11-01 (90 runs; job times rounded up per job,
  from the Actions API; the billing page wasn't read). 632 of them were push runs: every branch push ran CI, and the
  pull request ran it again. The owner set a 70% stop line.
- **Options considered:** keep the triggers and wait for the monthly reset (no merges for two weeks); make the
  repository public (free minutes; the owner's decision, not yet made); run CI once per change and move the rest of
  the checking to this machine.
- **Decision (owner, 2026-11-13):** CI runs on pull requests into `main` and pushes to `main` only. Every step also
  runs locally in `scripts\ci_local.ps1` (`make ci`), which is run before every push; a pull request is opened only
  when it passes. The Postgres job's setup moved into `scripts/ci_postgres_setup.sh`, used by both, so they can't
  drift. Milestone 12 uses fewer, larger pull requests, and reports minutes per run.
- **Tradeoff:** a branch gets no remote check until its pull request opens, and the local run is slow on this machine
  (the offline suite took 64 minutes under load on 2026-11-13, against about 3 on CI).
- **Result:** the trigger change and `scripts\ci_local.ps1`; minutes per run in the verification log.
- **What would change this decision:** a public repository (minutes are free), or a paid plan.
- **Superseded the same day (owner, 2026-11-13):** the repository was made public at 22:07 UTC, `main` at
  `f76c1d6`, so standard GitHub-hosted runners cost no minutes. CI is back to its earlier triggers (every pull
  request; pushes to `main` and `ci/**`), the 70% stop line is removed, and pull requests go back to their normal size.
  `scripts\ci_local.ps1` and the shared Postgres setup stay, as a way to check before pushing.

## ADR-0077: Traces and logs: OpenTelemetry, one scrubbing exporter, GenAI names in one module
- **Context:** spec F.1 asks for structured logs with correlation IDs, OpenTelemetry traces with context propagation,
  and sensitive-data filtering; L2 asks to use the GenAI conventions if usable, without prompt or response content.
  Two facts shaped it. (1) The customer-API adapter looks members up by email and family name **in the query
  string**, and the HTTP instrumentations record full URLs; the mock API's uvicorn access log already printed them.
  (2) The GenAI conventions moved from the core semantic-conventions repository (v1.42.0) to
  `open-telemetry/semantic-conventions-genai`, whose pages read on 2026-11-13 say **Status: Development**, and which
  has no release yet.
- **Options considered:** a vendor agent or LLM-observability SDK (L3 decides those in PR 7); OpenTelemetry with the
  instrumentations' own hooks to drop attributes (they can add attributes, not remove them); OpenTelemetry with one
  exporter wrapper that scrubs every span before it leaves the process.
- **Decision:** OpenTelemetry SDK 1.45.2 with the FastAPI and httpx instrumentations 0.66b2, OTLP/HTTP export only
  when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. Every span leaves through `ScrubbingExporter`
  (`app/observability/tracing.py`): URL query strings removed, GenAI content attributes dropped, and every string
  attribute, event and status scrubbed by one filter (`app/observability/scrub.py`, reusing `app/ai/redaction.py`).
  Logs are JSON with correlation and trace IDs, scrubbed by the same filter, configured only at process entry points.
  Model calls get a CLIENT span named `chat {model}` with operation, provider, request and response model, token
  counts, finish reason and this project's cost attribute; all `gen_ai.*` names live in `app/observability/genai.py`
  (a test fails if one appears anywhere else). Jobs store the W3C `traceparent` (migration 0012), so the worker's
  span continues the request's trace. Health and readiness probes aren't traced.
- **Found while building:** `opentelemetry-instrumentation-sqlalchemy` 0.66b2 supports SQLAlchemy < 2.1 and
  instrumented nothing on 2.1.6 (an error at startup). Database spans come from two engine events instead, with the
  statement text and never its parameters (TD-54). The mock API repeats the two scrub rules because it shares no
  code with the app (ADR-0040; TD-55, with a test that runs both over the same planted values).
- **Tradeoff:** scrubbing costs a copy of each span at export, and removing query strings loses the filter values
  that would help debugging a lookup; the route and status stay. The GenAI names may change before they're stable.
- **Result:** `tests/test_observability.py`: a planted email, phone, model key, bearer token, database password and
  query string never reach an exported span or a log line (and the unscrubbed spans do hold the query, so the
  filter is what removes it); one trace spans the app, a real local mock-API server and the worker.
- **What would change this decision:** the GenAI conventions reaching Stable (rename in one file); a SQLAlchemy 2.1
  release of the instrumentation (TD-54); a collector-side redaction processor the customer already runs, which
  could replace the in-process one only after the same tests pass against it.

## ADR-0078: Production quality monitoring: metrics, drift, QA sampling, analytics export
- **Context:** spec F.1 lists the metrics (queue, escalations, approvals, tool use, per-case model cost, provider
  spend); E5 asks for online QA sampling kept apart from offline evaluation, and drift signals with configurable
  thresholds; E7 asks for a privacy-filtered daily analytics export. Everything it needs is already stored: case
  events, AI runs and steps, approvals, jobs, the spend table.
- **Options considered:** a metrics pipeline with its own tables (a second copy of the truth); computing everything
  from the stored tables when asked (no new writes, slower as data grows); sampling by a random draw (not
  repeatable) or by a scheduled sweep (needs a scheduler and can miss cases).
- **Decision:**
  - **Metrics** stay computed from the stored tables (`app/services/metrics.py`), now with the oldest job's age,
    approvals, AI runs, tokens and cost per arm and per case, tool calls by status, and today's and this month's
    provider spend as the caps count it.
  - **Drift** (`app/services/drift.py`): seven observed signals for two windows of people's cases (scripted
    benchmark cases are left out), compared against thresholds in the customer's `monitoring` section. A signal
    drifts past its threshold: rates in absolute points, tokens per case as a fraction of the baseline, the category
    mix as a total variation distance. No alert below 30 cases in a window, rather than a noisy one.
  - **QA sampling** (`app/services/qa_sampling.py`, migration 0013): a keyed hash of the case reference picks the
    configured share of resolved cases in the configured arms (10%, arm C), in the same transaction that resolves
    them, on all three paths: arm A's close, arm B and C's close, and an executed adjustment. Repeatable, can't be
    steered by whoever closes the case, and needs no scheduler. Reviewers are supervisors or auditors, never the
    person whose work it was; answers are rubric codes only (`docs/qa-rubric.md`, proposed). Results live in their
    own table, which nothing in `benchmarks/` reads.
  - **Analytics export** (`app/services/analytics_export.py`): one CSV row per day, arm and kind of worker, from an
    allow-list of count, sum and median columns.
- **Found while building:** an executed adjustment resolves its case inside the write path, not through either close
  function, so the first version never sampled an adjusted case (a test watching the hook saw no call on DV-001).
  The write path now samples too, with the requester as the person whose work it was.
- **Tradeoff:** computing on request reads every case each time (fine at the synthetic volumes, measured in the load
  test, PR 4). The thresholds and the 10% rate are assumptions, not measurements. Category mix uses the queue, the
  only category the app has; a real customer's request types would replace it.
- **Result:** `tests/test_ops_monitoring.py` (14 tests): queue age, tool use, spend and cost per case; drift only
  past its threshold and with enough cases; sampling repeatable, keyed and within 8–12% at 10% over 5,000
  references; a person's executed adjustment sampled, a scripted one not; the reviewer rules, CSRF and the rubric over
  the API; the export holds none of the planted name, email, member number, confirmation, case reference or username.
- **What would change this decision:** volumes where computing on request is too slow (then materialized daily
  aggregates, as the analytics export already shapes them); a customer's own QA form (map it onto the rubric codes);
  a calibrated rubric from UAT (Milestone 18).

## ADR-0079: Security events: one classification over the audit tables, ECS export, owner-only retention
- **Context:** spec C.10 asks for security event logging (failed auth, denied authorization, privilege changes, tool
  execution, approval and execution, suspicious repeats, budget limits, configuration changes, credential
  revocation) with minimal content, restricted access, retention, and alerts with owners and runbooks; E7 asks for a
  SIEM-ready export with a field map. Most of these were already written where they happen, as append-only audit
  rows (ADR-0058). CSRF refusals were not.
- **Options considered:** a separate `security_events` table written beside the audit rows (two records of one
  fact, which can disagree); a log-only stream (lost on restart, and the app's logs are scrubbed of the detail an
  investigation needs); classifying the existing audit rows.
- **Decision:** `app/services/security_events.py` classifies existing audit rows by action (category, ECS outcome,
  a proposed severity) from one table, `KINDS`. A test fails if a classified action isn't written anywhere in the
  code, so the list can't claim coverage that doesn't exist. CSRF refusals are now recorded in the console and the API.
  Reading is for administrators and auditors only (`GET /api/v1/security/events`, the CLI export). The export is JSON
  lines with Elastic Common Schema names (`docs/siem-field-map.md`), and detail fields leave only from an allow-list.
  Retention: the audit record is kept. Only high-volume refusals expire (default 400 days, at least 30), and only
  the owner role can delete them, through the migrate service.
- **Tradeoff:** classifying on read means the rules can change without rewriting history, but an old export and a new
  one can classify the same row differently (the export carries the action, so a SIEM can re-map). "Suspicious
  repeats" are an alert over these events (the dashboards), not an event of their own. Severity levels are proposed.
- **Result:** `tests/test_security_events.py`: real flows (a failed sign-in with a password typed as the username, a
  denied page, an API write without CSRF, a kill switch change, a budget stop) produce classified events. The typed
  password, the kill switch's reason and the demo password never reach the export. Retention deletes only old
  refusals and refuses fewer than 30 days.
- **What would change this decision:** a customer SIEM with its own schema (map the ECS fields once); a requirement
  to stream events as they happen (add a log sink for the same documents; the classification stays one table).

## ADR-0080: Local dashboards and alerts: Grafana's all-in-one image, provisioned from the repository
- **Context:** spec F.1 asks for operational dashboards and actionable alerts linked to runbooks; C.10 asks for alerts
  with owners. Everything must run locally at no cost; the hosting choice (Render free, option A) has no metrics
  backend.
- **Options considered:** separate Prometheus, Tempo, Loki and Grafana containers (four images to pin and wire); a hosted
  observability vendor's free tier (an account, and synthetic telemetry leaving the machine); Grafana's
  `otel-lgtm` image, which bundles a collector, Prometheus, Tempo, Loki and Grafana behind one OTLP endpoint.
- **Decision:** `grafana/otel-lgtm:0.38.1` in a new `observability` profile, bound to 127.0.0.1, hardened like the
  other services, with the dashboards (`observability/grafana/dashboards/`) and alert rules
  (`observability/grafana/alerting/rules.yaml`) mounted read-only. Edits in the UI aren't saved, so every change is a
  reviewed commit. The worker exports seven gauges taken from one database snapshot per collection
  (`app/observability/ops_metrics.py`): queue, oldest job, dead jobs, AI spend and caps, security refusals and
  protocol calls in the last 15 minutes. The app exports its HTTP server metrics. Seven alert rules each carry a
  proposed owner, a severity and a runbook in `docs/runbooks/` (Stage 5's format, REUSE-05). No contact point is
  configured: wiring alerts to email or chat is the customer's choice at handover.
- **Found while building (six):** (1) the metric names Prometheus actually stores differ from what I first wrote
  (`loyalty_ai_spend_USD`, and the FastAPI instrumentation's `http_server_duration_milliseconds` with
  `http_status_code`, not the newer `http_server_request_duration_seconds`), so the rules and the dashboard use the
  names the first run read back. (2) The worker's once-a-second job poll made a one-statement trace named `SELECT`
  every second and buried the real ones. Database spans are now recorded only inside a request, job or model call (a
  test). (3) Every alert rule failed with "plugin not registered", and the Tempo proxy path answered 404. The cause:
  this image's Grafana runs as root and, at start, replaces its bundled Prometheus, Tempo and Loki plugins. With
  `cap_drop: ALL` it can't remove files it doesn't own, so no datasource worked. Three probe containers (none, all
  dropped, all dropped plus two) showed `DAC_OVERRIDE` and `FOWNER` are the smallest set that works; the hardening
  test allows exactly those two for this image. The check now also runs a query through Grafana, which would have
  caught it. (4) Postgres reported healthy before it accepted TCP: on first start the image runs its init scripts on a
  socket-only server, and the socket check passed, so the mock API got "connection refused". The healthcheck now
  uses `-h 127.0.0.1` (Compose, CI's service container, `scripts\ci_local.ps1`). It hadn't shown before, because the
  window is short; the large Grafana image starting alongside widened it. (5) Rules evaluated before the plugins
  were installed keep that error until their next clean evaluation, so the check waits for one. (6) "App not
  reporting" first keyed on the HTTP metrics, which exist only after a request, so an idle app went "pending" (a
  false alarm in five minutes). The app now reports `loyalty_app_up`, and the check requires that rule to stay quiet.
  Its first unit, `"1"`, became `loyalty_app_up_ratio` in Prometheus, which the rule didn't match while the check's
  prefix match let it pass; the unit is now `{process}` and the check matches names exactly.
- **Tradeoff:** one large image (about 900 MB) for a local profile; Grafana's built-in admin/admin stays, bound to
  localhost with anonymous viewers read-only (never for a shared host). Logs stay in `docker compose logs`, not Loki:
  the app writes scrubbed JSON to stdout, and shipping them is a collector setting a customer would choose. Gauges
  are counted from the database on each collection, so they read the same as `/metrics`, at the cost of one query
  set every 15 seconds.
- **Result:** `scripts\observability_check.ps1` (verification log, Milestone 12, row 21): gauges and HTTP metrics in
  Prometheus, app traces in Tempo with nothing planted in them, the dashboard and seven rules loaded, every rule
  evaluating cleanly, and a planted dead job making "Jobs giving up" fire. `tests/test_ops_metrics.py`: the gauges,
  and that every rule links an existing runbook listed in the index.
- **What would change this decision:** a customer's own monitoring (send the same OTLP to their collector, and load
  the dashboard and rules there; the names are in one module and one file); a hosted deployment that needs alerts
  delivered (add a contact point there, not here).

## ADR-0081: Circuit breakers, backpressure on new investigations, and the execution flag
- **Context:** spec F.1 asks for circuit breakers where justified, queue backpressure, a provider-outage manual
  fallback and feature flags for live AI and for adjustment execution. Milestone 8 already has bounded retries for
  transient errors, budgets, and the manual fallback. Missing: when a dependency is down, every case still spends its
  retries and timeouts; nothing stops the queue growing without limit; and `FEATURE_ADJUSTMENT_EXECUTION` was
  checked by preflight but read by no code.
- **Options considered:** a breaker library (one more dependency for about 60 lines); a breaker for every outbound
  call (the identity provider and protocol peers have their own short timeouts and few calls); backpressure on case
  intake (would refuse a member's request, the one thing that must always be recorded); backpressure on every job
  kind (would refuse executions and reconciliation, which must never be dropped).
- **Decision:**
  - A small breaker (`app/adapters/circuit.py`) for the customer systems and the live model provider only: 5
    failures within 30 seconds open it, and after 30 seconds one trial call decides. It counts only answers that
    mean the system is failing (503, timeouts, uncertain writes). "Not found", conflicts, rate limits and a provider's
    refusal of a bad request mean the system is up. While it's open, nothing is sent (safe even for a write), and the
    caller's existing rules apply: an investigation retries later, and the AI loop takes its manual fallback. One
    breaker per dependency per process, injected only by the production wiring, so tests that inject faults don't
    share one.
  - **Backpressure on new investigations only:** at `MAX_QUEUED_INVESTIGATIONS` (default 200, an assumption)
    waiting, starting one answers 503 with `Retry-After` (API problem `busy`, console page "Busy right now"), and
    the case is unchanged. Case intake, follow-up investigations, executions and reconciliation are never refused.
  - **`FEATURE_ADJUSTMENT_EXECUTION`** is now a setting read by the write path. When it's off, requesting execution
    is refused and a queued execution is held, exactly as under the kill switch: the approval stands and nothing is
    sent. It's on unless set otherwise, and `config/environments/production.env` sets it to `false`.
- **Tradeoff:** a per-process breaker means each worker learns of an outage on its own (a few extra failed calls
  with several workers). The default limit of 200 isn't measured yet; the load test (PR 4) gives the clearing rate.
- **Result:** `tests/test_reliability.py`. The breaker opens and recovers through one trial. A failing customer
  system stops calls going out, and a "not found" never opens it. A model outage fails the third call without
  reaching the provider, while a rejected request counts as the provider being up. A second investigation past the
  limit gets 503 with the case unchanged, while work already queued isn't refused. With execution off, an approved
  adjustment stays Approved, with no execution attempt.
- **What would change this decision:** several app instances behind a load balancer (share breaker state, for
  example in Redis, or accept per-instance learning); a measured clearing rate (set the limit from it); a customer
  who wants intake itself throttled (put it at the gateway, never by dropping a request).

## ADR-0082: Model lifecycle: a release gate on the frozen mock regression, retirement tracking, shadow, feedback
- **Context:** spec E.6 and E5 ask for a regression evaluation before release on any change, a known-good
  configuration for rollback, deprecation tracking, canary or shadow for prompt and model versions, and a
  feedback-to-dataset pipeline only through labeling review. The pieces exist: the committed mock run
  `benchmarks/results/mock/c-mock-dev` (Milestone 10), the allowed-model list, and the label review.
- **Options considered:** gating on the whole benchmark (minutes of scripted arms that a prompt can't change); gating
  only on a prompt-file change (misses the AI code, the mock, policies and eligibility); an LLM-judged comparison
  (the judge isn't calibrated, TD-48); routing a share of real investigations to a candidate (needs live calls).
- **Decision:**
  - **Release gate** (`scripts/release_gate.py`, CI job "Release gate" on every pull request). When a pull request
    touches a path that can change arm C, it re-runs arm C on the dev split with the mock provider and compares 12
    decision fields case by case with `c-mock-dev`. Any difference fails the gate, and a person reviews the list.
    The baseline's manifest names its commit: that's the known-good configuration to roll back to.
  - **Retirement tracking** (`app/ai/lifecycle.py`). Each allowed model carries `deprecated` and the provider's
    published `retires_on` (none for the current one, so none is written). The review blocks a deprecated, retired
    or soon-retiring model and warns when the check is stale. The harness refuses a model past its date.
  - **Shadow:** `AI_PROMPT` selects a candidate prompt for a run into its own folder, and the gate compares it
    (`--candidate`). Nothing of it reaches a case.
  - **Feedback to dataset** (`evaluations/feedback_candidates.py`). Disagreements become a review sheet with codes
    only, and only reviewed `add` rows are promoted, into the input for the next dataset version.
- **Tradeoff:** the gate takes about 2.5 minutes on this machine, on the pull requests where it runs. Comparing
  every decision field means an intended change always fails first and is re-baselined deliberately. On the mock,
  shadow checks plumbing, not prompt quality.
- **Result:** the gate passed on the code as committed: 100 of 100 case runs identical to the Milestone 10 baseline.
  So nothing since then (protocols, observability, reliability) changed arm C. With `max_turns` set to 1 it failed
  with 240 differences, so it isn't passing for want of looking. `tests/test_model_lifecycle.py`: the review's
  rules, no invented date, the harness refusal, `AI_PROMPT`, the gate's comparison and trigger paths, and feedback
  candidates holding none of 5 planted identifiers.
- **What would change this decision:** an approved live budget (shadow on the live model, and prompt caching,
  ENT-17); a calibrated judge (add explanation quality to the gate); a provider deprecation API (read `retires_on`
  from it instead of by hand).

## ADR-0083: A bounded load test with a small async driver, against a throwaway stack
- **Context:** spec F.1 asks for a declared, realistic load profile and a bounded load test that reports API against
  investigation latency, throughput, queue age and delay, failure rate and database behaviour, naming the simulated
  dependencies. The declared volume is small (about 320 requests a month, assumption A1), so the question is
  headroom and what breaks first.
- **Options considered:** Locust (a new dependency tree, gevent, and a web UI not needed for a bounded run); k6 (a
  second language and an install); a small asyncio driver on `httpx`, which the project already pins.
- **Decision:** `scripts/load_test.py`, run by `scripts\load_test.ps1` against its own Compose project with the demo
  accounts. The profile is declared in `docs/load-profile.md`: three 2-minute stages, `baseline` (2 virtual agents
  and 1 supervisor), `x4` and `x10`. Agents create a case from a synthetic dataset request, start its investigation,
  open the queue and read the case until the worker finishes. Supervisors read approvals and metrics. The run lifts
  the per-user rate limit, because virtual users share four demo accounts, and changes nothing else. The report
  and raw samples go to `performance/reports/`, labelled "not production capacity".
- **Tradeoff:** virtual users act far faster than people, so stages are stress steps, not a model of people's
  timing. Without `pg_stat_statements`, the database section uses counters, not per-query times. CPU was sampled
  only before and after, so the reading of what limits throughput is an inference.
- **Result (2026-11-14):** 4,602 API requests, **0 failures**. At `baseline`, 155 investigations finished in 120 s
  (p50 1.7 s, p95 1.9 s). Throughput peaked at `x4` (16.5 requests/s), then fell at `x10` (12.8) while API p95 rose
  to about 2 s. The queue stayed short (at most 16 waiting, the oldest 9 s), so the single worker kept up. Postgres
  stayed at 7–8 connections, cache hit over 99.7%, no deadlocks. The likely first limit is the single app process (1
  CPU), not the worker; that's inferred. `/metrics` is the slowest page, as ADR-0078 expected.
- **What would change this decision:** a pilot with real traffic (replay it instead of a synthetic mix); a hosted
  deployment (run the same driver against it, with the owner's approval and its own limits); a need for per-query
  numbers (load `pg_stat_statements` in the test's stack).

## ADR-0084: The full CI pipeline and the supply chain
- **Context:** spec F.2 asks for migration on an empty database, static analysis, dependency, secret, container and
  IaC scans, builds, an SBOM, Playwright and provenance "where supported", under rules: no paid key, least-privilege
  tokens, no secrets to untrusted pull requests, scanners failing the build. It also asks for a protected manual
  deploy with environment approval and OIDC. The repository went public on 2026-11-13, so minutes are free and
  artifact attestations are available (the attest action's README says they're in public repositories on every
  plan). Milestone 11's runner failure came from an `apt` step during the Playwright install.
- **Options considered:** Trivy through `trivy-action` (its default Trivy version disagreed between its release
  notes and README); the pinned `aquasec/trivy` image run directly, like gitleaks; signing with cosign and a key
  (a key to keep); GitHub's keyless build-provenance attestations.
- **Decision:**
  - **New jobs.** `browser` runs in Playwright's image (`mcr.microsoft.com/playwright/python:v1.64.1-noble`), so
    there's no apt step. `images` builds the app, protocols and mock API images, runs Trivy on each (fixable HIGH and
    CRITICAL fail) and on the Dockerfiles, and writes an SPDX SBOM of the app image. On pushes to main it also
    attests the saved app image's build provenance. `compose` starts the default stack from an empty volume, as a
    newcomer would, seeds the demo and checks `/readyz`. The `postgres` job also takes migrations on an empty
    database up to head, down to base and up again. `scripts\ci_local.ps1` gains the same migration and image steps.
  - **Rules:** CI reads no secret at all, so a fork's pull request has nothing to take. Permissions are
    `contents: read` everywhere; only the images job may write, and only an OIDC token and attestations. Every
    action and image is pinned to an exact version. Dependabot proposes updates weekly. A test keeps these rules.
  - **Images:** the base moves from `python:3.12.10-slim-bookworm` (Debian 12.11, 54 fixable HIGH/CRITICAL in the
    app image) to `python:3.12.15-slim-bookworm`, plus Debian's security updates at build time. Both images then
    scan clean (0 fixable HIGH or CRITICAL). The image scan checks vulnerabilities only: Trivy's secret scanner read
    two docstrings in the `anthropic` package as Google service-account keys. The repository's own secrets stay with
    gitleaks.
  - **Deploy** (`.github/workflows/deploy.yml`): manual, main only, a typed confirmation, the `production`
    environment's approval, and an AWS role assumed through OIDC from a repository variable; no AWS key exists
    anywhere. It stops when no role is set. **Never run:** there is no AWS account.
- **Tradeoff:** `apt-get upgrade` in the image makes a rebuild pick up newer Debian packages, so two builds of one
  commit can differ; the SBOM records what each build contains. Provenance is attested only on main, because a
  fork's pull request gets no OIDC token. The browser tests' coverage no longer counts toward the coverage gate,
  which is still met without them.
- **Result:** both images scan clean on the new base, and the Dockerfiles have no HIGH or CRITICAL
  misconfiguration. Local CI's migration round trip and image scans pass (verification log, Milestone 12, row 26),
  as does `tests/test_ci_workflow.py`. CI's first run of the new jobs is recorded with the pull request.
- **What would change this decision:** a registry for the images (attest and push there, and verify before deploy);
  a customer's own scanner or base-image policy; an AWS account with the owner's approval (configure the role and
  the environment's reviewers, then run the deploy once).

## ADR-0085: Terraform for one AWS path (validate only), rollback by image, operations documents
- **Context:** spec F.2 asks for Terraform for one AWS path (ECS Fargate, private RDS, ALB with ACM, Secrets
  Manager, least-privilege roles, CloudWatch, backups, tags, teardown) checked by `fmt` and `validate`, plus
  rollback, backup and restore, proposed SLOs, release gates per environment and a maintenance schedule. There is no
  AWS account, and `terraform apply` needs the owner's approval and a budget.
- **Options considered:** community modules (fewer lines, but versions and defaults to vet one by one); a single
  monolithic file; plain resources split by concern. For rollback: schema downgrades, or image rollbacks with
  expand/contract migrations.
- **Decision:**
  - **Terraform:** `infrastructure/terraform/aws/`, plain resources, Terraform 1.17.1 and AWS provider 6.71.0
    pinned, with the lock file committed. Two zones; the tasks and the database sit in private subnets. One NAT
    gateway (a stated cost choice). Only the ALB takes traffic from the internet, on 443 with TLS 1.3. RDS is
    encrypted with a project KMS key, keeps automated backups for 7 or 14 days, forces SSL, and has deletion
    protection in production. RDS manages the owner's password, so it's never in code or state. Secrets Manager
    entries are created empty, and a person fills them. The task role has no AWS permissions; the execution role
    reads only the named secrets. ECS's deployment circuit breaker rolls back a release that never becomes healthy.
    CloudWatch alarms name their runbooks, and a budget alarm covers spend. **Checked, never applied:**
    `scripts\terraform_check.ps1` and a CI job run `fmt -check`, `init -backend=false`, `validate` and Trivy.
  - **Rollback** (`docs/rollback.md`) rolls back the image, never the schema, because migrations are
    expand/contract. All 13 migrations have a downgrade; CI runs every one down to base and back up on a fresh
    Postgres. But 11 of them drop live data on the way down, so production fixes forward. The table lists each one,
    and a test fails if a new migration isn't added to it.
  - **Operations documents:** `docs/backup-restore.md` (instructions; the timed drill is Milestone 13),
    `docs/slos.md` (proposed only; "a local test proves no production availability"), `docs/environment-gates.md`,
    `docs/maintenance.md`, `docs/teardown.md` and `docs/aws-deploy-setup.md`.
- **Found while building:** Trivy reads its inline ignore only on the line before the resource, under the rule's
  new ID (`AWS-0132`, not `AVD-AWS-0132`). The one exception is the ALB log bucket's encryption: ALB access logs
  accept only SSE-S3. My first comments promised an HTTP-to-HTTPS redirect that didn't exist; the comment was
  corrected, and port 80 stays closed.
- **Tradeoff:** plain resources are longer than modules but every setting is visible and reviewed. One NAT gateway
  is a single point of failure for outbound calls, so the production SLO assumes two. The Terraform has never met
  real AWS; `validate` checks types and references, not behaviour.
- **Result:** the Terraform check passed: fmt, init, validate, and Trivy with 0 HIGH or CRITICAL findings
  (verification log, Milestone 12, row 27). `tests/test_infrastructure_docs.py` keeps the database private,
  encrypted and backed up; only the ALB open to the internet, on 443; no secret or access key in the code; the
  rollback table complete; and the SLOs labelled proposed.
- **What would change this decision:** an AWS account and a budget approved by the owner (plan, apply to a sandbox,
  run the deploy once, then the restore drill); a customer's own module library or landing zone (map onto it).
