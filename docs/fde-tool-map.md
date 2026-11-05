# FDE tool map

> **Early draft** of spec H.3 (requirement TOOL-MAP; completed in M15). One row per capability: the tool, how it
> connects, what access it needs, what data it touches, its status, and what happens when it isn't available.
> Status: exercised / configured / blocked / planned. Account details are in `docs/tool-access-matrix.md`.

| Capability | Tool | Connection | Access needed | Data touched | Status | If unavailable |
|---|---|---|---|---|---|---|
| Coding assistance | Claude Code | Local CLI / desktop app in this repo | Owner's subscription (developer-assistant access only) | Repo files (synthetic) | Exercised (M1–M2) | Work continues by hand; nothing in the app depends on it |
| Version control | Git, GitHub CLI | Local Git; `gh` with the vamsialladev account | Push needs the owner's OK | Repo | Git exercised; private repository `vamsialladev/loyalty-support-modernization` created 2026-11-03 with the owner's OK, `main` pushed 2026-11-04 (ADR-0053) | Local commits only |
| Dependency management | uv | Local CLI, `uv.lock` | None | Packages from PyPI | Exercised | `pip` with the lockfile exported |
| Lint, format, types | ruff, mypy | Local and (later) CI | None | Code | Exercised | — |
| Testing | pytest | Local and (later) CI | None | Synthetic data | Exercised | — |
| Continuous integration | GitHub Actions (`.github/workflows/ci.yml`) | Runs on every push to `main` and every pull request; read-only token | The repository; free private-repo allowance | Repo and synthetic data; no secrets | Exercised: first runs green on 2026-11-04, on a throwaway branch and on `main` (ADR-0053); full pipeline in M12 | The same commands run locally: `scripts\test.ps1`, `scripts\compose_check.ps1` |
| Secret hygiene | preflight, env-leak check; gitleaks | Local; gitleaks in CI as a pinned container, full history | None | `.env` (values never printed); Git history | All exercised (no local gitleaks install needed: Docker image) | Leak check still runs |
| Synthetic data and documents | Python generator; reportlab (PDF), Pillow (images), matplotlib (charts) | Local libraries, pinned in `uv.lock` | None | Synthetic records only | Exercised (M3) | — (core dependency; no external service) |
| Containers | Docker Desktop, Docker Compose | Local daemon; `docker-compose.yml`, `scripts\stack.ps1` | None | Synthetic data | Exercised (M4) | In-process contract tests still run on SQLite; Postgres tests show SKIPPED with the reason |
| Database | PostgreSQL 16 (`postgres:16.15-alpine`), SQLAlchemy 2, Alembic | Compose service; per-system roles and databases (ADR-0036) | Local role passwords in `.env` | Synthetic members, stays, ledger | Exercised (M4) | SQLite for in-process tests only |
| Customer system integration | Mock customer API (FastAPI) + `CustomerSystems` port + adapter (httpx) | HTTP with bearer token; OpenAPI contract `mock_customer_api/contracts/openapi-v1.json` | `MOCK_API_TOKEN` | Synthetic records | Exercised (M4) | Real systems replace it through a sibling adapter (`docs/real-system-swap-guide.md`) |
| Operational console | Jinja2 3.1 + htmx 2.0.11 (vendored, hash recorded) + CSS, served by FastAPI | Server-rendered pages; HTMX swaps search results; strict CSP `script-src 'self'` | None (local) | Synthetic cases and evidence | Exercised (M5) | Every page also works as a plain HTML form without JavaScript |
| Browser testing | Playwright for Python, Chromium | `tests/browser/` drives the console; offline (uvicorn + SQLite) or against the stack (`compose_check.ps1 -Browser`) | One-time Chromium download | Synthetic | Exercised (M5) | Tests show SKIPPED with the install command; HTTP-level console tests still run |
| Sign-in | argon2-cffi (local demo adapter) behind the `IdentityProvider` port | App database users and server-side sessions | `DEMO_USER_PASSWORD` in `.env` | Demo account names only | Exercised (M5) | OIDC (Keycloak) replaces the adapter in M9 |
| Durable background work | PostgreSQL `SKIP LOCKED` queue, `app/worker.py` | Same database as the app; `worker` Compose service | `DATABASE_URL` as the runtime role | Job rows hold IDs only | Exercised (M6, ADR-0060) | Execution waits: cases stay `Approved` with the job queued, and nothing is lost. `--list-dead` shows what stopped |
| Database migrations | Alembic in a one-shot `migrate` service | Owner role, only in that service (ADR-0058) | `APP_OWNER_DB_PASSWORD` | Schema | Exercised (M6) | `scripts\stack.ps1 -Action migrate` runs it by hand |
| Secret scan before pushing | gitleaks in Docker, locally, as well as in CI | `docker run ... gitleaks git /repo --redact` | None | Git history (redacted output) | Exercised (M6): run before every push since CI flagged a false positive on PR #7 | CI still runs it |
| AI runtime | Claude API (mock first) | Provider interface (M8) | `ANTHROPIC_API_KEY` in `.env` | Minimised, redacted case context | Blocked: needs key | Mock provider; live results reported as NOT RUN |
| Independent code review | Codex | Owner's CLI in a separate checkout; `docs/exercises/codex-reconciliation-review.md` | Owner's OpenAI account and spending limit | Repo files (synthetic only); never `.env` | Prepared, not run: **Manual step required** (M6 kit; Appendix G allows M6 or M13) | Claude Code's review and the tests stand alone; the exercise stays marked as not run |
| Collaboration, tracking, prototyping, review | Miro, Monday.com, bolt.new, CodeRabbit, Cursor | See `docs/tool-access-matrix.md` | Owner logins / tokens | Synthetic project info only | Planned (M15) | Import files and documented steps; marked Blocked |
