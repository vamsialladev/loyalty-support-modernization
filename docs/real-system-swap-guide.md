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
| Synthetic data generator | Exports or APIs from the loyalty platform, PMS, posting queue, CRM | Canonical model + per-customer mapping file | Planned (M3) |
| Mock customer API | The loyalty platform and PMS APIs | Adapter interfaces + versioned OpenAPI contracts | Planned (M4) |
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
