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
| Containers | Docker Desktop | Local daemon | None | Synthetic data | Configured (running; used from M4) | No local Postgres; tests needing it are skipped and reported |
| AI runtime | Claude API (mock first) | Provider interface (M8) | `ANTHROPIC_API_KEY` in `.env` | Minimised, redacted case context | Blocked: needs key | Mock provider; live results reported as NOT RUN |
| Collaboration, tracking, prototyping, review | Miro, Monday.com, bolt.new, CodeRabbit, Cursor, Codex | See `docs/tool-access-matrix.md` | Owner logins / tokens | Synthetic project info only | Planned (M15) | Import files and documented steps; marked Blocked |
