# Service level objectives (proposed)

Spec F.1; OPS-06; ADR-0085. **Proposed, not measured.** Nothing here is an availability result: the only measured
numbers are from a local laptop (`performance/reports/2026-11-14-local.md`), and **a local test proves no production
availability.** A customer's sponsor agrees these at handover; until then they're starting points, built on Stage 5's
SLO template (`hotel-ai-handoff`, REUSE-05) with this system's own targets.

## Proposed objectives
| Objective | Indicator (how it's measured) | Proposed target | Window | Measured so far |
|---|---|---|---|---|
| Console and API available | Share of `/readyz` probes and API requests answered without 5xx, at the load balancer | 99.5% | 30 days | Not measured (no hosted deployment) |
| Reads are fast | p95 latency of `GET` API requests | under 500 ms | 30 days | Local only: 78–160 ms at the baseline stage, 340–918 ms at x4 |
| Investigations complete | Share of investigations that finish (a result or a stated stop) within 2 minutes of starting | 99% | 30 days | Local only: 155 of 155 at baseline, p95 1.9 s |
| Queue is current | Age of the oldest waiting job | under 5 minutes, 99% of the time | 30 days | Local only: at most 9 s |
| Reconciliation settles | Share of "execution unknown" adjustments settled within 1 hour | 100% | 30 days | Tested (ADR-0061), not measured hosted |
| No double credit | Duplicate credits for one stay | 0 | always | Enforced by a unique index (0007) and idempotency keys; tested |

## Error budget
At 99.5% availability, about 3.6 hours a month. When the month's budget is spent, releases stop except fixes, and
the next release must pass the release gate and the full CI.

## What these need first
- A hosted environment (AWS reference path or the chosen host) with the load balancer's metrics.
- The alert rules (`observability/grafana/alerting/rules.yaml`, or CloudWatch on AWS) pointed at a real contact
  point.
- Two NAT gateways and a Multi-AZ database in production, for 99.5% to be credible (`infrastructure/terraform/aws/`).

## Kept apart on purpose
Measured results live in `performance/reports/` and `docs/verification-log.md`; this page only proposes. No page
in this repository claims an availability figure.
