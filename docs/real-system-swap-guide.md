# Real-system swap guide

> **Early draft.** Updated at the end of every milestone that adds or changes a mock, a generator or an adapter
> (project purpose, PURP-02). For each synthetic or mock component: what it stands in for, the seam where the real
> system plugs in, what changes, what access is needed, who approves, and the first checks to run. Nothing here
> claims a real integration exists.

## How to read this guide
Every stand-in sits behind an adapter interface or a configuration file. Swapping in a real system means writing (or
configuring) the real adapter, getting the access approved, and running the listed checks, without changing domain
code. The four access types never imply one another (spec B.2): developer-assistant, runtime model, customer system,
deployment.

## Components so far

| Stand-in | Stands in for | Seam (where the real one plugs in) | Status |
|---|---|---|---|
| `.env` + `python -m app.preflight` | The client's secret manager and configuration service | Environment variables; profiles in `app/preflight.py` | Built (M1) |
| Fictional discovery sessions | Real stakeholder interviews | `docs/customer-discovery.md` interview guide | Documentation (M2) |
| Synthetic data generator | Exports or APIs from the loyalty platform, PMS, posting queue, CRM | Canonical model + per-customer mapping file | Built (M3) |
| Mock customer API | The loyalty platform, PMS and CRM APIs | `CustomerSystems` port + adapter; versioned OpenAPI contract | Built (M4) |
| Local demo auth (`app/adapters/local_demo_identity.py`) / local Keycloak | The client's IdP (OIDC, SSO) | `IdentityProvider` port (`app/ports/identity.py`, ADR-0003, ADR-0045) | Local demo adapter built (M5); OIDC planned (M9) |
| Arm A legacy console (`app/arms/legacy/`, `config/legacy/`) | The client's current support tool: its search screens, rules configuration and policy index | Observation of the real tool replaces the modelled limits (ADR-0043) | Built (M5) |
| App case tables (`app/persistence/`) | The client's CRM or case system, if it must stay the system of record for cases | `create_ticket` on the port today; a case-sync adapter if the client requires it | Built (M5) |
| Mock model provider | The approved model endpoint (Claude API or an enterprise endpoint) | Provider interface (ADR-0006) | Planned (M8) |

## Configuration and secrets (Milestone 1)
- **Real system:** the client's secret manager (for example AWS Secrets Manager or Vault) and per-environment config.
- **What changes:** values are injected as environment variables by the platform instead of read from `.env`; the
  `approved` profile is selected; preflight runs as a deployment check.
- **Access needed:** platform team creates the secrets and grants the app's workload identity read access.
- **Who approves:** platform team and security.
- **First checks:** `python -m app.preflight --profile approved` shows READY without printing values; the leak check
  finds nothing in the repository.

## Member, stay, ledger, posting-queue and policy data (Milestone 3)
- **Stand-in:** `seed_data/generator/` writes canonical records to `seed_data/v1/` (members, stay records, ledger,
  posting queue) and policies to `policies/hg-demo/`.
- **Real systems:** the loyalty platform (members, ledger, posting queue, merge map), the PMS (stays, channels,
  partner confirmations, folios), the policy repository.
- **Seam:** the canonical models in `seed_data/generator/models.py` and the customer file
  `config/customers/<id>.yaml` (`field_mapping`, `source_code_channels`, prefixes). A real adapter reads the
  customer's export or API and maps upstream names to canonical ones; nothing downstream changes.
- **What changes:** write a read-only importer (or, from Milestone 4, an API adapter) per source; fill the mapping
  file; convert money to integer cents and timestamps to UTC; keep the property time zone for business dates.
- **Access needed:** read-only exports or API credentials for each source, scoped to the pilot properties and a date
  range; no write access to systems of record. Minimised fields only (names, emails and phones only where identity
  matching needs them).
- **Who approves:** the data owner (each source), security (access path, storage location), privacy/legal (lawful
  basis, retention, data processing agreement with any model provider before data reaches a model), the sponsor.
- **First data-quality checks (before any modelling):** row counts and date ranges per source; null rates
  (especially channel, member number on booking); duplicate profiles (phone + date of birth); merge-map coverage;
  partner-confirmation formats; UTC vs local business dates around midnight; reversal and re-post pairs; posting lag
  distribution; stays with conflicting records. These mirror the defect catalog, so the benchmark can be re-run on
  the customer's data shape.
- **Labels for real data:** a sample labelled by the customer's supervisors against the written policy; the
  reference labeler then serves as a consistency check, never the authority (ADR-0029).
- **Public data option:** none adopted; checklist in `docs/data-sources.md`.

## Customer system APIs: loyalty platform, PMS, CRM (Milestone 4)
- **Stand-in:** `mock_customer_api/` (its own service and database), reached only through the port
  `app/ports/customer_systems.py` and the adapter `app/adapters/mock_customer_api.py`.
- **Seam:** write a sibling adapter (for example `app/adapters/<vendor>_loyalty.py`) that implements
  `CustomerSystems` and raises the same typed errors. Nothing above the port changes. The contract tests in
  `tests/test_mock_api.py` become the acceptance tests for the new adapter (run them against the vendor sandbox).

| Mock endpoint | Typical real system | Contract mapping work | Auth (real) | Limits to plan for |
|---|---|---|---|---|
| `GET /v1/members/{loyaltyId}`, `GET /v1/members?emailAddress=&phoneNumber=` | Loyalty platform member API | Field names and codes in `config/customers/<id>.yaml`; fuzzy search may be a separate endpoint or none | OAuth 2.0 client credentials, scoped read-only | Per-client rate limits; PII returned only with an approved scope |
| `GET /v1/stays/{confirmationNumber}`, `GET /v1/stays?...` | PMS reservation or folio API, often through a central reservations system | Multiple records per stay (corrections) must still come back as a list; partner confirmations may live in a separate field or system | OAuth or API key per property group; often IP allow-listed | Nightly batch exports instead of live APIs are common: then a read-only replica, not live calls |
| `GET /v1/members/{loyaltyId}/ledger` | Loyalty platform transaction history | Pagination style (cursor, page number, date window) mapped to `get_ledger`; reversals and re-posts as transaction types | Same as members | Long histories: page size and date filters matter |
| `GET /v1/posting-queue` | Posting or accrual queue, often not exposed | Frequently missing: may need a vendor extension or a data feed; until then pending postings are unknown, which the policy (v2 §5.1) cannot check | Platform operations scope | May be available only as a batch file |
| `POST /v1/adjustments` (Idempotency-Key) | Loyalty platform "manual credit" or "goodwill points" API | Confirm the vendor honours idempotency keys and for how long; if not, the app needs its own dedupe and a status lookup before retry | Write scope, separate client from reads, least privilege | Write limits; approval may also be required on the vendor side |
| `GET /v1/adjustments?idempotencyKey=` | Transaction lookup by external reference | Essential for reconciliation (M6): if the vendor can't look up by our reference, store our key in a reference field it can search | Read scope | Lookup lag after a write (eventual consistency) must be tested |
| `POST /v1/tickets` | CRM / case system (e.g. a service desk or CRM case API) | Case fields, status values, attachment upload | OAuth, user-on-behalf-of where possible | Attachment size and type limits |

- **Access needed:** sandbox credentials first, then production read-only, then a separate write credential for
  adjustments, each requested with the access-request template (`docs/governance.md` §4.1).
- **Who approves:** each system's owner (loyalty platform, PMS, CRM), security (network path, credential storage,
  scopes), the sponsor (go-live), and vendor management (API terms, rate limits, data processing).
- **First checks against a real sandbox:** contract tests adapted to the vendor; every failure type in the fault table
  provoked or simulated (timeouts, 429, 503, lost responses); idempotency proven by sending the same key twice;
  lookup-by-reference latency measured; rate limits measured, not assumed.

## Sign-in, the legacy tool and the case system (Milestone 5)
- **Identity.** Stand-in: local demo accounts with argon2id hashes and server-side sessions
  (`app/adapters/local_demo_identity.py`, `app/services/sessions.py`). Real system: the client's IdP over OIDC.
  - **What changes:** an OIDC adapter implements `IdentityProvider` (`authenticate` becomes the code flow, `lookup`
    maps the token's subject to a user row); roles come from IdP groups mapped to `agent` / `supervisor`. Sessions,
    CSRF, the permission rules in `app/domain/roles.py` and every service stay the same.
  - **Access needed:** an app registration (client ID, secret or certificate, redirect URI), the group claims for the
    two roles, and a test tenant with one agent and two supervisors (separation of duties needs two).
  - **Who approves:** the identity team and security; the support lead confirms who holds which role.
  - **First checks:** the role tests in `tests/test_console_web.py` against the IdP's test users; the requester
    still cannot approve when both accounts are supervisors.
- **The legacy tool itself (arm A).** In a real engagement arm A is not built: it is the client's existing tool,
  observed. Stand-in: `app/arms/legacy/` with `config/legacy/hg-demo-legacy-rules.yaml` and a frozen keyword index.
  - **What changes:** record what the real tool's searches, rules configuration and policy index actually do (screen
    recordings, a configuration export, a sample of searches); the scripted agent's reading policy is rewritten from
    those observations and the benchmark runs on the client's data shape. Any difference from the modelled defects
    is logged as a new experiment (spec F9).
  - **Access needed:** read-only access to the support tool for an observer, a configuration export from its
    administrator, and permission to time a sample of real cases (timing protocol, E.7) with consent.
  - **Who approves:** the support lead and the tool's owner; privacy for any recording of real cases.
- **Cases and tickets.** The app owns its case tables; messages to members go out as tickets through the port
  (`create_ticket`). If the client's CRM must remain the system of record for cases, add a case-sync adapter that
  mirrors status changes to it; the write path still runs here.
- **Starter kit vs customer-specific.** Reusable: the console shell (banner, CSP, CSRF, sessions), the
  `IdentityProvider` port, the case workflow and event log, the `WritePath` protocol, the scripted-agent pattern.
  Customer-specific: the legacy rules file, the keyword index, the scripted agent's reading policy, intake routing.

## Policies, the write path and the worker (Milestone 6)
- **Policies.** Stand-in: fictional Markdown files in `policies/<customer>/`, loaded at their stated status, then published
  through the Configuration page.
  - **What changes:** a real customer's policy owner supplies the text. Rule values go in the front matter by hand, reviewed
    by that owner: nothing extracts rules from prose. If their policies live in a CMS, add a loader that produces the same
    document format. The rule fields in `policy_publishing._RULE_CHECKS` and the engine are the contract.
  - **Access needed:** read access to the policy source; a named owner for each document.
  - **Who approves:** the policy owner and the business owner; a second person for publishing if their governance requires it.
  - **First checks:** write their golden cases with the policy owner, from real past decisions (with consent), before any
    version is published.
- **The real platform's write API: the questions that decide whether this design holds.** Ask them before relying on it:

| Question | Why it matters here | If the answer is bad |
|---|---|---|
| Does the credit API honour an idempotency key, and for how long? | Same-key retries rest on it | Shorten our retry horizon below it. With no keys at all, a retry after a lost response can't be safe: stop at `Execution unknown` and have a person check |
| Can a transaction be looked up by our reference? | Reconciliation rests on it | Store our key in any searchable reference field. If nothing is searchable, reconcile by reading the ledger and matching stay and amount, with a person confirming |
| How long can a lookup lag after a write? | Sets `settle_seconds` (today an assumed 60) | Measure it in the sandbox. Raise the window to well past the worst case seen |
| Does a `200` mean committed? | The outcome table assumes it | If it can mean "accepted", treat it as uncertain and reconcile |
| Can a credit be conditional on the ledger's state? | Would close the gap between re-check and submit (RFC-0001) | Usually no: the gap stays a stated risk, with its size measured by the over-credit rate in a pilot |
| Are write rate limits separate from read limits? | Re-checks spend read quota | A per-customer limiter |

- **Job queue.** Stand-in: none needed; it's the real one, a table in the app's Postgres. If a customer mandates a queue product,
  `jobs.py` is the seam: the handlers don't know where jobs come from. Keep enqueue transactional with the state change, or add
  an outbox (Stage 10's territory).
- **Database roles.** The owner and runtime roles (ADR-0058) map to separate secrets in a real secret manager. Only the release
  step gets the owner's. **Who approves:** the DBA or platform team, and security.
- **Kill switch.** It's the real one. **Who holds it:** decide with the customer who the administrators are and who is on call,
  and put it in the incident runbook (M13). Note the stated limit: one submission per worker can land after it's off.
- **Starter kit vs customer-specific.** Reusable: `jobs.py`, `worker.py`, `approval_binding.py`, `kill_switch.py`, the four-step
  execution, the outcome table, `app-owner.sql`, the publishing flow. Customer-specific: rule fields and golden cases, policy
  text, `settle_seconds` and approval expiry, each arm's `ArmReview`, the adjustment's business fields.

## Arm B on a real platform (Milestone 7)

| What arm B assumes | Mock API | Ask a real vendor | If they don't have it |
|---|---|---|---|
| Search members by family name | `familyName`, ignoring case and accents (contract 1.1.0) | Is there a name search? Is it exact, and is it rate-limited? | D13 and D18 fall back to asking the member |
| Find a stay by partner confirmation | `partnerConfirmation` | Is the OTA's number indexed? | D05 stays unfixed: ask for the hotel's number |
| A posting queue feed | `/v1/posting-queue` | Is there one? How late can it be? | D06 can't be seen: wait longer before crediting |
| Reverse lookup of merged numbers | `merged_into` on a member | Can we follow merges both ways? | Only stays that carry the old number find it |
| Several reads per investigation | No limit | What's the rate limit? Is there a claim-lookup call? | Cache within one investigation; check the invalidation first |

**Customer-specific (a new customer changes these):** `config/conventional/<customer>.yaml` (nicknames, synonyms),
`config/customers/<customer>.yaml`, the `PROMPTS` wording, the language lists in `app/arms/conventional/signals.py`.

**Starter kit (reusable as they are):** the two-identifier rule, the group limit under row locks, the consolidated evidence pattern,
the override log, the JSON API's problem documents, the arm fence test.

## The model provider and documents (Milestone 8)

| Part | Here | For a real engagement |
|---|---|---|
| Model provider | `app/ports/model_provider.py`: mock, scripted, Claude | A sibling adapter (Bedrock, for example, in M12). Must pass the same tests, including strict tool arguments |
| Data sent to the provider | Redacted free text, summaries, excerpts | **Check the customer's data agreement and the provider's retention terms first.** Nothing real has been sent |
| Spending caps | `ai_spend`, in the database | Also set a limit in the provider's own console |
| Documents | Text-layer PDFs and emails by rules; vision through the provider | Real scans need OCR: install Tesseract or a cloud OCR, and measure it. Real layouts need new rules |

**Customer-specific:** `config/prompts/`, `config/ai/`, document field rules. **Starter kit:** the loop, the stop conditions and their tests, the validation shape, the harness tables, the idea of a fence around each baseline.

## Identity and machine access (Milestone 9)

| Part | Here | For a real engagement |
|---|---|---|
| Sign-in | Keycloak locally; `AUTH_MODE=oidc` plus `OIDC_*` settings | The customer's IdP (Entra ID, Okta or similar). Discovery does the rest. Run `scripts/oidc_check.py`'s steps against a test tenant first |
| Roles | `oidc.group_roles` in `config/customers/<id>.yaml` | The customer's real group names. No mapped group means no access |
| MFA | **Not enforced here:** a guide in `docs/identity.md` | Enforce it in the IdP, and test it there before claiming it |
| Provisioning | Accounts appear on first sign-in; SCIM documented, not built | SCIM if the customer needs it |
| Machine access | Read-only tokens, shown once | A service identity from the customer's platform, if they prefer |
| Rate limits | Per person and per address, by socket address | Set up a trusted proxy header first, or everyone shares one address |
| Retention | `RETENTION_DAYS`, daily from the worker | The customer's policy. Add backups to the erasure process |

**Customer-specific:** group mapping, retention period, regulatory notes. **Starter kit:** the OIDC adapter and its tests, the rate limiter, the red-team suite's shape, the route-walking test, the `security/` document set.

## Protocols (Milestone 11)

| Part | Here | For a real engagement | Who approves |
|---|---|---|---|
| Token issuer | Local Keycloak, clients created by `scripts/protocol_clients.py` | The client's IdP (Entra ID, Okta, their Keycloak): one client per caller, an audience per protocol service, short token lifetimes | Client's identity team |
| MCP clients | Claude Code (owner step), MCP Inspector | The AI tools the client's staff already use, each with its own client and scopes | Client's security team, per tool |
| Reservation specialist | Our agent over the mock PMS | The reservations team's own agent, or no A2A at all if their API is enough (`docs/a2a-vs-rest.md`) | Reservations team owner |
| Push-notification callbacks | `A2A_CALLBACK_BASES` on loopback | A public HTTPS endpoint behind the client's gateway, on an allowlist | Client's network team |
| AG-UI frontend | The console's panel | The client's own staff UI, if they build one; same endpoint, same session checks | Product owner |

**What changes:** configuration only (issuer, audiences, URLs, scopes). **What doesn't:** the verifier, the tool and
artifact checks, and the rule that no protocol writes.

## Operations and delivery (Milestone 12)
| Piece here | For a real customer | What to change |
|---|---|---|
| Local Grafana (`--profile observability`) | The customer's own collector and monitoring | Point `OTEL_EXPORTER_OTLP_ENDPOINT` at their collector; load `observability/grafana/` there or translate the seven rules to their tool; keep the in-process scrubbing until their collector's redaction passes the same tests (ADR-0077) |
| Security events export (ECS JSON lines) | Their SIEM | Map the ECS fields once (`docs/siem-field-map.md`); stream instead of exporting if they need it live |
| Circuit breakers and backpressure limits | Their system's real failure and rate patterns | Set the thresholds from the pilot's first weeks; share breaker state if several app instances run (ADR-0081) |
| The release gate on the mock | A live release gate | With an approved budget, run the gate on the live model too; keep the mock gate for every pull request (ADR-0082) |
| AWS Terraform (validate only) | Their landing zone | Map onto their modules and accounts; their state backend; apply in a sandbox first (`docs/aws-deploy-setup.md`) |
| The demo's one container (TD-56) | Separate services | Use `Dockerfile.app` and `mock_customer_api/Dockerfile` (the mock replaced by their system's adapter) |
| Systems of record | Their CRM, loyalty platform, PMS, warehouse | `docs/enterprise-integration.md`: the port operations and what each adapter needs |

## The benchmark (Milestone 10)

| Part | Here | For a real engagement |
|---|---|---|
| Cases and labels | A generator, from scenario facts | A customer's real cases, labelled by their people, with reviewers who didn't build the arms |
| Simulated member | `evaluations/member.py` | Real replies in a pilot |
| Simulated supervisor | Approves what the engine proposes | Real reviewers (UAT, Milestone 18), measuring overrides and automation bias |
| Person working an escalation | None | Model one, or measure one: H3 here rests on this |
| Handoff cost, point value, volume | Assumptions | The customer's own numbers. The break-even moves directly with them |
| Spending cap | `evaluations/spend.py`, this project's $5 | The customer's budget, plus a limit in the provider's console |

**Customer-specific:** cases, labels, thresholds, financial assumptions. **Starter kit:** the runner shape, the freeze, the spending guard, kinds of result kept apart, verdicts by code, generated slices, the sensitivity pattern.
