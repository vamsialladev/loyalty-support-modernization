# Workflow: current and proposed

> Simulated client engagement, synthetic data. Requirement DISC-04. Handling times and costs are **assumptions**
> (`docs/customer-discovery.md` §6, A2–A3), not measurements.

## 1. Current workflow (legacy, arm A)

```mermaid
flowchart TD
    R[Member writes: email, web form or phone note] --> Q[Case lands in the CRM queue<br/>routed by keywords]
    Q -->|"contains 'refund'"| BQ[Billing queue: points claim waits]
    Q --> M[Screen 1: member search<br/>exact member number or exact name + email]
    M -->|not found| ASK1[Ask the member for details<br/>contact +1]
    M --> S[Screen 2: stay search<br/>exact confirmation number]
    S -->|not found| ASK2[Ask for the hotel's confirmation number<br/>contact +1]
    S --> L[Screen 3: ledger, last 90 days<br/>re-posts grouped under later dates]
    L --> P[Screen 4: keyword policy search<br/>index built 2026-03-15]
    P --> RULE[Legacy rule config<br/>current rules applied to every stay]
    RULE -->|eligible| PROP[Agent types notes, proposes points]
    RULE -->|ineligible or channel blank| DENY[Deny]
    RULE -->|too early| WAIT[Tell member to wait]
    PROP --> SUP[Supervisor approves: status flag]
    SUP --> EXE[Manual adjustment in the loyalty platform<br/>no duplicate check, no re-check]
    EXE --> DONE[Resolved]
```

| Step | Who | System | Manual work | Time (assumed) |
|---|---|---|---|---|
| Triage | Queue rules | CRM | Keyword routing; multi-issue messages misrouted | — |
| Find member | Agent | Loyalty platform, screen 1 | Exact match only | 2 min |
| Find stay | Agent | PMS view, screen 2 | Exact confirmation only; partner numbers not indexed | 3 min |
| Check ledger | Agent | Loyalty platform, screen 3 | Read postings; reversals look like gaps; no pending feed | 2 min |
| Find policy | Agent | Keyword search, screen 4 | Stale index; today's rules only | 2 min |
| Decide | Agent | Legacy rule config | Blank channel = ineligible; one property's wait still 30 days | 2 min |
| Notes and proposal | Agent | CRM | Free-text notes of uneven quality | 2 min |
| Approve | Supervisor | CRM status | Approves on trust; nothing binds the approval | 1 min |
| Adjust | Agent | Loyalty platform | Manual; a retry after a timeout is a new adjustment | 1 min |

Median about 14 minutes per case (assumption A2), more for multi-stay requests. Loaded cost about $7.50 per case at
$32 per hour (assumption A3). These figures feed the financial model as assumptions only.

## 2. Proposed workflow (target, spec A.1)

1. **Request** arrives (form fields, free text, optional attachment); stored as data, never as instructions.
2. **Authorized evidence retrieval:** member, stays, ledger (posted, pending, reversed), case history, all filtered
   by the caller's role and customer before anything reaches a model.
3. **Applicable policy** chosen by checkout date in Eastern time.
4. **Deterministic eligibility** with points, reasons and policy references.
5. **Explanation with citations** (arm C drafts it; arm B shows the rule's reasons).
6. **Branch:** clarification (Awaiting information), escalation, proposed adjustment (Pending approval), or no
   adjustment required (credited, pending posting, wait until a date, not checked out, ineligible).
7. **Supervisor approval**, bound to the exact action; the proposer can't approve.
8. **Simulated adjustment** through the mock loyalty API with an idempotency key from the approval, after re-checking
   eligibility and the ledger.
9. **Reconciliation** of uncertain outcomes (timeout, lost response) by status lookup before any retry.
10. **Audit history and metrics.**

```mermaid
flowchart LR
    A[Request] --> B[Authorized evidence] --> C[Policy by checkout date] --> D[Deterministic eligibility]
    D --> E[Explanation with citations]
    E --> F{Next action}
    F -->|missing info| G[Awaiting information]
    F -->|conflict or missing record| H[Escalated]
    F -->|adjustment| I[Pending approval]
    F -->|nothing to do| J[Resolved: no adjustment]
    G --> B
    I --> K[Approved by another supervisor] --> L[Re-check, then execute with idempotency key]
    L -->|confirmed| M[Resolved]
    L -->|timeout or lost response| N[Execution unknown] --> O[Reconcile by status lookup] --> M
```

## 3. Case states (spec B.10; full diagram and tests in Milestone 6)

```mermaid
stateDiagram-v2
    [*] --> New
    New --> Investigating
    Investigating --> AwaitingInformation
    AwaitingInformation --> Investigating
    Investigating --> Escalated
    Investigating --> PendingApproval
    Investigating --> Resolved: no adjustment required
    PendingApproval --> Approved: another supervisor
    PendingApproval --> Rejected: with reason
    PendingApproval --> Investigating: evidence or policy changed
    Approved --> PendingApproval: approval invalidated
    Approved --> Executing
    Executing --> Resolved: confirmed
    Executing --> ExecutionUnknown: timeout or lost response
    ExecutionUnknown --> Resolved: reconciliation finds it applied
    ExecutionUnknown --> Approved: reconciliation finds it not applied
    Rejected --> Investigating: reopened
    Resolved --> Investigating: reopened with reason
    Escalated --> Investigating: property answered
```

## 4. System boundaries and ownership

| System (synthetic stand-in) | Holds | Owner (client side) | This project's access |
|---|---|---|---|
| Loyalty platform (mock customer API) | Members, points ledger, posting queue, adjustment API | Loyalty data owner / IT | Read; adjustments only via the API with an idempotency key |
| PMS (mock customer API) | Stays, channels, partner confirmations, folios | Property IT | Read |
| CRM / case system | Cases, notes, attachments | Support operations | This app is the case system in the simulation |
| Policy repository | Versioned policy documents | Administrator | Read; publish through the workflow |
| Model provider (arm C only) | Nothing stored by design; prompts in transit | Vendor management | Minimised, redacted context only |

## 5. Member journey (simulated, F6)
Request → (each information request is a contact; the simulated member answers only if the question asks for
something the scenario holds) → resolution → reopen if the outcome was wrong. Measured per arm in Milestone 10:
contacts per case, simulated days to resolution, whether the member ended with the correct points, and the modelled
satisfaction proxy. All labelled simulated.
