# Business requirements

> Simulated client engagement, synthetic data. Requirement IDs DISC-06, DISC-09, DISC-10. Each BR maps to rows in
> `docs/requirements-matrix.md`. Business thresholds are **provisional**: no real stakeholder has approved them.

## 1. Business goals (from the KPI tree, `docs/kpi-tree.md`)
1. Members end with the points they earned (member trust).
2. Lower cost to serve per correctly resolved request.
3. No points-liability leakage (over-credits, duplicate credits).
4. Every adjustment explainable after the fact (auditability).

## 2. Business requirements

| ID | Requirement | Why | Matrix rows |
|---|---|---|---|
| BR-01 | Every adjustment needs a supervisor's approval; the person who proposed it can't approve it | Sponsor's stop condition; stage 0's rejected idea F | WP-03, WP-04, WP-05 |
| BR-02 | The policy version applied is the one in force on the stay's checkout date (Eastern time), and the decision cites it | Before-July stays were judged on today's rules | POL-04, D15 |
| BR-03 | Eligibility and points come from written rules, never from a model | Auditability; a model can be wrong or manipulated | ELIG-01, ELIG-02 |
| BR-04 | A stay is never credited twice, including after a timeout or two cases for one stay | Double credits found by finance | WP-07, WP-08, WP-09, H6 |
| BR-05 | A changed amount, member, stay, policy or evidence cancels an existing approval | Approvals given on old evidence | WP-06, D11 |
| BR-06 | Agents see member, stays, ledger (including pending postings and reversals) and the policy in one view | Four screens; reversals look like missing points | UI-01, D06, D07, D14 |
| BR-07 | Requests mentioning several stays, other languages or attached folios are fully handled or explicitly routed | Partial answers create repeat contacts | D16, D20, D22, D23 |
| BR-08 | When information is missing, the member is asked for the specific item, once | Repeat contacts | AI-14, H4 |
| BR-09 | When records conflict or are missing upstream, the case escalates to the property instead of guessing | Unfixable cases (D24, D25) | POL-06 |
| BR-10 | Investigation keeps working when AI is off or adjustments are switched off | Provider outage; emergencies | WP-10, OPS-05 |
| BR-11 | The audit trail shows who proposed, who approved, what evidence, which policy version, what executed and when | Auditor's requirement | WP-11 |
| BR-12 | The options (legacy, improved tools, AI-assisted) are compared on the same held-out cases before any recommendation | Sponsor: "I'm not paying for AI to fix a search box" | Part E, H1–H5 |

## 3. Nonfunctional requirements

| ID | Requirement | Target (proposed) | Measured where |
|---|---|---|---|
| NFR-01 | Security: deny by default; authorization on every operation; secrets never in code, logs or prompts | 100% of authorization tests pass | Part C, M9 |
| NFR-02 | Privacy: send the model only needed fields; redact card, passport, phone and email in free text before model calls and logs | Redaction tests pass on synthetic examples | ENT-12 |
| NFR-03 | Reliability: durable jobs, no in-memory critical work, reconciliation before retry | Real-Postgres tests pass | M6 |
| NFR-04 | Investigation latency (model + tools, benchmark environment) | p95 ≤ 15 s (H5) | M10 |
| NFR-05 | API latency for console pages | p95 ≤ 500 ms locally (proposed) | M12 load test |
| NFR-06 | Model cost per correctly resolved case | ≤ $0.02 (H5) | M10 live runs |
| NFR-07 | Accessibility: keyboard navigation, labels, AA contrast | Checked per page | M7 |
| NFR-08 | Portability: runs on Windows and macOS/Linux; Docker Compose locally | Clean install from a fresh clone | M20 |
| NFR-09 | Observability: health and readiness endpoints, structured logs, traces with no prompt content | Present and tested | M12 |
| NFR-10 | Retention: free text and summaries deleted on schedule; legal hold respected | Retention job tests | M9 |

## 4. MVP scope
Arms A, B and C for missing-points requests at both properties; the safe write path; the server-rendered console;
the mock customer API; the benchmark. One customer (the hotel group) first; Cedarpoint Inns in Milestone 14.

## 5. Exclusions
Refunds, real payments, messages to members, autonomous adjustments, complex multi-agent orchestration, changes to the
loyalty program, real customer systems or data, the posting pipeline (Stage 10). Commerce and payment protocols exist
only as isolated sandbox labs (Milestone 16).

## 6. Success metrics and acceptance criteria

| Metric | Definition | Acceptance criterion (provisional) |
|---|---|---|
| Final-ledger accuracy | `docs/hypotheses.md` §1 | Recommended option beats the next-best by its hypothesis threshold on held-out cases |
| False approvals | Over-credits per case | Never higher for the recommended option than for arm B (H2) |
| Duplicate credits / unauthorized actions | Write-path failures | 0 in every arm, split and run (H6) |
| Contacts per case (simulated) | Member journey | Recommended option ≤ arm B |
| Cost per correctly resolved case | Model + API cost / correct cases | ≤ $0.02 for arm C (H5) |
| Handling time | Real participants only | Reported only if measured (H7) |

## 7. Pilot and rollout plan

| Stage | What runs | Gate to the next stage | Stop or roll back if |
|---|---|---|---|
| 1. Offline evaluation | Benchmark on synthetic held-out cases | H6 passes; the recommended option meets its hypothesis | Any H6 failure |
| 2. Shadow | Recommendations on real cases, nothing executed; agents work as today | Disagreements reviewed with supervisors; no unexplained pattern | Recommendations disagree with supervisors on a whole category |
| 3. Limited pilot | Two agents and one supervisor use the new console; adjustments executed after approval | Two weeks with zero duplicate credits and false approvals at or below arm B's offline rate | Any duplicate credit; any approval-integrity failure |
| 4. Human-approved execution, whole team | All agents | Sponsor, security and audit sign-off (real people, not simulated) | As above; or a cost overrun |
| 5. Broader rollout | Other properties | Acceptance criteria met at stage 4 | As above |

This project runs stage 1 only, on synthetic data. Stages 2–5 are a plan for a real engagement.

## 8. Scope-change template

```
Change request CR-<number>
Requested by:            Date:
What changes:
Why:
Effect on scope:         (requirements added / removed, matrix IDs)
Effect on timeline:      (milestones affected)
Effect on cost:          (engineering hours, model or hosting cost)
Effect on risk:          (security, data, evaluation validity: does it touch pre-registered items?)
Evaluation evidence needed before release:
Rollback plan:
Decision:   approved / rejected / deferred      By (client owner):        Date:
Recorded in: CHANGELOG.md, docs/decisions.md, docs/requirements-matrix.md
```

A change to a pre-registered item (`docs/legacy-defect-catalog.md`, `docs/hypotheses.md`) is also logged in that
document's change log and treated as a new experiment.

## 9. Milestone plan
`docs/implementation-plan.md` (20 milestones, Appendix C "done when" criteria).
