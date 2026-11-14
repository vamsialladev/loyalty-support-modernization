# Data residency and transfer map

Spec E7; ENT-11; ADR-0086. Where each kind of data lives and where it travels. Every value in this project is
synthetic; the map is what a customer's data protection review would check before real data arrives.

| Data | Stored in | Travels to | Region setting |
|---|---|---|---|
| Cases, events, adjustments, approvals, AI run records | The app's Postgres | Nowhere else (backups stay with the database) | The database host's region: `var.region` in `infrastructure/terraform/aws/`, or the Neon project's region for the demo |
| Member and stay records | The customer's systems (the mock customer API here) | Read by the app per case, never copied in bulk | The customer's |
| Text sent to the model | Not stored by this system beyond the run record's codes | The model provider, redacted first (`app/ai/redaction.py`), only what the case needs | Anthropic API: the provider's processing locations under its terms. Claude via Amazon Bedrock: `AWS_REGION` (preflight checks it; configured only) |
| Logs | stdout, collected by the host (CloudWatch on AWS) | The host's log service; the OTLP collector if configured | The host's region |
| Traces and metrics | Not stored by the app | `OTEL_EXPORTER_OTLP_ENDPOINT` if set (local only in this project) | Wherever that collector runs |
| Security event and analytics exports | Files a person writes | Where that person sends them (a SIEM, a warehouse) | The receiving system's |
| Secrets | `.env` locally; Secrets Manager or the host's dashboard | The process that needs each one | The host's region |

## Choosing the region
- **The database and the app:** in the customer's agreed region. On AWS that's `var.region`; on Render and Neon it's
  chosen when the service and project are created (pick the same region for both, to keep latency and transfer
  low).
- **The model:** if the customer requires processing in a region, Claude via Amazon Bedrock in that region is the
  path (`AI_PROVIDER=bedrock`, `AWS_REGION`). It's configured but not built or tested here (ENT-13, blocked).
  Otherwise the Anthropic API's terms decide.
- **Transfers:** member data leaves the customer's system only per case, and only to the app's region. Text reaches
  the model only after redaction, and only for an AI-assisted case.

## What a customer's review still needs
A data processing agreement with each provider, its sub-processor list, and the retention terms for model inputs
(the provider checklist in `docs/enterprise-integration.md`). None is in place here: no real data, no customer.
