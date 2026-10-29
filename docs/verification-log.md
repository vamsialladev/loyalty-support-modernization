# Verification log

Every check run, with the command, date and result. Newest milestone first. Results are copied from real runs;
nothing here is predicted.

## Milestone 4 (2026-10-29)

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Owner's `.env` before starting anything (owner's request) | `python -m app.preflight --profile portfolio` | `POSTGRES_PASSWORD`, `MOCK_API_TOKEN`, `APP_SECRET_KEY` set; `APP_DB_PASSWORD`, `MOCK_API_DB_PASSWORD` missing (new in M4, ADR-0036). The stack was **not** started on the owner's `.env` |
| 2 | Base images exist and are pinned | `docker pull` | `postgres:16.15-alpine` (PostgreSQL 16.15), `python:3.12.10-slim-bookworm`, `ghcr.io/astral-sh/uv:0.13.5` |
| 3 | In-process smoke test | scratch script: migrate SQLite, seed, adapter calls | Seed loaded 3,286 / 6,800 / 3,836 / 12; replay returned the same `ADJ-` ID; commit-then-lost raised `UncertainOutcome`, then found by key; bad token gave a typed 401 |
| 4 | Contract tests, first run | `pytest tests/test_mock_api.py` | 1 failure: a test helper passed `timeout_fault_seconds` twice (test bug). Fixed; 41 passed |
| 5 | Label-isolation scan after adding the mock API | `pytest -k app_cannot` | The word scan flagged Alembic's `branch_labels` and a docstring. Changed to path-like references (`labels/`, `benchmarks`, `evaluations`, `ground_truth`, `label-review`); the mock may read `seed_data/v1`, the app may not |
| 6 | Lint and types | `ruff check`, `ruff format`, `mypy` (strict, 44 files) | Clean after configuring bugbear for FastAPI's `Depends`/`Query`/`Header` defaults |
| 7 | Compose check, first run | `scripts\compose_check.ps1` | Failed at step 1: PowerShell 5.1 turns Docker's stderr progress into errors under `Stop`. Scripts switched to exit-code checking |
| 8 | Compose check, second run | same | Everything passed except the image-contents step: PowerShell 5.1 stripped the inner double quotes of the `sh -c` script. Re-run by hand on the built images with a quote-free script: both pass (no `benchmarks`/`evaluations`/`seed_data`/`docs`/`tests`, no `.jsonl` on the image file system, UID 10001, `/srv` not writable) |
| 9 | **Compose check, third run (Appendix C, M3-4)** | same | **Passed**: from an empty volume, `up --build --wait` healthy; `app.seed` migrated the app and loaded 3,286 members, 6,800 stays, 3,836 ledger entries, 12 queue items; app `/readyz` ready; 6/6 live checks (member, stay, sim clock, idempotent replay, real network timeout, commit-then-lost found by key); both images clean; **6/6 real-Postgres tests** (atomicity, 20 concurrent same-key requests apply once, conflict, two keys both apply, full seed, commit-then-lost over HTTP); `loyalty_app` refused by `mock_customer_api`. Stack and volume removed |
| 10 | Full offline suite | `scripts\test.ps1` | Exit 0: ruff and mypy clean; **204 passed, 6 skipped** (the real-Postgres tests, which skip without `TEST_MOCK_API_DATABASE_URL` and passed in row 9); coverage 94% (gate 70%) |

## Milestone 3 (2026-10-28 to 2026-10-29)

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Purpose docs committed before any M3 code | `git log` | `f0b3c34`; 124 tests passed at that commit |
| 2 | Libraries work on Windows (incl. time-zone data) | `python -c "import zoneinfo, PIL, reportlab, matplotlib, pydantic"` | `America/New_York` resolves (tzdata installed); Pillow 13.0, reportlab 5.1, pydantic 2.14.1 |
| 3 | First full generation | `python -m seed_data.generator generate --root <scratch>` | Failed: case DV-079 found no valid checkout date (wasteful sampling for post-July stays). Fixed by sampling inside the valid range |
| 4 | Second full generation | same | **The label cross-check failed on DV-078 (D16):** the labeler said escalate (24,809 points, above the 20,000-point supervisor limit in the policy); the builder intent said adjust. The labeler was right; the D16 builder now keeps multi-stay totals under the limit, and the limit rule has its own unit test |
| 5 | Third full generation | same | Failed on a reportlab font name (`Times-Roman-Bold` → `Times-Bold`). Fixed |
| 6 | Performance | `cProfile` at scale 0.2 | 54 s under the profiler on a cold machine; hot spots: `strptime` and PNG encoding. Switched to `fromisoformat` and `compress_level=1`. Warm full generation now about 5 s (first cold run about 70 s) |
| 7 | History volume matches assumption A1 | generation counts | First run 4,022 cases (seasonality multipliers averaged 1.033). Normalised to average 1: 3,872 (A1 × 12 = 3,840) |
| 8 | Lint and types | `ruff check`, `ruff format`, `mypy` (strict, 24 files) | 19 lint findings fixed (long lines, en dashes; S311 allowed for seeded generation; `RUF001` allowed on one Turkish name); 14 mypy errors fixed (covariant `Sequence`, misplaced ignores after formatting, reportlab has no stubs) |
| 9 | Full suite | `scripts\test.ps1` | Exit 0: **151 passed**, coverage **97%** (gate 70%), about 27 s including a full generation in a temp folder |
| 10 | Reproducibility | `scripts\data.ps1 -Action generate` twice | Manifest SHA-256 identical (`883095…6294`) |
| 11 | Clean removes regenerated data only | `scripts\data.ps1 -Action clean` | `seed_data/v1` removed; `benchmarks/datasets/v1/manifest.json` kept |
| 12 | Verify against the committed manifest | `scripts\data.ps1 -Action verify` | `verify: identical` |
| 13 | Split sizes and held-out composition | `tests/test_generator.py` | dev 100, validation 30, held-out 80, stress 30, fairness 40; held-out controls 20, every defect ≥ 2 (D24, D25 ≥ 3) |
| 14 | Documents match ground truth (one per type, opened) | viewed `ATT-DV-048-1.png`, `ATT-DV-004-1.pdf`, `ATT-DV-018-1.eml` | All fields match `labels/documents.jsonl` (confirmation, dates, member, totals); the receipt shows its planted crop, rotation and speckle |
| 15 | Day-one analysis | `python -m evaluations.discovery_analysis` | 3,872 cases, 1,057 failures (27%). **First version overstated the non-AI share (79%):** it counted D16 as partly fixable by B because it read the catalog's "Partial" cell, while catalog §11 says D16 is C-only. Now read from §11: **61% predicted fixable without AI, 21% AI-only, 9% split** (D18, D22). Committed reports equal a regeneration from the data (test) |
| 16 | Label-review sheet | open `review-sheet.csv` | 30 rows, template columns, strata 6/6/2/5/6/5, held-out rows within 10–20 (test) |

## Milestone 2 (2026-10-28)

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Property time zones in existing stages | `grep` over the cloned repos | Mountain Lodge's shuttle serves Asheville (AVL) in stage 1; Beach Resort is near Miami; stage 6 uses `America/New_York`. Both properties are Eastern time, so D04 became "UTC read as local" |
| 2 | Drafts shown to the owner before commit | — | Owner asked for a summary by intervention class and a restatement of choice 1, then approved with one change (A as-is variant) |
| 3 | Pre-registration content pinned | `uv run pytest tests/test_preregistration.py` | 7 passed |
| 4 | Pre-registration commit | `git commit` of catalog, hypotheses, decisions, matrix rows, test | `1f8b8e6`; no arm-B or arm-C code exists in the repository at this commit |
| 5 | Discovery docs test, first run | `uv run pytest` | 2 failed. `docs/legacy-discovery.md` named the category "known functionality" only in lower case (heading fixed). `docs/kpi-tree.md` had the phrase but wrapped over two lines: **a measurement problem**, fixed by matching with line breaks ignored |
| 6 | Full suite | `uv run pytest -q` | 108 passed |
| 7 | Completion scores | `uv run python scripts/matrix_scores.py` | 356 requirements; scores in `docs/implementation-status.md` |
| 8 | Full offline checks on Windows | `powershell -ExecutionPolicy Bypass -File scripts\test.ps1` | Exit 0: ruff clean, mypy clean, **108 passed**, coverage 97% (gate 70%) |
| 9 | Mermaid diagrams render | — | **Not checked**: no renderer installed; code fences checked closed by a test. To check on GitHub once the repo exists (registers PR-09) |

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
