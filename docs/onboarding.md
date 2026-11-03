# Onboarding: your first day on Stage 9

> **Early draft**, updated at the end of every milestone (project purpose, PURP-03). Written for a newly joined
> engineer. If something here is wrong or missing, fixing it is a good first pull request.

## 1. What this project is
A simulated client engagement for a fictional hotel group's loyalty team: members write "my points are missing", and
the project builds and measures three ways to handle it: the legacy tool (arm A), an improved non-AI tool (arm B)
and an AI-assisted tool (arm C), all with a supervisor approving every points adjustment. All data is synthetic.
Start with `README.md`, then `docs/project-purpose.md`.

## 2. How to run it today

```powershell
uv sync
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

```powershell
uv run python -m app.preflight --profile portfolio
```

On macOS/Linux use `make test` and `make preflight`. No API key is needed for anything offline.

## 3. Where things live

| Path | What |
|---|---|
| `docs/MASTER-SPEC.md` | The binding specification. Read the Part for your task |
| `CLAUDE.md`, `AGENTS.md`, `.cursor/rules/` | Rules every contributor and coding assistant follows |
| `docs/requirements-matrix.md` | Every requirement with tier, milestone and status. Pick work from here |
| `docs/decisions.md` | ADRs: why things are the way they are |
| `docs/legacy-defect-catalog.md`, `docs/hypotheses.md` | Pre-registered experiment design. Don't edit without a change-log entry |
| `app/preflight.py` | Configuration readiness check (never prints values) |
| `app/env_leaks.py` | Finds `.env` secret values in tracked files |
| `scripts/matrix_scores.py` | Completion scores counted from the matrix |
| `tests/` | Every check above has a test |

## 4. Why the key decisions were made (read these ADRs first)
- ADR-0019: AI may interpret and explain; eligibility, points, approval and execution stay deterministic.
- ADR-0016 and ADR-0018: why the defect catalog and hypotheses were committed before any arm existed, and why an
  "A as-is" variant runs without the safe write path.
- ADR-0014: why preflight fails loudly instead of falling back to the mock provider.
- ADR-0005: why this isn't on free Streamlit hosting like the other stages.

## 4a. The data layer (Milestone 3)

**What it is.** A deterministic generator (`seed_data/generator/`) builds a synthetic world (members, stay records,
points ledger, posting queue), 280 benchmark cases with ground-truth labels, a 12-month legacy history, and folio
PDFs, receipt images and OTA emails. Same seed, same bytes.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\data.ps1 -Action generate
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\data.ps1 -Action verify
```

| Where | What | Committed? |
|---|---|---|
| `seed_data/v1/` | What the customer's systems hold (the mock API reads it from Milestone 4), plus history and documents | No: regenerate with `-Action generate` |
| `benchmarks/datasets/v1/<split>.jsonl` | What an arm receives: the request(s) only | Yes |
| `benchmarks/datasets/v1/labels/` | Ground truth and the planted facts | Yes, but **the app must never read it** (a test enforces this) |
| `benchmarks/datasets/v1/manifest.json` | Checksums of every generated file | Yes |
| `policies/hg-demo/` | The written policy; rule parameters are in each file's front matter | Yes |
| `config/customers/hg-demo.yaml` | How this customer names its fields; how a blank channel is derived | Yes |

**How a label is made (ADR-0029).** Each scenario builder plants facts and says what the right outcome is;
`evaluations/labeler.py` recomputes the label from those facts and the policy files. If they disagree, generation
stops. That check has already caught one builder error (a multi-stay case over the supervisor limit).

**Why the app can't see labels.** If any arm could read expected answers, the benchmark would measure nothing. Labels
live only under `benchmarks/datasets/v1/labels/`, and `tests/test_generator.py` fails if `app/` mentions it.

**First task in this layer.** Add a variant to an existing scenario (for example a D17 case where the confirmation
number has an extra digit): change its builder in `seed_data/generator/scenarios.py`, regenerate, and see whether
the labeler agrees. Then explain what the manifest diff tells you.

## 4b. The local stack (Milestone 4)

**What runs.** Three containers (`docker-compose.yml`): Postgres 16 with separate databases and roles for the app
and the mock customer systems; the mock customer API (a synthetic loyalty platform + PMS, port 8020); the app
placeholder (health and readiness only, port 8010). All ports bind to 127.0.0.1.

**First run.**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update-local-env.ps1
```

```powershell
uv run python -m app.preflight --profile portfolio
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action up
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action seed
```

Then open http://127.0.0.1:8020/docs (the mock API's contract, with the customer's field names) and
http://127.0.0.1:8010/readyz. `-Action reset-demo` reloads the data; `-Action clean` deletes the database volume.

**How the app talks to a customer system.** Only through `app/ports/customer_systems.py`. The adapter
(`app/adapters/mock_customer_api.py`) maps the customer's field names to canonical records with
`customer_shapes` and the customer file in `config/customers/`, and turns every failure into a typed error.
Remember three rules: reads retry only transient failures; **a write that times out is never retried blindly**
(`UncertainOutcome`: look it up by idempotency key first); half a ledger is an error (`PartialResult`), never a result.

**Testing failures.** With `MOCK_API_FAULTS=true`, send `X-Mock-Fault: <name>` (see `mock_customer_api/faults.py`);
with `MOCK_API_SIM_CLOCK=true`, send `X-Sim-Time` to see the world at a case's request time. Both stay `false` in your
`.env` and are refused in public demo mode.

**Checks.** `tests/test_mock_api.py` runs everything in-process on SQLite (no Docker). `scripts\compose_check.ps1`
builds the images, brings up a throwaway stack (its own env file and project name, never your `.env` or volume),
seeds it, runs live checks and the real-Postgres tests, and tears it down.

**First task here.** Add a fault (for example a 502 from a proxy) to `faults.py`, handle it in the adapter, and add a
contract test. Then explain whether a 502 after a write is safe to retry.

## 4c. The legacy console, arm A (Milestone 5)

**What it is.** The "before" picture: a credible legacy support tool that a supervisor-approved adjustment goes
through end to end. It is competent; its only weaknesses are the pre-registered defects, each one mapped to a file
and a test in `docs/legacy-discovery.md` §2a. Read that table before changing anything in `app/arms/legacy/`.

**Run it in the browser.**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update-local-env.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action up
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action seed
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action demo-cases
```

Open http://127.0.0.1:8010 and sign in as `agent.ana` with the `DEMO_USER_PASSWORD` from your `.env` (open the file
yourself; no tool prints it). For evidence "as of" each request's date, set `MOCK_API_SIM_CLOCK=true` in `.env` and
run `-Action up` again; the banner then shows each case's simulated time.

**Walk one case (a K01 control).** Open the oldest case, "Start work", then use the four screens in the case
navigation: Member search (exact name and email, or member number) → Attach; Stay search (exact confirmation) →
Attach; Ledger (tick "Show older entries" if the stay is more than 90 days old) → Attach; Policy search ("missing
points") → Attach. The rules checklist on the case page now says `adjust` with the points. Request the adjustment,
sign out, sign in as `supervisor.sam`, open Approvals, approve, execute. The case ends `Resolved` with the
platform's adjustment ID.

| Path | What |
|---|---|
| `app/arms/legacy/` | Arm A: rules config loader, checklist, the four screens, keyword index, intake routing |
| `config/legacy/hg-demo-legacy-rules.yaml` | The legacy configuration, out of date exactly where the catalog says |
| `app/services/cases.py` | Case workflow every arm shares (intake, evidence, notes, decisions) |
| `app/services/write_path.py` | The shared write path: approval, execution, reconciliation (thin until Milestone 6) |
| `app/services/sessions.py`, `app/adapters/local_demo_identity.py` | Sign-in, sessions and CSRF (ADR-0045) |
| `app/web/` | The Jinja2 + HTMX console; `static/vendor/README.md` says where htmx came from |
| `app/persistence/models.py`, `migrations/versions/0002_*` | The app's business tables (ADR-0046) |
| `benchmarks/agents/legacy_scripted.py` | The scripted legacy agent, "scripted, not human timing" (ADR-0048) |
| `tests/browser/test_legacy_e2e.py` | The Playwright end-to-end test (Appendix C, Milestone 5) |

**Existing volume from an earlier milestone?** Your data is kept; you don't need `-Action clean`. Run these in order:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update-local-env.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action up
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action seed
```

`up` rebuilds the images; each service migrates its own database as it starts, and `up` then reports `stack: ready` or
the actual cause (ADR-0052). `seed` is safe to repeat: it migrates, creates or resets the demo accounts, and prints
`mock data already loaded, skipped` when the mock API has data. To reload the mock data on purpose use
`-Action reset-demo`. The compose check runs this path on every run.

**Rules to remember.** The browser only sends record numbers; the server re-reads every record before attaching it.
The agent never types an amount. A supervisor never decides on their own request, and the server checks that, not
the template. A write that times out goes to `Execution unknown` and is looked up by key before anything else.

**First task here.** Add a "Rate code" column to the ledger screen's attached-evidence summary, with a test. Then
explain why adding a nickname list to `screens.search_member` would be wrong *in arm A* (hint: D18, and what the
benchmark would then measure).

## 5. Common failure modes so far
- **`ModuleNotFoundError: app`** when running pytest outside `uv run`: use `uv run pytest`.
- **Preflight says NOT READY:** expected with an empty `.env`; it lists exactly which settings are missing.
- **A test about the matrix fails:** a row cites a test that doesn't exist, or uses an unknown status label.
- **`labeler (...) != builder intent (...)` during generation:** a scenario builder and the policy disagree. Read
  the policy section first; the labeler is usually right.
- **`test_committed_manifest_is_reproduced` fails:** generator output changed. If the change is intended, regenerate
  and commit the new manifest with a reason; if held-out labels changed, that is a new dataset version.
- **`docker compose` says a variable is required:** run `scripts\update-local-env.ps1`; it adds only missing
  values and never changes yours. Preflight then shows which settings are still missing.
- **Compose warns "variable is not set" but preflight shows it set, or a URL is "invalid format":** a `.env`
  line uses `${NAME}` above the line that defines `NAME`, and `.env` is read top to bottom. Preflight names the
  line; `scripts\update-local-env.ps1` moves the definition up. `stack.ps1` refuses to run until it's fixed.
- **The mock API's `/readyz` says `not_seeded`:** run `scripts\stack.ps1 -Action seed` (generate `seed_data/v1`
  first if the seed reports `seed_data_missing`).
- **Port 5432, 8010 or 8020 already in use:** another stack (or the compose check with `-Keep`) is running; stop it.
- **A Postgres test shows SKIPPED:** `TEST_MOCK_API_DATABASE_URL` isn't set; the compose check sets it on its own stack.
- **Generation feels slow:** the first run on a cold machine took about 70 s (later runs about 5 s). Use
  `--scale 0.1 --no-documents` while iterating.
- **Sign-in says the username and password don't match:** run `scripts\stack.ps1 -Action seed` after
  `DEMO_USER_PASSWORD` is in `.env`; the seed creates the four demo accounts (it says "skipped" if the variable is
  missing).
- **`up` says the stack is not ready:** the line above the error names the cause (a failed migration, a changed role
  password, a slow start). A password message means `.env` no longer matches the volume: role passwords are stored when
  the volume is created. `scripts\stack.ps1 -Action logs` shows everything.
- **A case was closed by mistake:** there is no reopen until Milestone 6. Open a new case with the same details from
  "New case"; the closed one stays as the audit record.
- **The queue is empty:** run `scripts\stack.ps1 -Action demo-cases`.
- **"Request refused: the form expired":** the page's CSRF token belongs to an older session (you signed in again
  in another tab). Reload the page.
- **The checklist says "Ledger view attached, covering the checkout date: Fail":** the 90-day view starts after the
  stay's checkout; tick "Show older entries" and attach again (ADR-0050).
- **A browser test shows SKIPPED:** Chromium isn't installed; run `uv run playwright install chromium`.
- **"Customer system error" in the console:** the mock API is down or the token differs; check
  `http://127.0.0.1:8020/readyz` and `scripts\stack.ps1 -Action logs`.

## 6. First tasks to try
1. Run the checks and read the preflight output for each profile.
2. Pick one `Planned` row in the matrix and find where the spec defines it.
3. Read one ADR and write down what would make you reverse it.
