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

## 4d. Upgrading your own stack to the split database role (Milestone 6, ADR-0058)

From Milestone 6 the app runs as `loyalty_app`, which can't change audit history, and a separate `loyalty_owner` runs
migrations. **A volume from before Milestone 6 needs one new `.env` value and one normal `up`.** Your data stays. Nothing
needs pasting: the first command generates the password, writes it to `.env` and prints only the name.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update-local-env.ps1
```

It should list `APP_OWNER_DB_PASSWORD` under "added from template" and "generated". Check it without printing a value:

```powershell
uv run python -m app.preflight --profile portfolio
```

Then bring the stack up. This starts the database first, splits the role (safe to repeat), migrates as the owner and starts
the app:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action up
```

You should see `stack: ready`. If you ran this before the fix, it stopped at `app database: unreachable`. Running it again on
the fixed code grants the missing right; your data was never at risk.

Then load the initial policy set and the two new demo accounts (`admin.ada`, `auditor.abe`; same demo password):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action seed
```

Check it worked:

```powershell
Invoke-RestMethod http://127.0.0.1:8010/readyz
```

`status` should be `ready`. To test this upgrade path itself, without touching your stack (it builds a volume with the real
Milestone 5 code, under its own project and ports; the compose check runs it too):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\upgrade_check_m5.ps1
```

**To undo the split** on a local volume, if you ever need an older checkout: as the database admin, run `REASSIGN OWNED BY
loyalty_owner TO loyalty_app`. Or start clean with `scripts\stack.ps1 -Action clean`, which deletes the local data.

**To redo case A-000010:** sign in as an agent or supervisor, open the case, and use "Reopen" with a reason of at least 20
characters. Its `case_closed` event stays as the record of the wrong denial. The next close follows the ADR-0054 rules.

## 4e. The write path, in one page (Milestone 6)

Read `docs/rfcs/RFC-0001-write-path-integrity.md` first, then ADR-0055 to ADR-0061.

**What happens when a supervisor clicks Execute:**
1. The web request locks the case, checks the switch and the stored approval, and queues a job in the same transaction.
2. The worker claims it, then re-reads the evidence through the arm's own evaluator and checks the ledger. No lock is held.
3. It locks the case, re-checks, records the attempt and `Executing`, and commits. From here a crash means "unknown".
4. It looks at the switch once more, then submits with a key derived from the approval.
5. It locks the case and records what came back.

**Where things live:**

| Path | What |
|---|---|
| `app/domain/eligibility.py`, `policy.py`, `case_states.py`, `approval_binding.py` | The pure rules. No database, web or HTTP |
| `app/services/write_path.py` | Decide, execute, reconcile. The file to read most carefully |
| `app/services/jobs.py`, `job_handlers.py`, `app/worker.py` | The queue, what the jobs do, and the process |
| `app/services/approvals.py`, `arm_review.py` | Ending approvals; each arm's re-check |
| `app/services/policies.py`, `policy_publishing.py` | Storing, finding and publishing policy versions |
| `app/services/kill_switch.py` | The emergency switch |
| `infrastructure/postgres/sql/app-owner.sql` | The two database roles |
| `tests/test_execution_postgres.py`, `test_worker_postgres.py`, `test_write_path_postgres.py`, `test_audit_postgres.py` | The Appendix C proof. They need a real database |

**Running the real-Postgres tests:** they only run through the compose check, which makes its own throwaway stack and never
touches yours. Don't run it beside `scripts\test.ps1`.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\compose_check.ps1 -Browser
```

**Operating it:**

```powershell
docker compose exec worker python -m app.worker --list-dead
```

```powershell
docker compose exec worker python -m app.worker --requeue 12
```

The kill switch is on the Configuration page; sign in as `admin.ada`. `auditor.abe` reads cases and changes nothing.

**Starter kit vs customer-specific:** see the swap guide's Milestone 6 section.

## 4f. Arm B, in one page (Milestone 7)

**Try it.** Sign in as `agent.ana`, choose **New case**, pick **Arm B**, and describe a request. Or load dev cases:

```powershell
uv run python -m benchmarks.intake --split dev --limit 10 --arm B
```

Open a case and press **Investigate**. The worker does the reading, so **the worker must be running** (`stack.ps1 -Action up` starts it).

**What happens, in order** (`app/arms/conventional/investigation.py`):
1. Who is asking: candidates from the number, the email and the family name. Two identifiers must match.
2. Which stay: exact number, partner number, missing prefix, near match within this member's stays, or an unmistakable date.
3. One read: stay records, ledger on every linked profile, posting queue. This same code runs again for each re-check.
4. The eligibility engine decides (`app/domain/eligibility.py`). Rules on the message can only send it to a person.
5. One evidence snapshot and one `recommendations` row are stored. The latest row counts.

**Where to look when something's wrong**

| Symptom | Likely cause | Check |
|---|---|---|
| "The worker has this" never ends | The worker isn't running | `docker ps`, then the worker's log |
| "The investigation couldn't finish" | The customer system refused us | The code on the page; `/admin` for dead jobs; press Investigate again |
| Always `second_identifier` | The message has one identifier | That's the two-identifier rule, not a bug |
| A credit is refused after approval | The facts changed | `invalidated-reason` on the case |
| `test_arm_a_fence` fails | Shared code changed arm A | **Fix the change. Don't regenerate the fence** unless the owner approved a change to arm A |

**Arm B's JSON API** is at `/api/v1`, with the console's session and an `X-CSRF-Token` header. `GET /api/v1/me` gives you the token.
After changing the API, run `uv run python -m app.api.contract --write` and look at the difference.

**The rule to remember:** nothing an agent or a member types can set an amount. The only route to a credit is the engine's own result.

## 4g. Arm C, in one page (Milestone 8)

**Try it offline, for free.** Choose **Arm C** on New case, then press Investigate. `AI_PROVIDER=mock` is the default. Everything the mock writes starts with `[MOCK]`, and **says nothing about any real model.**

**Read in this order:** RFC-0002, `app/ai/loop.py`, `app/ai/tools.py`, `app/ai/validation.py`, `app/services/assisted.py`, then `docs/ai-engineering-matrix.md`.

**To turn on a real model** (costs money, so it needs the owner's go-ahead): set `AI_PROVIDER=anthropic`, `FEATURE_LIVE_AI=true`, `ANTHROPIC_MODEL=claude-haiku-5-5`, `ANTHROPIC_API_KEY` and the `LLM_BUDGET_USD_*` caps in `.env`. Only the worker gets the key.

**Where to look when something's wrong**

| Symptom | Likely cause | Check |
|---|---|---|
| `ai_fallback` on a case | The run ended early | The reason is on the page; `ai_runs.stop_reason`; `ai_steps` for the step |
| `unknown_model` | The ID isn't in `config/ai/hg-demo.yaml` | Add it with its price and the date, after comparing it |
| `budget_exhausted` straight away | A cap is reached, or a cap didn't parse (counts as zero) | `ai_spend`; the `LLM_BUDGET_USD_*` values |
| `test_prompt_versioning` fails | The prompt's text changed | Add a new version file; don't edit the old one |

**The rule to remember:** if you're tempted to let the model's output change a decision, put a deterministic check in front of it, and give that check to arm B as well (ADR-0067).

## 4h. Security, in one page (Milestone 9)

**Read in this order:** `security/threat-model.md`, `security/control-matrix.md`, `security/test-results.md`, `security/residual-risks.md`, ADR-0069.

**Try the real sign-in, offline:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\oidc_check.ps1
```

It starts a local Keycloak with synthetic users and signs in through a real browser. Details: `docs/identity.md`.

**Administrator tools** (Admin page, signed in as an administrator): users and deactivation, recovery links, machine tokens, access review export, legal hold, member export and erasure.

| Symptom | Likely cause | Check |
|---|---|---|
| 429 on the console or API | A rate limit | `rate_limits` table; `RATE_LIMIT_PER_MINUTE`. Behind a proxy, everyone shares one address (`docs/known-limitations.md`) |
| 429 at sign-in, even with the right password | 5 failures on that account in the window | It clears when the 300 s window ends; the events are `sign_in_failed` |
| Keycloak user gets no access | No mapped group | `config/customers/hg-demo.yaml`, `oidc.group_roles`. This is on purpose |
| A case "isn't found" that exists | It belongs to another customer | `cases.customer_id` against the person's `users.customer_id` |

**The rule to remember:** every new query that reads a record has to scope by customer. The route-walking test covers access, but it can't see what a query returns.

## 4i. The benchmark, in one page (Milestone 10)

**Read in this order:** `docs/hypotheses.md`, RFC-0003, `benchmarks/reports/heldout/hypotheses.md`, `docs/error-analysis.md`.

**Run a deterministic arm, free:**

```powershell
uv run python -m evaluations.run --arm b --split dev --name my-try
```

**Compare two runs:**

```powershell
uv run python -m evaluations.compare benchmarks/results/deterministic/a-dev benchmarks/results/deterministic/b-dev
```

**Regenerate every report, free, from stored runs:**

```powershell
uv run python -m evaluations.final_report
```

Live runs cost money, need `--budget-usd`, and stop themselves at the owner's cap (`evaluations/spend.py`). Held-out needs `--confirm-frozen`, a clean tree and an unchanged freeze.

| Symptom | Likely cause | Check |
|---|---|---|
| `changed since the freeze` | You changed something an arm depends on | That's a new experiment. Don't re-write the freeze to get past it |
| A number looks too good | It may be a measurement bug | Every bug here was in the measuring. Read the case's stored record, then the arm's trail |
| `spend` stops a run | The ledger's at its limit | `benchmarks/results/live/spend-ledger.jsonl`. It's append-only: never edit it |

**The rule to remember:** look at a result before you believe it, and report the ones that go against you. Every slice where a simpler arm wins is generated, so nothing can be left out.

## 4j. Protocols, in one page (Milestone 11)

**Read in this order:** `docs/protocol-selection.md` (why, and when REST is enough), RFC-0004, `docs/mcp.md`,
`docs/a2a-vs-rest.md`, `docs/protocol-test-results.md`.

**The one rule:** a protocol is a door, not a new room. MCP, A2A and AG-UI reach the same services, permission checks
and audit tables as REST, and none can approve, credit or change a case. With every flag off (the default), the app
is what it was at Milestone 10.

| Protocol | What it's for here | Where | Start (each needs its flag) |
|---|---|---|---|
| MCP 2026-07-28 | AI clients read one case's facts, exactly what arm C's model sees | `protocols/mcp/` | `uv run python -m protocols.mcp.server` |
| A2A 1.0 | The loyalty coordinator asks a reservations agent for stay evidence | `protocols/a2a/` | `... -m protocols.a2a.specialist`, then `... -m protocols.a2a.coordinator --case <id>` |
| AG-UI 1.0 | Watch an arm C investigation live on the case page | `protocols/ag_ui/` | `... -m protocols.ag_ui.server` (the console with the endpoint on) |

**Run the tests, free, offline:**

```powershell
uv run pytest tests/test_protocol_auth.py tests/test_mcp_server.py tests/test_a2a.py tests/test_ag_ui.py
```

**Tokens against a real local Keycloak, free (Docker):**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\protocol_token_check.ps1
```

| Symptom | Likely cause | Check |
|---|---|---|
| MCP or A2A answers 401 to a token that "should" work | Wrong audience: a token for one service isn't accepted by another | The token's `aud` must be that service's URL; `scripts/protocol_clients.py` sets it per client |
| A2A returns `-32009` | No `A2A-Version: 1.0` header: the SDK reads the request as 0.3 | The official client sends it; a hand-written client must too |
| An A2A artifact fails its hash | A number turned into a float on the way (protobuf `Struct`) | `content_hash` compares whole numbers as integers; don't hash raw JSON yourself |
| The AG-UI panel shows nothing | The page refreshed itself and replaced the button | The script uses one delegated listener; check the browser console for CSP errors |

**Customer-specific:** the tool list, field allowlists, scopes, Keycloak clients, which protocols are on. **Starter
kit:** the token verifier, the flag-and-start-command pattern, the G.13 test checklist, "same SDK isn't interop".

## 4k. Containers, profiles and environments (Milestone 12)

**Read:** ADR-0073 (one issuer), ADR-0074 (images and profiles), ADR-0075 (environments).

`docker compose up --build -d` still starts only the default stack (db, mock-api, migrate, app, worker). Add a
profile for more:

| Profile | Adds | Use it for |
|---|---|---|
| `demo` | `demo-seed` (runs `app.seed --dataset demo` once the app is healthy) | A seeded stack in one command |
| `test` | `test-db` (Postgres in memory, port 55432) | `pytest -m postgres` without touching your data |
| `enterprise-identity` | `keycloak` | Sign-in through OpenID Connect |
| `labs` | `keycloak`, `mcp`, `a2a-specialist` | The Milestone 11 protocol services in containers |

```powershell
docker compose --profile labs up --build -d --wait
```

The labs profile needs `KEYCLOAK_ADMIN_PASSWORD` in `.env`; Keycloak refuses to start without it, and nothing else
does. To prove the whole thing works, free and on throwaway ports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\labs_check.ps1
```

**One issuer:** tokens always name `http://127.0.0.1:<KEYCLOAK_HOST_PORT>/realms/hotel`. A container can't reach
127.0.0.1 on your machine, so it fetches keys from `http://keycloak:8080` (`PROTOCOL_TOKEN_FETCH_URL`) and still checks
`iss` against the public issuer.

**Environments:** `config/environments/{local,staging,production}.env` hold the non-secret settings for each.
Secrets never go there. Hosted profiles (`staging`, `approved`) refuse default, test or short secrets, by name only:

```powershell
uv run python -m app.preflight --profile approved
```

**Pre-commit:** `uv run pre-commit install` once per clone; gitleaks then checks every commit (through Docker, same
version as CI).

| Symptom | Likely cause | Check |
|---|---|---|
| `docker compose` stops with "required variable KEYCLOAK_ADMIN_PASSWORD" | An old Compose file, or `extends` from `docker-compose.oidc.yml` | Compose reads every service, even outside the active profiles; this file avoids required variables there |
| MCP in a container answers 421 | The client used a host the server doesn't allow | It allows the host in `MCP_RESOURCE_URL`; use that URL |
| A protocol service in a container answers 503 to every token | It can't reach Keycloak | `PROTOCOL_TOKEN_FETCH_URL` must be `http://keycloak:8080/realms/hotel`, and Keycloak healthy |

**Starter kit:** the profile layout, the hardening anchors, the one-issuer pattern, the environment files and the
default-credentials check. **Customer-specific:** which profiles a customer runs, ports, the realm.

## 4l. Operating it: telemetry, reliability, CI, the demo (Milestone 12)
- **See it working:** `scripts\observability_check.ps1` starts the stack with Grafana, makes traffic, and checks the
  traces, metrics, dashboard and alerts (21 checks). To look yourself, start the profile (`docker-compose.yml`, above `otel-lgtm`), open <http://127.0.0.1:3000> (or `GRAFANA_HOST_PORT`) → Dashboards →
  Loyalty support. Each alert names a runbook in `docs/runbooks/`.
- **Logs are JSON** with `correlation_id` and `trace_id`; take a reference from an error page, find the line, open the
  trace in Grafana's Explore. Query strings and personal data never appear (ADR-0077).
- **When the customer system or the model is failing,** a circuit breaker stops calls for 30 seconds and the fallbacks
  take over; when too many investigations wait, new ones get 503 and `Retry-After` (ADR-0081).
- **Before an AI change merges,** the release gate re-runs arm C on the mock: `uv run python scripts/release_gate.py
  --force` (`docs/release-gate.md`).
- **Load:** `scripts\load_test.ps1` (about 10 minutes); the report goes to `performance/reports/`.
- **CI, locally:** `scripts\ci_local.ps1` runs the same jobs, including Trivy on the images; `scripts\terraform_check.ps1`
  checks the AWS Terraform without an account.
- **The public demo:** `PUBLIC_DEMO_MODE=true` gives sign-in buttons (no passwords, no administrator), a daily case cap
  and mock AI. `Dockerfile.demo` runs everything in one container; `scripts/demo_smoke.py <url>` checks it.
- **Rollback:** roll the image back, never the schema (`docs/rollback.md`).

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
- **A Postgres test shows SKIPPED:** the `TEST_*_DATABASE_URL` settings aren't set; the compose check sets them on its own
  stack.
- **Generation feels slow:** the first run on a cold machine took about 70 s (later runs about 5 s). Use
  `--scale 0.1 --no-documents` while iterating.
- **Sign-in says the username and password don't match:** run `scripts\stack.ps1 -Action seed` after
  `DEMO_USER_PASSWORD` is in `.env`; the seed creates the demo accounts (it says "skipped" if the variable is
  missing).
- **`up` says the stack is not ready:** the line above the error names the cause (a failed migration, a changed role
  password, a slow start). A password message means `.env` no longer matches the volume: role passwords are stored when
  the volume is created. `scripts\stack.ps1 -Action logs` shows everything.
- **A case was closed by mistake:** use "Reopen" on the case, with a reason of at least 20 characters. The old events stay.
  If a credit was applied, only a supervisor can reopen it, and the stay can't be credited again.
- **Execute does nothing and the page says "The worker has this":** the `worker` container isn't running. Check
  `scripts\stack.ps1 -Action status`. Nothing is lost; the job waits.
- **A case sits in `Execution unknown`:** the outcome really is unknown. "Check status" asks the platform. "Not found" needs 2
  lookups and 60 seconds before it counts. If its job went dead, it stays here until a person requeues it: that's on purpose.
- **"This approval can't stand":** the evidence or policy changed, or 24 hours passed, or `APP_SECRET_KEY` changed. Check the
  evidence and request again. A new request gets a new approval and a new key.
- **"Adjustments are switched off":** an administrator turned the switch off. Investigation still works. See Configuration.
- **"no single published policy covers a checkout":** the policies aren't loaded, so run `scripts\stack.ps1 -Action seed`; or the
  stay really is before any policy, so escalate.
- **`app database: unreachable` while every container says healthy:** "healthy" for the app means the process answers;
  `/readyz` is what checks the database. The reason is in `scripts\stack.ps1 -Action logs`, after `readiness: database check
  failed`. `permission denied for database "loyalty"` means the role lost `CONNECT`: on the fixed code, `stack.ps1 -Action up` grants it
  back (ADR-0058).
- **The worker is `unhealthy`:** it can't reach the database, or hasn't yet. Its log says `claim failed`, at most about once a
  minute once it has backed off. Nothing is lost: jobs wait.
- **`permission denied` from Postgres in the app's logs:** the app role can't change audit history or the schema, by design
  (ADR-0058). If a migration is what failed, run `scripts\stack.ps1 -Action migrate`, not `alembic` inside the app container.
- **`deadlock detected`:** should not happen. If it does, look for a new `FOR UPDATE` on `cases`: use `key_share=True`
  (verification log, Milestone 6, row 36).
- **"The evidence is incomplete" or "search the member screen first" when closing:** expected (ADR-0054). Attach the
  evidence, or run the search that finds nothing before `deny_not_found`. `deny_other` needs a note of at least 20
  characters and is counted as an override.
- **The queue is empty:** run `scripts\stack.ps1 -Action demo-cases`.
- **"Request refused: the form expired":** the page's CSRF token belongs to an older session (you signed in again
  in another tab). Reload the page.
- **The checklist says "Ledger view attached, covering the checkout date: Fail":** the 90-day view starts after the
  stay's checkout; tick "Show older entries" and attach again (ADR-0050).
- **A browser test shows SKIPPED:** Chromium isn't installed; run `uv run playwright install chromium`.
- **"Customer system error" in the console:** the mock API is down or the token differs; check
  `http://127.0.0.1:8020/readyz` and `scripts\stack.ps1 -Action logs`.

- **Milestone 12's traps:** an alert rule can load and never work (Grafana's datasource plugins failed under
  `cap_drop: ALL`, so the check runs a query through Grafana and makes an alert fire); a metric's unit can rename it
  (`"1"` became `_ratio`, so the check matches names exactly); Postgres can report healthy before it accepts TCP (the
  healthcheck now uses `-h 127.0.0.1`); a guard test you didn't run still runs on CI (run every test that reads
  `docs/` before pushing).

## 6. First tasks to try
1. Run the checks and read the preflight output for each profile.
2. Pick one `Planned` row in the matrix and find where the spec defines it.
3. Read one ADR and write down what would make you reverse it.
4. Read `app/services/write_path.py::execute`, and for each commit ask what happens if the process dies right after it. Then
   check your answers against `tests/test_execution_postgres.py`.
