# Governance and ownership (spec A.4)

> Simulated client engagement. Requirements GOVN-01, GOVN-02, GOVN-03, DISC-11. Every approval, sign-off and owner
> on the client side is **fictional and unfilled**: no real person has approved anything. The FDE team is Vamsi
> Alla (with Claude Code as the implementer, ADR-0001).

## 1. Responsibility boundaries

| Party | Owns | Does not own |
|---|---|---|
| Application / FDE team | Code, tests, evaluations, benchmark, docs, technical controls in this repo, handover | Client identity, cloud accounts, real data, business sign-off |
| Identity team (client) | IdP configuration, groups, MFA, SCIM provisioning, offboarding | Application roles' meaning (shared with product owner) |
| Platform / cloud team (client) | Accounts, networking, managed Postgres, secrets manager, backups | Application logic |
| Security team (client) | Threat-model review, exceptions, pen testing, incident command | Day-to-day fixes |
| Data owner (client) | Source data quality, merges, retention schedule, data-subject requests | The app's derived data handling (shared) |
| Product / business owner (sponsor) | Scope, acceptance criteria, rollout gates, business thresholds | Technical design |
| Incident response | Containment, communication, post-incident review | — |
| Vendor management | Model provider and host contracts, retention terms, regions | — |

## 2. RACI (R = responsible, A = accountable, C = consulted, I = informed)

| Activity | FDE team | Sponsor | Supervisor | Admin | IT | Security | Data owner | Auditor |
|---|---|---|---|---|---|---|---|---|
| Discovery and requirements | R | A | C | C | C | C | C | I |
| Defect catalog and hypotheses (pre-registration) | R | A | C | I | I | I | C | I |
| Rules and policy configuration | C | A | C | R | I | I | C | I |
| Building arms A, B, C | R/A | I | C | C | C | C | I | I |
| Authorization and approval controls | R | A | C | I | C | C | I | C |
| Threat model and red team | R | I | I | I | C | A | I | I |
| Benchmark runs and business-value report | R | A | I | I | I | I | I | C |
| Data fixes (merges, channels) | C | I | I | I | C | I | R/A | I |
| Rollout gate decisions | C | A | C | I | C | C | C | C |
| Prompt, model and policy changes after handover | C | A | I | R | C | C | I | I |
| Incident response | C | I | I | I | R | A | C | I |
| Audit review | C | I | I | I | I | C | I | R/A |

## 3. Technical controls (this repo) vs organizational controls (external owners)

| Control | Technical (implemented here, when built) | Organizational (needs an external owner) |
|---|---|---|
| Approval | Proposer ≠ approver enforced server-side; approval hash | Who may be a supervisor; approval limits policy |
| Access | Deny-by-default authorization; role mapping from IdP claims | Access requests, reviews, offboarding |
| Data | Minimisation, redaction, retention jobs | Retention schedule, legal basis, DSR process |
| Model provider | Configured destination; no silent fallback | Contract, retention terms, region approval |
| Change | Regression evaluation before release; known-good config | Change approval (CAB), communication to staff |
| Incidents | Kill switches, runbooks, alerts | Incident command, customer communication |

## 4. Templates

### 4.1 Access request
```
Access request AR-<number>
Requester (role):                 Date:
System and environment:           (e.g. mock loyalty API, staging)
Access type:                      developer-assistant / runtime model / customer system / deployment
Scope:                            read / write; records or tables; customers
Purpose and duration:
Data categories involved:
Approver (system owner):          Decision:          Date:
Revocation date / procedure:
```

### 4.2 Security exception
```
Security exception SE-<number>
Requirement not met:              (control ID)
Reason:
Risk (impact × likelihood):
Compensating controls:
Named owner:                      Expiry date (mandatory):
Approved by (security):           Date:
Review on expiry:  renew / close
```

### 4.3 Risk acceptance
```
Risk acceptance RA-<number>
Risk (from the register):         ID:
Why it is accepted rather than mitigated:
Compensating controls:
Residual risk after controls:
Accountable owner (named role):   Expiry / review date:
Decision by:                      Date:
```

No template in this repository is filled in with a real approval. Simulated entries, if any are made for an
exercise, carry the word SIMULATED in the decision field.
