# Product requirements

> Simulated client engagement, synthetic data. What the product does, for whom, and how each feature is accepted.
> Business requirements (BR-*) are in `docs/business-requirements.md`; this file turns them into user stories.

## 1. Users and roles

| Role | Can | Can't |
|---|---|---|
| Agent | Create cases, run investigations, supply missing information, propose adjustments, escalate, leave feedback | Approve anything; change configuration |
| Supervisor | Everything an agent can, plus approve or reject adjustments with a reason | Approve an adjustment they proposed; change configuration |
| Administrator | Manage policies (draft → publish), rule configuration, users and roles, switches | Approve adjustments |
| Auditor | Read cases, evidence, approvals, executions and the audit trail | Change anything |

Roles come from the server-side session or the identity provider's claims, never from a form field, a URL or a model.

## 2. User stories and acceptance criteria

| ID | As a… | I want… | Accepted when | BR |
|---|---|---|---|---|
| US-01 | Agent | to create a case from a request (form fields, free text, attachment) | The case has a request ID, the original text is stored as data, and attachments pass type and size checks | BR-07 |
| US-02 | Agent | one evidence view: member, stays, ledger (posted, pending, reversed), policy for the checkout date | Each panel shows its source and retrieval time; pending postings and reversals are visible | BR-06 |
| US-03 | Agent | the deterministic eligibility result with points and the policy section | Result is one of `eligible / ineligible / insufficient_evidence / needs_escalation` with reasons and a citation that opens the exact excerpt and version | BR-02, BR-03 |
| US-04 | Agent | (arm C) an AI-drafted recommendation | It is labelled AI-generated, cites evidence and policy, matches the deterministic result, lists missing information, and shows no confidence percentage | BR-07, BR-08 |
| US-05 | Agent | to ask the member for one specific missing item | The question names the item; the case moves to Awaiting information; the reply resumes the case | BR-08 |
| US-06 | Agent | to escalate with a reason | The case moves to Escalated with the reason in the audit trail | BR-09 |
| US-07 | Supervisor | to see facts and the rule result before any AI summary | The approval page orders: evidence → deterministic result → AI summary (if any); approve requires viewing the cited evidence | BR-01 |
| US-08 | Supervisor | to approve or reject with a reason | Approval is bound to member, stay, points, policy version, evidence snapshot, approver and expiry; rejection needs a reason; self-approval is refused server-side | BR-01, BR-05 |
| US-09 | Supervisor | approvals that expire when the case changes | Any change to amount, member, stay, policy or evidence cancels the approval and returns the case to Pending approval | BR-05 |
| US-10 | Agent or supervisor | to execute an approved adjustment and see its status | Eligibility and ledger are re-checked first; the request carries an idempotency key from the approval; a timeout moves the case to Execution unknown and reconciliation runs before any retry | BR-04 |
| US-11 | Agent | to reopen a resolved case | Reopen needs a reason; any earlier approval is not reused | BR-11 |
| US-12 | Auditor | the full audit timeline of a case | Every proposal, approval, rejection, execution, reconciliation and override, with who and when | BR-11 |
| US-13 | Administrator | to publish a new policy version | Draft → regression checks → published; pending approvals affected by the change are cancelled | BR-02, BR-05 |
| US-14 | Administrator | to switch live AI off, or adjustment execution off | AI off: the console works as arm B; execution off: investigation continues, execute is refused | BR-10 |
| US-15 | Any user | to see which mode I'm in | Banner: SYNTHETIC DATA · profile · AI mode (MOCK / LIVE: model ID) · customer | BR-03 |
| US-16 | Agent | to give feedback or override a recommendation with a reason | Stored with the case; never changes prompts or rules automatically | BR-12 |

## 3. What AI does and does not control

| AI may (arm C only) | AI never |
|---|---|
| Read the request and find which stays and dates it means | Decide eligibility, points, permissions, approval or execution |
| Choose which read-only tools to call (within an allowlist and budget) | Call a tool outside the allowlist, or any write, SQL, shell, file, browser, network or payment capability |
| Summarise evidence with citations | Cite a passage it wasn't given |
| Draft a recommendation and a reply for staff | Send anything to a member |
| Flag missing information | Override a deterministic result |

## 4. The three arms in the product
- **Arm A (legacy):** separate member and stay search, ledger lookup, keyword policy search, legacy rule config,
  manual notes, supervisor approval. Run by a scripted agent for benchmarking.
- **Arm B (improved, no generative AI):** corrected rules, one evidence view, fuzzy search, full-text policy search,
  validation, automatic calculations. It is also the manual mode when AI is off.
- **Arm C (AI-assisted):** arm B plus the bounded AI layer above.
- **A as-is (benchmark-only variant):** arm A on the legacy write path; never reachable from the product.

All arms share authorization, approval and the write path (spec B.8).
