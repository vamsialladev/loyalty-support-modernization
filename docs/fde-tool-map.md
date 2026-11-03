# FDE tool map

> **Early draft** of spec H.3 (requirement TOOL-MAP; completed in M15). One row per capability: the tool, how it
> connects, what access it needs, what data it touches, its status, and what happens when it isn't available.
> Status: exercised / configured / blocked / planned. Account details are in `docs/tool-access-matrix.md`.

| Capability | Tool | Connection | Access needed | Data touched | Status | If unavailable |
|---|---|---|---|---|---|---|
| Coding assistance | Claude Code | Local CLI / desktop app in this repo | Owner's subscription (developer-assistant access only) | Repo files (synthetic) | Exercised (M1–M2) | Work continues by hand; nothing in the app depends on it |
| Version control | Git, GitHub CLI | Local Git; `gh` with the vamsialladev account | Push needs the owner's OK | Repo | Git exercised; GitHub configured (no remote yet) | Local commits only |
| Dependency management | uv | Local CLI, `uv.lock` | None | Packages from PyPI | Exercised | `pip` with the lockfile exported |
| Lint, format, types | ruff, mypy | Local and (later) CI | None | Code | Exercised | — |
| Testing | pytest | Local and (later) CI | None | Synthetic data | Exercised | — |
| Secret hygiene | preflight, env-leak check; gitleaks (planned) | Local; CI from M12 | None | `.env` (values never printed) | Preflight and leak check exercised; gitleaks blocked (not installed) | Leak check still runs |
| Synthetic data and documents | Python generator; reportlab (PDF), Pillow (images), matplotlib (charts) | Local libraries, pinned in `uv.lock` | None | Synthetic records only | Exercised (M3) | — (core dependency; no external service) |
| Containers | Docker Desktop, Docker Compose | Local daemon; `docker-compose.yml`, `scripts\stack.ps1` | None | Synthetic data | Exercised (M4) | In-process contract tests still run on SQLite; Postgres tests show SKIPPED with the reason |
| Database | PostgreSQL 16 (`postgres:16.15-alpine`), SQLAlchemy 2, Alembic | Compose service; per-system roles and databases (ADR-0036) | Local role passwords in `.env` | Synthetic members, stays, ledger | Exercised (M4) | SQLite for in-process tests only |
| Customer system integration | Mock customer API (FastAPI) + `CustomerSystems` port + adapter (httpx) | HTTP with bearer token; OpenAPI contract `mock_customer_api/contracts/openapi-v1.json` | `MOCK_API_TOKEN` | Synthetic records | Exercised (M4) | Real systems replace it through a sibling adapter (`docs/real-system-swap-guide.md`) |
| Operational console | Jinja2 3.1 + htmx 2.0.11 (vendored, hash recorded) + CSS, served by FastAPI | Server-rendered pages; HTMX swaps search results; strict CSP `script-src 'self'` | None (local) | Synthetic cases and evidence | Exercised (M5) | Every page also works as a plain HTML form without JavaScript |
| Browser testing | Playwright for Python, Chromium | `tests/browser/` drives the console; offline (uvicorn + SQLite) or against the stack (`compose_check.ps1 -Browser`) | One-time Chromium download | Synthetic | Exercised (M5) | Tests show SKIPPED with the install command; HTTP-level console tests still run |
| Sign-in | argon2-cffi (local demo adapter) behind the `IdentityProvider` port | App database users and server-side sessions | `DEMO_USER_PASSWORD` in `.env` | Demo account names only | Exercised (M5) | OIDC (Keycloak) replaces the adapter in M9 |
| AI runtime | Claude API (mock first) | Provider interface (M8) | `ANTHROPIC_API_KEY` in `.env` | Minimised, redacted case context | Blocked: needs key | Mock provider; live results reported as NOT RUN |
| Collaboration, tracking, prototyping, review | Miro, Monday.com, bolt.new, CodeRabbit, Cursor, Codex | See `docs/tool-access-matrix.md` | Owner logins / tokens | Synthetic project info only | Planned (M15) | Import files and documented steps; marked Blocked |
