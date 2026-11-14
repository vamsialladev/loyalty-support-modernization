# SIEM field map (security and audit events)

Spec C.10, E7; SEC-20, ENT-31; `app/services/security_events.py`. Every value is from a **simulated engagement with
synthetic data**.

The export is JSON lines, one event per line, with **Elastic Common Schema (ECS)** field names. ECS is chosen because
most SIEMs read it directly or map it in one step (Splunk, Microsoft Sentinel and Google SecOps all document an ECS
mapping). Nothing here was sent to a real SIEM; that needs a customer's tenant (Milestone 15's tool exercises).

    python -m app.services.security_events --since 2026-11-01 --out exports/security-2026-11.jsonl
    GET /api/v1/security/events?since=2026-11-01        (administrators and auditors)

| Field | Meaning | Source |
|---|---|---|
| `@timestamp` | When it happened, UTC | `system_events.at_utc` / `case_events.at_utc` |
| `event.kind` | Always `event` | fixed |
| `event.category` | `authentication`, `access`, `privilege`, `configuration`, `execution`, `budget` (one-item list) | `KINDS` in the module |
| `event.action` | The audit action, e.g. `sign_in_failed`, `kill_switch_changed`, `adjustment_executed` | the audit row's `action` |
| `event.outcome` | `success`, `failure` or `unknown` (an execution whose result isn't known yet) | `KINDS` |
| `event.severity` | 1 info, 2 notice, 3 warning, 4 high | `KINDS` (proposed levels) |
| `event.dataset` | `loyalty.system_events` or `loyalty.case_events` | which table |
| `user.name` | Who acted: a username, or `system-…` for the app itself. **A failed sign-in names no user**: what was typed may be a password | the audit row's `actor` |
| `labels.actor_kind` | `human`, `scripted`, `system` or `service` | the audit row |
| `labels.correlation_id` | Joins the event to its logs and trace (`trace_id` is in the log line with the same correlation ID) | the audit row's detail |
| `labels.case_reference` | The case, for case events | `cases.reference` |
| `labels.synthetic` | Always `"true"` in this project | fixed |
| `service.name` | `loyalty-app` | fixed |
| `loyalty.detail.*` | An allow-list of code fields: `method`, `path`, `kind`, `engaged`, `policy`, `version`, `points`, `stop`, `name`, `username` | the audit row's detail |

**Never exported:** passwords, tokens, reasons and notes typed by people (a kill switch's reason stays in the audit
row), request text, member or stay details. A test plants a password in the username box and a reason on the kill
switch, and checks neither reaches the export (`tests/test_security_events.py`).

**Retention:** audit history is append-only for the app's role (ADR-0058) and is kept as the audit record. Only the
high-volume refusals (`sign_in_failed`, `authorization_denied`, `rate_limited`, `csrf_failed`) expire, after
`SECURITY_EVENT_RETENTION_DAYS` (default 400, at least 30), and only the owner role can delete them:

    docker compose run --rm migrate python -m app.services.security_events --purge

**Alerts** on these events, each with its runbook, are in `observability/` (repeated failed sign-ins:
`docs/runbooks/auth-failures.md`).
