# RFCs

One short RFC per design-heavy milestone (PURP-05): **M6** approvals, idempotency and reconciliation; **M8** AI loop
and harness; **M10** benchmark design; **M11** protocols. Written before the code, in plan mode, and linked from the
ADRs they produce.

| RFC | Title | Milestone | Status |
|---|---|---|---|
| [RFC-0001](RFC-0001-write-path-integrity.md) | Approvals, idempotency, reconciliation and durable jobs | 6 | Accepted 2026-11-04 |

## Template

```
# RFC-<n>: <title>
Status: draft / accepted / superseded      Milestone:      Author:      Date:

## Context
What problem, which requirement IDs, what constraints (spec Parts).

## Options considered
| Option | Pros | Cons | Cost |

## Decision
What we'll build and why this option.

## Risks
What could go wrong, how we'd notice, what we'd do.

## Rollout
How it ships safely (flags, migration order, rollback).

## Open questions
What we don't know yet, and who decides.
```
