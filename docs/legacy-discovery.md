# Legacy discovery: the current loyalty support tools

> **SYNTHETIC.** The "legacy system" is arm A of this project: a deliberately realistic, competent legacy workflow
> built in Milestone 5, carrying the pre-registered defects in `docs/legacy-defect-catalog.md`. It is not modelled on
> any real company's software. Requirements ARMA-02, DISC-07, POL-01.

## 1. Known functionality: what the legacy workflow does well
Built in Milestone 5 as the arm A console (`app/web/`, `app/arms/legacy/`, `app/services/`). **Implemented and
verified** by `tests/test_legacy_rules.py`, `tests/test_legacy_screens.py`, `tests/test_case_workflow.py`,
`tests/test_console_web.py` and the Playwright test `tests/browser/test_legacy_e2e.py`.
- A points queue with status and "assigned to me" filters, a billing queue, and a "New case" form for phone requests.
- Finds members by exact member number, and by exact first name, last name and email together.
- Finds stays by exact hotel confirmation number within the found member's stays.
- Shows the posted ledger, newest first and grouped by posting date: the last 90 days by default, with a working
  "Show older entries" (ADR-0050).
- Keyword policy search over the legacy index.
- A rules checklist the legacy engine computes from the evidence the agent attached by hand (member, stay, ledger
  view, policy excerpt): checked out, claim window, channel, not already credited, waiting period, approval limit.
- Calculates points correctly from room revenue (floor of 10 per US dollar; taxes and fees excluded). The agent
  cannot type an amount.
- Manual notes, information requests to the member (a ticket), escalation with a reason, closing with a reason code;
  closing against the checklist is an override that needs a note.
- Supervisor approval or rejection with a reason; a supervisor never decides on their own request; agents never
  decide. Execution of the simulated adjustment, with reconciliation when the outcome is uncertain.
- An audit timeline of every step; the same log feeds the E.2 instrumentation.
- Handles the straightforward cases correctly (controls K01–K06: about half of history cases).

It is not made incompetent, insecure or incomplete on purpose. Sign-in, sessions, CSRF protection and authorization
work (ADR-0045).

## 2. Limitations, by kind (spec B.8)

| Kind | Limitation | Catalog IDs |
|---|---|---|
| Missing functionality | No view of pending postings; no partner-confirmation search; no duplicate-profile or merge-map lookup; no policy-by-date view; no attachment reading; no language handling; no cross-case duplicate check; approvals not bound to evidence | D02, D05, D06, D15, D22, D23, D10, D11 |
| Configuration errors | Mountain Lodge still on the 30-day wait; v2's OTA rule never configured; corporate exception never configured; blank channel treated as ineligible; keyword index frozen at 2026-03-15 | D08, D09, D21, D03 |
| Data problems | Duplicate profiles; stays on merged numbers; blank channels; UTC timestamps read as local dates; reversed and re-posted transactions | D01, D02, D03, D04, D07 |
| Operational delays | Late postings after property interface outages; claims routed to the billing queue | D06, D20 |
| UI friction | Four separate screens; exact-match search; ledger grouping hides re-posts | D12, D13, D14, D07 |
| Not fixable by tools | Missing upstream records; conflicting records | D24, D25 |

## 2a. How each limitation is built (Milestone 5)

Every limit comes from the pre-registered catalog and nowhere else (ADR-0043). Where it lives, and the test that pins
it:

| ID | Built behaviour in arm A | Where | Test |
|---|---|---|---|
| D01 | Stays on a duplicate profile never appear: stay search covers only the found profile; no duplicate candidates | `screens.search_stay`, `screens.search_member` | `test_legacy_screens.py::test_d01_d02_...[D01]` |
| D02 | A merged profile shows its `merged_into` number, which the screen never follows | `screens.search_member`, `search_stay` | `...[D02]` |
| D03 | A blank booking channel is not in the eligible list, so it is denied (the reservation source code is not used) | `config/legacy/hg-demo-legacy-rules.yaml`, `checklist.evaluate` | `test_legacy_rules.py::test_d03_...` |
| D04 | Waiting period and claim window compare UTC calendar dates, not Eastern business dates | `rules.py` (`date_basis: utc`), `checklist.utc_day` | `test_d04_...` |
| D05 | Partner (`TRV-`) confirmations are not searchable on the stay screen, though the platform has them | `screens.search_stay` | `test_d05_...` |
| D06 | No screen reads the posting queue | `screens` (never calls `get_pending_postings`) | `test_d06_...` |
| D07 | The ledger screen lists a re-post under its own date without the stay's confirmation; the checklist nets by stay, so the reversal shows and the re-post doesn't | `screens.ledger_view` | `test_d07_...` (screen and checklist) |
| D08 | Mountain Lodge still waits 30 days after 2026-07-01; Beach Resort was updated to 14 | rules YAML | `test_d08_...` |
| D09 | v2's OTA rule never configured; the keyword index holds only what was in force on 2026-03-15 | rules YAML, `keyword_index.py`, `scripts/build_legacy_index.py` | `test_d09_...`, `test_index_holds_only_...` |
| D10 | Intake opens one case per contact and no screen warns about another case for the same stay. **In arm A the shared write path refuses the second credit** (ADR-0044); only the A-as-is variant lets it through (ADR-0051) | `benchmarks/intake.py`, `write_path.SharedWritePath._duplicate` | `test_case_workflow.py::test_d10_...` |
| D11 | Not built as a limit: approval binding is a shared-write-path safeguard (Milestone 6). Until then approvals are not bound to an evidence snapshot in any arm (TD-12) | `write_path.py` | Milestone 6 |
| D12 | Exact-term keyword search: every word must appear; no stemming, no synonyms | `keyword_index.KeywordIndex.search` | `test_keyword_search_is_exact_term_d12` |
| D13 | Exact member number (case-sensitive), or exact first name + last name + email | `screens.search_member` | `test_d13_...`, `test_name_and_email_...` |
| D14 | Evidence is on four separate screens, each attached to the case by hand | `app/web/templates/screen_*.html` | Playwright test; step counts in `case_events` |
| D15 | The rules revision in force on the day the case is worked applies, whatever the stay's checkout date | `LegacyRules.revision_on` | `test_d15_...` |
| D16 | One stay per case: attaching another stay replaces the first | `cases.current_evidence` | scripted agent policy |
| D17 | No fuzzy or prefix match on confirmation numbers | `screens.search_stay` | `test_d17_...` |
| D18 | No nickname list, accent folding or married-name match | `screens.search_member` | `test_d18_...` (3 dev cases) |
| D19 | The stay screen needs a confirmation number; dates alone don't find a stay | `screens.search_stay` | scripted agent policy |
| D20 | Any message containing "refund" goes to the billing queue, which this tool doesn't work | `intake.route` | `test_d20_...` (rules, workflow, scripted agent) |
| D21 | v2's corporate travel exception (`CORP*`) never configured | rules YAML | `test_d21_...` |
| D22 | Attachments are listed by file name only; there is no viewer | `case.html` | — |
| D23 | No language handling; the scripted agent asks for English | `benchmarks/agents/legacy_scripted.py` | `test_scripted_agent.py::test_non_english_...` |
| D24 | A missing stay record is "not found" | `screens.search_stay` | scripted agent policy |
| D25 | When the PMS holds two records for one confirmation, the screen shows the first one returned | `screens.search_stay` | `test_d25_...` |

**What is deliberately *not* a limitation.** The 90-day ledger default would have hidden old postings and made
already-credited late claims look missing, a defect outside the catalog. So "Show older entries" works, and the
checklist refuses a ledger view that doesn't cover the checkout date (ADR-0050). The window costs steps, never
accuracy.

**Open gap, not a legacy defect (found by the owner on 2026-11-03, TD-17).** `cases.close_case` lets an agent close with
a rule-based code (for example `deny_claim_window`) while the checklist says `incomplete_evidence`, as long as a note
is present. No catalog defect covers this and spec B.8 rules out making the tool incompetent on purpose, so it is a
gap in the Milestone 5 build, not intended behaviour. Case A-000010 shows the harm: denied on the claim window with no
evidence attached, when its stay (checkout 2025-05-20, claim 2026-01-06) was inside the window. The scripted agent
never takes this path, so no pre-registered prediction depends on it. Proposed fix, awaiting the owner:
`docs/backlog.md`.

## 2b. The scripted legacy agent and the A-as-is variant
- **Scripted agent** (`benchmarks/agents/legacy_scripted.py`, ADR-0048): works arm A through the same services and
  permissions as the browser. Its reading policy is fixed in its docstring. Output is labelled **"scripted, not human
  timing"**: step counts and elapsed software time, never handling time. Milestone 5 runs it for mechanics only;
  arm A's accuracy is measured in Milestone 10, after the thresholds file is committed.
- **A as-is** (ADR-0018, ADR-0051): the same scripted agent with a benchmark-only write path (approval as a status
  flag, no duplicate check, a fresh key per attempt), against a disposable database, interleaving D10/S05 pairs.
  Built in Milestone 10, reported next to arm A, excluded from H1–H6. Nothing in `app/` can import it (tested).

## 3. System inventory (synthetic stand-ins)

| System | Role | Interface | Freshness | Owner |
|---|---|---|---|---|
| Loyalty platform | Members, tiers, points ledger, posting queue, merge map, adjustment API | Mock customer API (REST, versioned OpenAPI) | Ledger real time; posting queue every 15 minutes (assumed) | Loyalty data owner |
| PMS | Stays, room revenue, channel, partner confirmation, folios | Mock customer API | Nightly export (assumed); stays appear the day after checkout | Property IT |
| CRM / case system | Cases, notes, attachments, routing | This application in the simulation | Real time | Support operations |
| Policy repository | Versioned policies with effective dates | Markdown with front matter, ingested into Postgres | On publish | Administrator |
| Keyword index (legacy only) | Policy search for arm A | Frozen snapshot | Built 2026-03-15 (D09) | Administrator |

## 4. Integration contracts and constraints
- Read endpoints: member lookup, stay lookup, ledger lookup (paginated), posting-queue lookup.
- Write endpoints: support ticket creation; adjustment submission **requires an idempotency key**; adjustment status
  lookup by key or adjustment ID.
- Typed errors: 401/403 authentication and authorization, 404 not found, 409 idempotency conflict (same key,
  different body), 422 validation, 429 rate limit with `Retry-After`, 503 transient, timeouts.
- Constraint from security: no direct database writes to the loyalty platform; every adjustment through the API.
- Constraint from IT: contracts are versioned; adapters must survive an added field and reject a removed required one.
- Known hazard: the platform can complete an adjustment and lose the response. Only a status lookup tells the truth.
- Full contracts and contract tests: Milestone 4.

## 5. Source register (spec B.6)

| Data | Authoritative source | Freshness requirement | Field mapping notes | Owner | Conflict rule |
|---|---|---|---|---|---|
| Member identity | Loyalty platform member record | Real time | `member_number` = `GR-#####`; follow `merged_into` | Loyalty data owner | Platform wins over the request; a duplicate needs two matching identifiers |
| Stay facts (dates, revenue, channel) | PMS stay record | Next day | Checkout timestamp UTC → Eastern business date; `partner_confirmation` for OTA | Property IT | PMS wins; disagreeing PMS records → escalate (D25) |
| Points posted | Loyalty ledger | Real time | Net reversal + re-post by stay ID | Loyalty data owner | Ledger wins |
| Points in flight | Posting queue | 15 minutes | Pending postings by stay ID | Loyalty data owner | A pending posting means no adjustment yet |
| Policy | Policy repository, published version in force on the checkout date | On publish | `policy_id`, `version`, `effective_from`, `effective_to`, section IDs | Administrator | Published version only; drafts never apply |
| Attachments | The member's upload | At intake | Extracted fields are evidence only | Member / agent | Never overwrite a system of record |

## 6. Data quality assessment (expected, from the catalog; measured in Milestone 3 on the synthetic history)

| Dimension | Expected issue | Catalog ID | Check |
|---|---|---|---|
| Completeness | Blank channel on about 5% of stays | D03 | Null rate per field |
| Uniqueness | About 4% of members have a duplicate profile | D01 | Matching phone + date of birth |
| Validity | Partner confirmation formats differ from hotel ones | D05 | Format patterns |
| Consistency | Reversal and re-post pairs; disagreeing stay records | D07, D25 | Pairs by stay ID |
| Timeliness | Late postings beyond the waiting period | D06 | Posting lag distribution |
| Accuracy | UTC dates read as local dates | D04 | Local vs UTC business-date mismatches |

Milestone 3 replaces "expected" with counts measured on the generated data, and Milestone 10's root-cause analysis
ties each benchmark failure back to a row here.
