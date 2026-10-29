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
| Local demo auth / local Keycloak | The client's IdP (OIDC) | `IdentityProvider` port (ADR-0003) | Planned (M9) |
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
