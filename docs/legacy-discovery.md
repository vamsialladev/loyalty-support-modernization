# Legacy discovery: the current loyalty support tools

> **SYNTHETIC.** The "legacy system" is arm A of this project: a deliberately realistic, competent legacy workflow
> built in Milestone 5, carrying the pre-registered defects in `docs/legacy-defect-catalog.md`. It is not modelled on
> any real company's software. Requirements ARMA-02, DISC-07, POL-01.

## 1. Known functionality: what the legacy workflow does well
- Finds members by exact member number, and by exact name plus email.
- Finds stays by exact hotel confirmation number within a member's stays.
- Shows the posted ledger for the last 90 days.
- Applies written eligibility rules automatically (channel, waiting period, claim window, checkout status).
- Calculates points correctly from room revenue (10 per US dollar, taxes and fees excluded).
- Requires a supervisor's approval before an adjustment.
- Handles the straightforward cases correctly (controls K01–K06: about half of history cases).

It is not made incompetent, insecure or incomplete on purpose. Authentication and authorization work.

## 2. Limitations, by kind (spec B.8)

| Kind | Limitation | Catalog IDs |
|---|---|---|
| Missing functionality | No view of pending postings; no partner-confirmation search; no duplicate-profile or merge-map lookup; no policy-by-date view; no attachment reading; no language handling; no cross-case duplicate check; approvals not bound to evidence | D02, D05, D06, D15, D22, D23, D10, D11 |
| Configuration errors | Mountain Lodge still on the 30-day wait; v2's OTA rule never configured; corporate exception never configured; blank channel treated as ineligible; keyword index frozen at 2026-03-15 | D08, D09, D21, D03 |
| Data problems | Duplicate profiles; stays on merged numbers; blank channels; UTC timestamps read as local dates; reversed and re-posted transactions | D01, D02, D03, D04, D07 |
| Operational delays | Late postings after property interface outages; claims routed to the billing queue | D06, D20 |
| UI friction | Four separate screens; exact-match search; ledger grouping hides re-posts | D12, D13, D14, D07 |
| Not fixable by tools | Missing upstream records; conflicting records | D24, D25 |

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
