# Verification log

Every check run, with the command, date and result. Newest milestone first. Results are copied from real runs;
nothing here is predicted.

## Milestone 5 (2026-10-29)

All work by Claude Code (Opus 5.5) on the owner-approved plan (decisions D1–D6). No value from `.env` was read or
printed; tests and the compose check use generated throwaway values.

| # | Check | Command | Result |
|---|---|---|---|
| 1 | State before work | `scripts\test.ps1` equivalent (ruff, format, mypy, `pytest -p no:cacheprovider`) | All clean; **211 passed, 13 skipped** (real-Postgres and Docker tests) |
| 2 | Dependencies | `uv add --group api jinja2~=3.1.6 python-multipart~=0.0.32 argon2-cffi~=25.1.0`; `uv add --group dev pytest-playwright~=0.10.0 playwright~=1.64.1` | Resolved and locked (`uv.lock`) |
| 3 | htmx vendored and verified | download `htmx.org-2.0.11.tgz` from the npm registry; compare SHA-512 with the registry's `dist.integrity` | Match; `dist/htmx.min.js` extracted unchanged, SHA-256 `d6fdc75f…f717` recorded in `app/web/static/vendor/README.md` and checked by a test |
| 4 | Chromium for Playwright | `uv run playwright install chromium` | Installed (exit 0) |
| 5 | Frozen keyword index | `uv run python scripts/build_legacy_index.py`, then `--check` | Built from Missing Points Requests v1 and Earning v2 (the policies in force on 2026-03-15), 11 sections; `--check` matches |
| 6 | First in-process smoke of the console | a scratch script driving the routes with TestClient | **Failed first:** every page answered 422 "missing query parameter s". Cause: the dependency aliases were defined inside a function while the module uses postponed annotations, so FastAPI couldn't resolve them. Fixed by moving them to module level. Then DV-001 went New → Resolved with adjustment `ADJ-…` and one 14,840-point `adjustment` entry in the mock ledger |
| 7 | Idempotency key design | review while writing the tests | **Bug found before any test ran:** a key built from the approval's row number repeats after an app database reset, and the mock platform would answer 409. Fixed: the key uses a random ID stored with the approval (ADR-0044) |
| 8 | Workflow and write path | `uv run pytest tests/test_case_workflow.py` | First run: 1 failed. The D20 test picked a case whose out-of-scope item is a noise complaint, which doesn't mention a refund, so the legacy rule correctly left it in the points queue. **The test was wrong, not the rule:** it now picks the refund variant (the routing keyword was not widened, which would tune arm A toward its predictions). Then **17 passed** |
| 9 | Screens on seeded data | `uv run pytest tests/test_legacy_screens.py` | 12 passed; the D18 test was hard-coded to one case, made generic over the three dev D18 cases: **14 passed** |
| 10 | Scripted agent | `uv run pytest tests/test_scripted_agent.py` | First run: 2 failed, both real. (a) The simulated supervisor rejected K01: the stored checklist lines were a tuple and the review expected a list; the checklist is now stored as plain JSON. (b) The English check (three common English words) took "Missing points. Beach Resort, December 16-17, 2025." for another language, an unregistered failure; it now looks for unmistakable Spanish, French, Portuguese or German words, checked on the dev split only (3 of 3 non-English found, 0 of 99 English flagged). The full-dev test passed during (a) because "Rejected" counts as a resting state, so it now also asserts that no adjustment is rejected. Then **8 passed**; all 102 dev contacts end in a resting state, no `system_error` event, no label file opened |
| 11 | Console over HTTP | `uv run pytest tests/test_console_web.py` | **16 passed** (sessions, CSRF, revocation, expiry, deactivation, the requester's forged approve refused, a form "role" ignored, banner and headers on every page, escaping, every visible control) |
| 12 | Boundaries | `uv run pytest tests/test_arm_a_boundaries.py` | **6 passed** (legacy layer pure, `app/` never imports `benchmarks/`, loader never opens labels, migration 0002 = models, htmx hash, no inline script or style) |
| 13 | Playwright, offline | `uv run pytest tests/browser` | **2 passed**: DV-001 through the four screens to 14,840 points, approved and executed by `supervisor.sam`, the ledger shows exactly that adjustment; htmx loaded under the CSP, an HTMX search request was observed, no console errors. The requester sees no Approve button and a forged POST with a valid CSRF token gets 403 |
| 14 | Full offline checks | `scripts\test.ps1` | **Failed first:** `tests/test_generator.py::test_app_cannot_read_labels_or_generator_metadata` (an existing guard) flagged `app/demo_cases.py`, which named the benchmark folder. The guard is right: the loader moved to `benchmarks/intake.py`; the test was not changed. Then exit 0: ruff and mypy clean, **299 passed, 13 skipped**, coverage 92% (gate 70%) |
| 15 | Matrix scores | `uv run python scripts/matrix_scores.py` | 369 requirements; core 25/108, benchmarks 14/64, security 5/55 verified |
| 16 | Compose check next to the owner's running stack | `scripts\compose_check.ps1 -Browser` | The owner's `loyalty` stack holds ports 5432/8020/8010 and another session may use it, so it was **not** stopped. The compose file now takes `DB_HOST_PORT`, `MOCK_API_HOST_PORT`, `APP_HOST_PORT` (defaults unchanged) and the check uses 15432/18020/18010 |
| 17 | Compose check, real Postgres and built images | same | Every step passed (up from an empty volume, migrate, seed incl. demo accounts, `/readyz` ready, live adapter checks, no labels in either image, 9 real-Postgres tests, app role refused by the mock database) **except the browser step, which failed intermittently**: 1 of 3 runs. With full output: the self-approval test clicked "Attach this view" while the HTMX swap to "Show older entries" was still in flight, so it attached the default 90-day view; the checklist correctly refused it (ADR-0050) and "Request adjustment" stayed disabled. **A test race, not an app bug.** Offline it passed 3 of 3 (faster swap) |
| 18 | Fix and re-check | wait for the swapped-in "all entries" view (as the first test already did) and for checklist outcome `adjust` before clicking; `scripts\compose_check.ps1 -Browser` twice | "compose check passed" both times; Playwright 2 passed each time, against real Postgres and the built images |
| 19 | Final offline checks (after the HTTP every-control test and the race fix) | `scripts\test.ps1` | Exit 0: ruff and mypy clean, **300 passed, 13 skipped**, coverage **94.5%** (gate 70%) |

## Milestone 4 follow-up: blank `${NAME}` expansion in the owner's `.env` (2026-10-29)

**Reported by the owner** after running `scripts\update-local-env.ps1` on their `.env`: (1) preflight called
`DATABASE_URL` and `MOCK_API_DATABASE_URL` "invalid format"; (2) `scripts\stack.ps1 -Action up` and `-Action seed`
warned `The "APP_DB_PASSWORD" variable is not set. Defaulting to a blank string.` (same for `MOCK_API_DB_PASSWORD`),
while preflight showed both as set. The stack started and seeding worked. No value was printed or read by hand at
any step; the owner's `.env` was handled only by the script and preflight.

**Root cause (one cause, both symptoms):** the script appended missing keys at the end of the file but rewrote the
URL lines in place, so the URLs used `${APP_DB_PASSWORD}` / `${MOCK_API_DB_PASSWORD}` above the lines defining
them. python-dotenv (preflight) and Docker Compose both expand `${NAME}` in a `.env` file top to bottom, so both
URLs got a blank password. The containers were not affected: `docker-compose.yml` builds their URLs from
`${APP_DB_PASSWORD:?}` itself and never uses the `.env` URL lines. The compose check missed it because it builds a
fresh file from the template, where the order is already right.

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Reproduce on a fake pre-Milestone-4 file (fake values, scratchpad) | old `update-local-env.ps1`, then preflight and `docker compose config --quiet` | Both symptoms reproduced: URL lines at lines 24-25, the appended passwords at 97-98; preflight NOT READY (2 problems, both URLs "invalid format"); Compose printed both "variable is not set" warnings |
| 2 | Did the blank value reach the containers? | `docker compose config --format json` on the same file, lengths only | No: `db` got both role passwords (48 characters each); the `app` and `mock-api` URLs had 48-character passwords |
| 3 | Live roles on the owner's original stack, before any change (read-only) | `pytest tests/test_db_roles_postgres.py` with `TEST_DB_ROLES_CONTAINER=loyalty-db-1` | 3 passed: `loyalty_app` and `mock_api` each have a stored SCRAM-SHA-256 password, and both refuse a blank password over TCP. No role was created with a blank password |
| 4 | Fix | commit `6adbc3b` | Script moves each definition above the first line that uses it (repairs old files too); preflight names a `${NAME}` used above its definition or never defined; compose uses `${NAME:?}` for every secret; `01-roles.sh` refuses blank or short role passwords before `psql` runs; `stack.ps1` stops on Compose's unset-variable warning and gains `-Action verify-roles` |
| 5 | New tests catch the bug | the 9 new offline tests with the four fixed files stashed (old code) | All 9 failed on the old code; all pass on the fix (preflight per-role URL form x3, compose strictness x1, init script refusing blank or short passwords x3, script repair from two starting files x2) |
| 6 | Full offline suite | `scripts\test.ps1` | Exit 0: ruff and mypy clean; **215 passed, 9 skipped** (6 mock-API and 3 role tests need a running stack); coverage 94% |
| 7 | Guard on the owner's unrepaired `.env` | `scripts\stack.ps1 -Action status` | Refused: "Compose would use a blank value for: APP_DB_PASSWORD, MOCK_API_DB_PASSWORD" |
| 8 | Repair the owner's `.env` | fixed `update-local-env.ps1` | "moved above the lines that use them: APP_DB_PASSWORD, MOCK_API_DB_PASSWORD"; nothing added, generated or rewritten; backup `.env.bak` |
| 9 | Preflight after the repair | `python -m app.preflight --profile portfolio` | **READY**; both URLs and both role passwords `set` |
| 10 | Reset the owner's stack (owner approved deleting `loyalty_pgdata`) | `stack.ps1 -Action clean`, `up`, `seed` | Volume removed and recreated (21:09 UTC); `01-roles.sh` ran: `CREATE ROLE` x2, `CREATE DATABASE` x2; all three services healthy; seed: 3,286 members, 6,800 stays, 3,836 ledger entries, 12 queue items; app and mock `/readyz` both ready (each role logged in with its real password) |
| 11 | Roles after the reset | `stack.ps1 -Action verify-roles` | 3 passed (stored SCRAM password for both roles; blank password refused for both); `docker compose config` printed 0 unset-variable warnings; preflight READY |
| 12 | Appendix C again (changed init script and compose check) | owner stack `down` (volume kept), `scripts\compose_check.ps1`, owner stack `up` | **compose check passed**, every step including the real-Postgres step with the new role tests; owner stack back up with its seeded data |

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
