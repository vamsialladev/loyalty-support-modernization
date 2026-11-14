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
| Accessibility check | axe-core through `axe-playwright-python`, in the browser suite | Python dev dependency, offline | None | The console's pages, synthetic data | Exercised (M7) | Keyboard and label tests remain |
| Model provider | Anthropic Python SDK behind `app/ports/model_provider.py`; a mock by default | API key in the owner's `.env`, worker only | Costs money per call: the owner's go-ahead and caps | Redacted request text, summaries, excerpts | **Exercised live in M10:** smoke test, dev, validation, held-out × 3, stress × 3, fairness, ablations. $1.83 of a $5 cap | The case keeps arm B's result |
| PDF text | `pypdf` | Python dependency, offline | None | Attached documents, synthetic | Exercised (M8) | The document goes to a person |
| Routing baseline | scikit-learn | Python dev dependency, offline | None | Dev and validation requests, synthetic | Exercised (M8); not shipped | Rules stay |
| Enterprise sign-in | Keycloak 26.4.2 (local, Docker) with PyJWT 2 for token checks | `docker-compose.oidc.yml`, `scripts/oidc_check.ps1`; synthetic users only | None; local | Synthetic names and groups | Exercised (M9): 7 of 7 in a real browser | Local demo sign-in |
| Secret scan before pushing | gitleaks in Docker, locally, as well as in CI | `docker run ... gitleaks git /repo --redact` | None | Git history (redacted output) | Exercised (M6): run before every push since CI flagged a false positive on PR #7 | CI still runs it |
| AI runtime | Claude API (mock first) | Provider interface (M8) | `ANTHROPIC_API_KEY` in `.env` | Minimised, redacted case context | Available; smoke test passed. Spending capped at $5 total (`evaluations/spend.py`) | Mock provider; live results reported as NOT RUN |
| Independent code review | Codex | Owner's CLI in a separate checkout; `docs/exercises/codex-reconciliation-review.md` | Owner's OpenAI account and spending limit | Repo files (synthetic only); never `.env` | Prepared, not run: **Manual step required** (M6 kit; Appendix G allows M6 or M13) | Claude Code's review and the tests stand alone; the exercise stays marked as not run |
| Collaboration, tracking, prototyping, review | Miro, Monday.com, bolt.new, CodeRabbit, Cursor | See `docs/tool-access-matrix.md` | Owner logins / tokens | Synthetic project info only | Planned (M15) | Import files and documented steps; marked Blocked |
| Protocol SDKs | `mcp` 2.3.0, `a2a-sdk` 1.3.0, `ag-ui-protocol` 1.0.0 | Python packages in the `protocols` group | None | Synthetic case data | Exercised (M11): every protocol test uses them; audited before locking | The core app doesn't import them; protocols stay off |
| Protocol access tokens | Keycloak 26.4.2 (local, Docker) | OIDC discovery and JWKS from the issuer's host; client credentials | Local admin password (generated per run) | None: machine clients and scopes only | Exercised (M11): `scripts\protocol_token_check.ps1`, 9 of 9 | Offline tests sign their own tokens |
| MCP independent client | MCP Inspector CLI 2.14.0 | `npx`, over Streamable HTTP | The owner's OK to download it (given 2026-11-11) | One synthetic case | **Exercised (M11, 2026-11-12):** pass (`security/evidence/mcp-inspector-run.txt`) | Same-SDK tests only |
| MCP client in daily use | Claude Code | `.mcp.json`, token from an environment variable (`docs/mcp.md`) | The owner's own Claude Code config | One synthetic case | Planned: owner step | — |
| A2A independent peer | A2A TCK (`a2aproject/a2a-tck`) | Cloned at `70f6f73` into a scratch folder, its own locked venv, run against a local specialist | The owner's OK to install it (given 2026-11-11) | Synthetic stays | **Exercised (M11, 2026-11-12):** verified with limitations: 45 of 47 required checks that ran pass, the 2 failures are scenarios rejected by design, auth not tested by the TCK (ADR-0072; `security/evidence/a2a-tck-run.txt`) | Same-SDK tests only |
| AG-UI independent client | `@ag-ui/client` | `@ag-ui/client@1.0.4` in a scratch folder (`--ignore-scripts`), driven by `tests/interop/ag_ui_client.mjs` | The owner's OK to install it (given 2026-11-11) | Synthetic cases | **Exercised (M11, 2026-11-12):** pass, 4 runs (`security/evidence/ag-ui-client-run.txt`) | Our browser panel only, which is our own client |
| Telemetry (traces, logs, metrics) | OpenTelemetry SDK 1.45.2; FastAPI and httpx instrumentations; Grafana `otel-lgtm` 0.38.1 locally | OTLP/HTTP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; `--profile observability` | None (local) | Scrubbed spans and JSON logs: no query strings, no personal data, no model content (ADR-0077) | Exercised (M12): `scripts\observability_check.ps1`, 21 of 21 | Nothing exported; log lines still carry trace IDs |
| Security and supply chain | Trivy 0.76.1 (images, IaC), Syft SBOM via `anchore/sbom-action`, GitHub build-provenance attestations | Pinned images and actions in CI | None (public repository) | Images and their package lists | Exercised (M12, ADR-0084) | `pip-audit` and gitleaks still run |
| Infrastructure as code | Terraform 1.17.1, AWS provider 6.71.0 | `scripts\terraform_check.ps1` and CI: fmt, validate, Trivy | None: never planned or applied | Configuration only | Configured: validated, never applied (ADR-0085) | — |
| Load testing | A small async driver on `httpx` (`scripts/load_test.py`) | Against a throwaway Compose stack | None | Synthetic requests | Exercised (M12): `performance/reports/2026-11-14-local.md` (ADR-0083) | — |
| Public demo hosting | Render free web service + Neon free Postgres (option A) | `render.yaml`, `Dockerfile.demo` | The owner's new Render account (one repository) and a new Neon project | Synthetic only | **Manual step required**: ready, not deployed (ADR-0087) | The local stack |

## LLM observability tools (spec L3): adopt, not needed, or revisit at scale
**Documentation only: no trial ran** (the optional trial was skipped; each tool would need an account or a new
service, and this project's needs are met). Facts read from each project's own pages on 2026-11-14.

| | Langfuse | Arize Phoenix | LangSmith |
|---|---|---|---|
| Self-hosting | Open source (MIT, except `ee` folders); "you can self-host it for free"; some add-ons need a license key | Open source, self-hosted; Elastic License 2.0 | Self-hosted and hybrid on the Enterprise plan (custom pricing) |
| Cloud free tier | Hobby: 50k units a month, 30 days, 2 users | AX Free: 25k spans a month, 1 GB, 15 days | Developer: 5k base traces a month, 1 seat |
| Cheapest paid | Core $29 a month (100k units, then $8 per 100k) | AX Pro $50 a month (50k spans, 30 days) | Plus $39 per seat a month (10k base traces) |
| Takes our OTLP traces | Yes: an OTLP/HTTP endpoint (`/api/public/otel`); "aims to be compliant" with the GenAI conventions | Yes: "accepts traces over OpenTelemetry (OTLP)"; its own instrumentation is OpenInference | Not found on the pages read |
| Cloud regions | US, EU or Japan (HIPAA region on Enterprise) | US, EU or Canada | US or EU, or your own VPC on Enterprise |

**What they'd add over what's built:** a trace viewer made for prompts and tool calls, prompt version management,
datasets and online evaluators in one place, and annotation queues. **What's already here:** GenAI spans with tokens,
cost and finish reason (ADR-0077); a frozen benchmark and a release gate on every AI change (ADR-0082); online QA
sampling with a rubric, drift signals and feedback-to-dataset through review (ADR-0078); Grafana dashboards and alerts
(ADR-0080). This project deliberately keeps prompt and response content out of every trace. That content is most of
what these tools display, so sending it would be a data-protection decision first.

**Verdict: not needed now; revisit at scale.** Revisit when there are live model calls in production with enough
volume that people review AI runs every day, or when a customer already runs one of these. Then Langfuse or Phoenix,
self-hosted in the customer's region, would take the same OTLP export with no code change (only the endpoint, and a
deliberate decision on whether any content may be sent).
