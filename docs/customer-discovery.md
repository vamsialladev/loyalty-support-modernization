# Customer discovery: loyalty support

> **Simulated client engagement. FICTIONAL people, sessions and answers.** The hotel group, every role and every
> answer below are invented to match the synthetic data used in later milestones, so the documents and the code tell
> one story. Roles only; no names are recorded (stage 0 convention). Statements in quotes are *assumed customer
> statements*: perceptions to validate against data, not facts. Requirement IDs DISC-02, DISC-03, DISC-05.

## 1. Fictional customer context

- **Who:** the same fictional hotel group as stages 0–8, two properties: Beach Resort (near Miami) and Mountain Lodge
  (near Asheville). Its loyalty program is **Guest Rewards** (Silver / Gold / Platinum; 10 points per US dollar of
  room revenue). See `docs/continuity.md` §3–4.
- **Where this starts:** after stages 1–8, the group's loyalty operations manager asked for help with one queue:
  members writing "I stayed, but my points are missing". It is handled by a small group-level loyalty support team
  that serves both properties.
- **Why now (assumed):** a policy change on 2026-07-01 (waiting period 30 → 14 days; some OTA bookings now earn) was
  followed by more contacts and a few double credits found in a month-end ledger check.
- **What the client does not want:** stage 0's general manager said one confident wrong answer about money would make
  them switch AI off, and stage 0 rejected "automatic refunds decided by AI" for that reason. Every design choice here
  keeps a person approving every adjustment and keeps eligibility and amounts in deterministic rules.

## 2. Stakeholder map

| Role | Interest | Influence | What they need from this project | Involvement |
|---|---|---|---|---|
| Sponsor: loyalty operations manager | Cost to serve, points-liability control, member trust | High (budget owner for the pilot) | Measured evidence that a change is worth it, including "don't use AI" if that's the answer | Decides scope, approves pilot gates |
| Support agent (6 assumed) | Fewer screens, fewer repeat contacts, clear rules | Medium | One evidence view; a recommendation they can check; no blame for system errors | Daily user; UAT participant |
| Supervisor (2 assumed) | Approvals they can trust; no duplicate credits | Medium | The evidence and the rule result before any summary; a reason box for every rejection | Approves every adjustment |
| Administrator (loyalty systems analyst) | Configuration that matches the published policy | Medium | Versioned policy and rule config, a publish workflow with checks | Maintains policies and limits |
| Auditor (internal audit / finance) | Every adjustment explainable after the fact | High at sign-off | Read-only audit trail: who proposed, who approved, on what evidence, what executed | Reviews controls |
| IT (application owner) | Integration with the loyalty platform, PMS, CRM | High | Clear contracts, no direct database writes, a rollback plan | Owns integrations after handover |
| Security | No new path to move points without control | High (can block) | Threat model, authorization tests, secrets handling, red-team results | Reviews before pilot |
| Operations (support team lead) | Backlog and SLA | Medium | Queue views, SLA alerts, a manual fallback when AI is off | Runs the pilot day to day |
| Data owner (loyalty data / CRM owner) | Data quality, merges, retention | Medium | A list of data defects found, with who fixes what | Fixes source data (merges, channels) |
| **Affected, not a user: members** | Getting the points they earned | None directly | Correct points, fewer contacts, faster answers | Never see the system; modelled only through the simulated member journey |

## 3. Personas

| Persona | Day | Pain (assumed) | What "better" looks like |
|---|---|---|---|
| **Agent, two years in** | Works the queue from the CRM; opens member, stay, ledger and policy screens one by one | "Half my time is finding the stay." Partner confirmation numbers don't search; names don't match exactly | Finds the stay in one view; the rule result is shown, not worked out by hand |
| **Supervisor** | Approves 20–40 adjustments a day between other work | "I approve on trust. I can't re-check every case." Found two double credits last quarter | Sees the evidence and the rule result first; can't be asked to approve their own work; a changed case can't keep its old approval |
| **Loyalty operations manager (sponsor)** | Reports on cost to serve and liability monthly | "I don't know how many we get wrong, in either direction." | A baseline with numbers, then a measured comparison of options |
| **Auditor** | Quarterly control review | "Approvals are a status flag. I can't tell what was approved." | Each approval bound to the exact member, stay, points, policy version and evidence |

## 4. Discovery interview guide

Format (as in stage 0): 45–60 minutes per role, one note-taker, answers read back at the end, roles only.

| Area | Questions |
|---|---|
| The work | Walk me through the last missing-points request you handled. Which screens, in what order? Where did you get stuck? |
| Volume and time | How many a day? How long does a normal one take? What makes one take an hour? |
| Rules | Which policy version do you apply to a stay from before July? How do you know? Who changes the rule settings? |
| Data | What do you do when the stay isn't found? When the member has two accounts? When the channel is blank? |
| Errors | How would you know if a case was wrong? Who finds double credits, and when? |
| Approval | What does a supervisor look at before approving? What happens if the case changes afterwards? |
| Members | How often does a member write again about the same stay? What do they say? |
| Systems | Which systems hold the truth for members, stays, points? How fresh is each? Who owns it? |
| Success | What would make this queue "fixed" in three months? What would make you stop the project? |
| AI | What should a machine never decide here? What would you want it to do first? |

## 5. Simulated sessions (FICTIONAL)

### 5.1 Loyalty operations manager (sponsor)

| # | Question I asked | Answer (simulated) |
|---|---|---|
| 1 | What's going wrong in this queue? | "Members write twice or three times about the same stay. And finance found double credits in a month-end check." |
| 2 | How many requests? | "A few hundred a month across both properties, more after the holidays and in July." (Assumption A1 below) |
| 3 | Do you know your error rate? | "No. That's the honest answer. We find over-credits when finance looks; we never find under-credits unless the member complains again." |
| 4 | What would success look like? | "Members get the right points the first time, and I can show finance the liability isn't leaking." |
| 5 | What would make you stop? | "Anything that lets points move without a supervisor. Or if it costs more than it saves." |
| 6 | Would you use AI here? | "Only if it's clearly better than fixing the tools we have. I'm not paying for AI to fix a search box." |
| 7 | Budget owner? | "Me for the pilot." |

### 5.2 Support agent

| # | Question I asked | Answer (simulated) |
|---|---|---|
| 1 | Walk me through the last one. | "Member number, then the stay search by confirmation number. Not found, because they gave me the booking site's number. I asked them for the hotel's number." |
| 2 | What takes longest? | "Four screens. And the ledger view groups re-posts under a later date, so a reversal looks like missing points." |
| 3 | Before-July stays? | "The system just applies today's rules. I'm not always sure that's right." |
| 4 | Blank channel? | "The rules treat it as not eligible. I deny it, unless I have time to dig." |
| 5 | Messages with several stays? | "I handle the one with a number on the form. The others come back as new tickets." |
| 6 | Non-English messages? | "We ask them to write in English. Some never write back." |
| 7 | What should a machine never do? | "Give points away. And tell a member yes when the supervisor might say no." |

### 5.3 Supervisor

| # | Question I asked | Answer (simulated) |
|---|---|---|
| 1 | What do you check before approving? | "The amount looks right for the stay, the member matches. I don't re-search." |
| 2 | Double credits? | "Two agents worked the same stay from an email and a phone call. Both got approved, by me." |
| 3 | If the case changes after approval? | "It stays approved. The approval is a status." |
| 4 | Would an AI summary help? | "Only if I see the facts first. If it's a summary on top, I'll just read the summary." |

### 5.4 IT, security, data owner, auditor (combined call)

| # | Question I asked | Answer (simulated) |
|---|---|---|
| 1 | Sources of truth? | IT: "Loyalty platform for members and the ledger, PMS for stays, the posting queue for in-flight points, CRM for cases." |
| 2 | Can a new tool write points? | Security: "Only through the loyalty platform's adjustment API, with an idempotency key, never the database." |
| 3 | Data problems you know of? | Data owner: "Duplicate profiles after re-enrolments; a 2025 merge left old numbers on future bookings; the PMS import drops some channels." |
| 4 | Retention? | Data owner: "Cases seven years for finance; free text shouldn't live forever." (to validate with legal) |
| 5 | What do you need at audit? | Auditor: "For each adjustment: who proposed, who approved, what evidence, which policy version, what executed and when." |
| 6 | Model provider concerns? | Security: "Send it only what it needs. No card numbers, ever. Tell me where it runs." |

## 6. Problem framing

### Pain points (from the sessions; to validate with the synthetic history in Milestone 3)
1. Evidence is spread over four screens and searches are exact-match only.
2. Rule configuration lags the published policy (waiting period at one property, the OTA rule).
3. Some source data is wrong or incomplete (duplicate profiles, merged numbers, blank channels, UTC dates).
4. Free-text requests (several stays, other languages, folios) get partial answers and repeat contacts.
5. Approvals are status flags; double credits happen when two cases cover one stay.
6. Nobody measures error rates in either direction.

### Assumptions to validate with a real customer
| ID | Assumption | Used for | How a real engagement would validate it |
|---|---|---|---|
| A1 | About 320 missing-points requests a month across both properties, with peaks in January and July | Synthetic history volume (M3) | 12 months of case exports |
| A2 | Median legacy handling time about 14 minutes; multi-stay cases 25+ minutes | Financial model inputs | Timing study with real agents (`docs/timing-protocol.md`, M10) |
| A3 | Loaded agent cost $32 per hour | Financial model | Finance |
| A4 | Points liability valued at $0.008 per point | Over-credit leakage estimate | Finance / loyalty accounting |
| A5 | 6 agents, 2 supervisors | Workload and UAT design | Team roster |
| A6 | The defect frequencies in `docs/legacy-defect-catalog.md` | Synthetic history | Case-by-case review of a real sample |
| A7 | Members never see the tool; replies are sent by staff | Scope and risk | Confirm with the sponsor |

### Who owns the problem
The loyalty operations manager owns the outcome. Data defects belong to the data owner, integration fixes to IT, rule
configuration to the administrator. The FDE team owns the build, the measurements and the handover.

### What a successful resolution means
For each request: the member's ledger ends with exactly the points the policy says they earned, at the first answer
where possible, with no duplicate credit, and with an audit record a reviewer can follow. For the project: a measured
comparison that tells the sponsor which fix is worth paying for.

### When ordinary software is sufficient
When the failure is a stale rule, a missing index, an exact-match search, a missing merge map, a UTC conversion or a
fragmented screen. The defect catalog predicts that most failures are of this kind (arm B).

### What AI adds (if the measurements agree)
Reading free text that mentions several stays, vague dates, nicknames, other languages, mixed complaints, and noisy
receipt images; summarising evidence with citations; spotting missing information. Always as a recommendation that
deterministic rules check and a supervisor approves.

### Conditions for stopping or redesigning
- Any adjustment executed without a valid supervisor approval, or any duplicate credit, in any test (H6): stop and fix.
- Arm C raises false approvals over arm B (H2): C loses proposal authority or is dropped.
- Arm B delivers most of the value (H1 supported, H2 not): recommend B; AI only where H3 shows a gain.
- Cost per correctly resolved case above the limit (H5): redesign or drop C.
- The sponsor, security or audit withholds approval at a rollout gate (`docs/business-requirements.md` §6).
