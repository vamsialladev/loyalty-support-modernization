# Tool access matrix

Workspace, repository and access audit for Stage 9 (Milestone 1, requirement `TOOLMAT-01`). Commands and results
are in `docs/verification-log.md` (2026-10-28). This file grows into the full Part H matrix in Milestone 15.

## 1. Workspace and repository

| Item | Finding (2026-10-28) |
|---|---|
| Repository | `C:\projects\project1\loyalty-support-modernization`, local Git, branch renamed `master` → `main` (ADR-0013) |
| Existing commits | 3 (spec and env template; Appendix L; spec update for the current site); `docs/MASTER-SPEC.md` had no uncommitted changes |
| Remote | **Private** `vamsialladev/loyalty-support-modernization`, created 2026-11-03 with the owner's OK (ADR-0053). `main` pushed 2026-11-04 after the owner unticked the email block for it; new commits use the noreply address. Making it public needs the owner's OK |
| `.env` | present, untracked, now Git-ignored. Byte-identical to `.env.example`, so every value is still empty (checked with `cmp`, file not opened) |
| Earlier implementation | none; only `docs/MASTER-SPEC.md`, `.env.example` |
| Parent folder | `C:\projects\project1` holds the other stages' working copies and the local video kit; its `CLAUDE.md`, `HANDOFF.md`, `PROGRESS.md` belong to the portfolio project and are ignored here |

## 2. The four access types (spec B.2: one never implies another)

| Access type | What it is here | Current state |
|---|---|---|
| Developer-assistant access | Claude Code in this folder (the owner's subscription) | Active. Grants nothing at runtime |
| Runtime model access | Claude API key in `.env` (`ANTHROPIC_API_KEY`) for live mode | **Not set.** App runs on the offline mock provider; live runs are NOT RUN until set |
| Customer-system access | Real loyalty, PMS or CRM systems | **None, by design.** Only the synthetic mock API (Milestone 4) |
| Deployment access | GitHub push, AWS, Supabase, Vercel | **GitHub push to this private repository only**, approved by the owner on 2026-11-03; each later push still needs the owner's OK. No cloud credentials |

## 3. Local tools

| Tool | Needed for | Status | Version / note |
|---|---|---|---|
| Git | everything | Available | 2.45.2.windows.1; identity Vamsi Alla / vamsialla.dev@gmail.com |
| GitHub CLI `gh` | repo creation, PRs (with OK) | Available | 2.78.0; two accounts signed in, `vamsialladev` active. Push with the `gh auth git-credential` helper (`CLAUDE.md`) |
| Python | app | Available | 3.12.10 |
| uv | dependencies, lockfile | Available | 0.13.5 |
| ruff | lint, format | Available | 0.17.0 (also pinned in the dev group) |
| Docker Desktop | Postgres, Compose, Keycloak | Available, daemon running | 27.0.3 |
| Node.js / npm | React frontend (Milestone 15) | Available | v24.22.1 / 11.19.1. Not needed for the browser tests: they use Playwright for Python |
| Playwright for Python + Chromium | browser tests (Milestone 5) | Installed 2026-10-29 | `playwright` 1.64.1, `pytest-playwright` 0.10.0 (dev group); Chromium from `uv run playwright install chromium` (Playwright's official download, outside the repo). Tests skip with the reason if it is missing |
| ffmpeg | demo video | Available | on PATH |
| Cursor | Cursor exercise | Installed (`cursor` on PATH) | exercise in Milestone 15 |
| make | `make` targets | **Missing** | every target has a `scripts\*.ps1` equivalent |
| gitleaks | secret scanning (K2.6) | Via Docker image `ghcr.io/gitleaks/gitleaks:v8.30.1` | runs in CI and on demand; no local install needed. Pre-commit hook in Milestone 12 |
| Terraform | IaC validate (F.2) | **Missing** | needed by Milestone 12 (free install; `fmt`/`validate` only, never `apply`) |
| Trivy, syft | container/IaC scan, SBOM | **Missing** | CI actions in Milestone 12; local optional |
| AWS CLI | AWS path | **Missing** | not needed until an approved deploy; SSO profile only |
| Supabase CLI | Supabase profile | **Missing** | Milestone 15 |
| PostgreSQL client `psql` | debugging | **Missing** | not required; `docker compose exec db psql` works |
| PowerShell 7 `pwsh` | — | Missing | Windows PowerShell 5.1 is used; scripts target 5.1 |
| Codex CLI | Codex exercise (kit ready: `docs/exercises/codex-reconciliation-review.md`) | **Missing** | owner installs and signs in, then runs the kit (Milestone 6 or 13) |

## 4. Accounts and services

| Service | Category (C.3) | Needed for | Status |
|---|---|---|---|
| Anthropic Claude API | B. runtime model | live arm C, live smoke test | Available: settings in `.env` (owner, 2026-11-07). Smoke test passed. Live evaluation approved with a $5 total cap |
| Amazon Bedrock | B. runtime model | enterprise endpoint adapter | Blocked: needs AWS SSO profile and model access (configure only) |
| Kimi / GLM / Qwen | B. runtime model | open-model exercise | Blocked: needs one key or a local server (Milestone 15) |
| GitHub (this repo) | A/D. dev and CI | remote, CI, PRs | Manual step required: owner approves creating the repo |
| CodeRabbit | A. dev review | PR review exercise | Blocked: owner installs the GitHub app on this repo only |
| Supabase | C/D. hosted DB + Auth | Supabase profile | Blocked: owner account and keys |
| Vercel | deployment | React frontend | Blocked: owner account, and only after bolt.new |
| bolt.new | A. prototyping | React prototype | Blocked: owner browser login |
| Monday.com, Miro | collaboration | board exercises | Blocked: owner tokens (import files prepared without access) |
| Telegram / Mira | personal productivity | Mira exercise | Blocked: product verification first (Milestone 15) |
| Egolite, Invoco | personal productivity | exercises | Blocked: verification; both described as macOS apps, owner is on Windows |
| AWS account | deployment | IaC apply (never without OK) | Not requested; IaC is validate-only |

Batched account questions go to the owner once per milestone that needs them, starting with Milestone 8 (Claude
API key and budget). Nothing here asks for a secret in chat; values go into `.env` (see `docs/accounts-setup.md`).
