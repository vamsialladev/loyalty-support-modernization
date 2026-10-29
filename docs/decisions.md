# Decisions (ADR style)

Each decision records context, decision, tradeoff and result. ADR-0001 to ADR-0010 are the binding resolutions
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

## ADR-0006: live model through an application-owned provider interface; default Claude Haiku 5.5
- **Context:** Claude Code (dev tool) and the Claude API (runtime) are different access types (spec B.2). Every
  published stage uses Claude Haiku 5.5 (`docs/continuity.md` §11).
- **Decision:** runtime model calls go through the provider interface. Offline mock provider by default. The live
  default is Claude Haiku 5.5 (model ID `claude-haiku-5-5`, to be re-verified in official docs at Milestone 8).
  One alternative provider (Kimi, GLM or Qwen) only behind the same interface, with access, by explicit selection.
- **Tradeoff:** an interface to maintain; in return no SDK in domain code and no silent provider switch.
- **Result:** applies from Milestone 8.

## ADR-0007: at least 60 labelled evaluation cases
- **Decision:** ≥60 labelled synthetic cases (supersedes the earlier 40), split dev / validation / held-out / stress.
- **Result:** applies from Milestone 3.

## ADR-0008: Postgres full-text search is the retrieval baseline
- **Decision:** embeddings, hybrid search or reranking only after a controlled comparison shows a benefit.
- **Tradeoff:** stage 1 needed hybrid search for meaning-only questions; Stage 9 measures before adopting it.
- **Result:** applies from Milestone 6.

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
