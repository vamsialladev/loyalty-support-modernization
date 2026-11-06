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
