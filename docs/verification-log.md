# Verification log

Every check run, with the command, date and result. Newest milestone first. Results are copied from real runs;
nothing here is predicted.

## Milestone 1 (2026-10-28)

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Repo state before work | `git status`, `git log --oneline` | Branch `master`, 3 commits, `docs/MASTER-SPEC.md` committed with no uncommitted changes; only `.env` untracked |
| 2 | `.env` contents without opening it | `cmp -s .env .env.example` | Identical: every value in `.env` is still empty |
| 3 | `.env.example` holds no secrets | read the committed template | Comments and non-secret defaults only |
| 4 | `.env` ignored after adding `.gitignore` | `git check-ignore -v .env` | `.gitignore:2:.env` |
| 5 | Branch rename | `git branch -m master main` | On `main` (ADR-0013) |
| 6 | Local tools | `<tool> --version` for git, gh, python, uv, docker, node, npm, ruff; `command -v` for the rest | See `docs/tool-access-matrix.md` §3: gitleaks, terraform, make, trivy, syft, aws, supabase, psql, pwsh, codex missing |
| 7 | GitHub CLI | `gh auth status` | Signed in as `vamsialladev` (active) and a second account; no remote on this repo (`git remote -v` empty) |
| 8 | Docker daemon | `docker info --format '{{.ServerVersion}} {{.OperatingSystem}}'` | 27.0.3, Docker Desktop, running |
| 9 | Public repos listed | `gh repo list vamsialladev --limit 50` | 14 public repos plus 1 private (`python-fluency-drills`, not reviewed, never listed publicly) |
| 10 | Public repos cloned read-only | `git clone --depth 1` × 13 into the session scratchpad | All 13 cloned; commits recorded in `docs/continuity.md` §1 |
| 11 | Live site matches the website repo | `curl "https://vamsialla.com/<page>?cb=<epoch>"` then `diff` against `main` for `data/projects.json`, `projects.html`, `index.html`, two case studies | All 200 and **identical** |
| 12 | Dependencies and lockfile | `uv add python-dotenv`, `uv add --dev pytest pytest-cov ruff mypy`, `uv lock`, `uv sync` | Resolved 17 packages; python-dotenv 1.2.4, pytest 9.2, pytest-cov 7.1, ruff 0.17.3, mypy 2.4.1 |
| 13 | First test run | `uv run pytest` | Collection error: `app` not importable. Fixed with `pythonpath = ["."]` in `pyproject.toml` |
| 14 | Second test run | `uv run pytest` | 7 failed, 61 passed. Six were tracking files not yet written. **One was a wrong measurement:** `test_env_example_has_no_secret_values` flagged `DATABASE_URL`, whose template value only references `${POSTGRES_PASSWORD}`. Fixed by reading the template without interpolation and allowing only a `${VAR}` reference as a URL password; added a test that the check still catches a literal key and a literal URL password |
| 15 | Lint and types | `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` | First run: 16 lint findings (long lines, an en dash, tuple concatenation) and 1 mypy error (`leaks` annotation). Fixed; then all clean (mypy strict: 4 source files, no issues) |
| 16 | Preflight on the owner's real `.env` | `uv run python -m app.preflight --profile portfolio` | NOT READY, 5 problems: `APP_SECRET_KEY`, `POSTGRES_PASSWORD`, `MOCK_API_TOKEN` missing; `DATABASE_URL`, `MOCK_API_DATABASE_URL` invalid (empty password). No value printed. Correct for an empty template |
| 17 | Leak check on the owner's real `.env` | `uv run python -m app.env_leaks` | "Checked 0 secret value(s) from .env against tracked files: 0 leak(s)." (no secrets set yet, so this run proves only that the check runs; the planted-value tests prove it detects) |
| 18 | Completion scores | `uv run python scripts/matrix_scores.py` | 355 requirements (Tier 1: 188, Tier 2: 102, Tier 3: 26, Tier 4: 39); scores in `docs/implementation-status.md` |
| 19 | Full offline checks on Windows | `powershell -ExecutionPolicy Bypass -File scripts\test.ps1` | Exit 0. ruff clean, 26 files formatted, mypy no issues, **71 passed**, coverage **97%** (`app/preflight.py` 98%, `app/env_leaks.py` 92%), gate 70% |
| 20 | PowerShell preflight wrapper | `powershell -ExecutionPolicy Bypass -File scripts\preflight.ps1 -Profile live-model` | Exit 1, NOT READY: the core variables above plus "live-model needs AI_PROVIDER set to a real provider, not mock" and "live-model needs FEATURE_LIVE_AI=true". No value printed |
| 21 | `make` targets | — | Not run: `make` is not installed on this machine. The `scripts\*.ps1` equivalents were run instead |
