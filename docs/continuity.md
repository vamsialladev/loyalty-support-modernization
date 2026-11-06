# Continuity review: how Stage 9 fits the existing engagement

**Status:** Implemented and verified (read-only review, 2026-10-28). Requirement IDs `CONT-01` to `CONT-08`.

The live site and the public repositories are the source of truth. Where they differ from `docs/MASTER-SPEC.md`,
this file follows the site and records the difference (section 12).

## 1. Sources reviewed

| Source | How | Version reviewed |
|---|---|---|
| vamsialla.com | `curl` with a cache-busting query, compared byte-for-byte with the website repo's `main` | `data/projects.json`, `projects.html`, `index.html` and two case studies were **identical** to `main` at `7a2cfe7` (2026-10-28) |
| `vamsialladev.github.io` | shallow clone, read-only | `7a2cfe7` (2026-10-28) |
| `fde-account-research-agent` (PS) | shallow clone | `967930f` (2026-10-28) |
| `hotel-ai-discovery` (0) | shallow clone | `e502e2b` (2026-10-24) |
| `hotel-ops-assistant` (1) | shallow clone | `dd01234` (2026-10-24) |
| `guest-request-agent` (2) | shallow clone | `cfe4ace` (2026-10-24) |
| `eval-harness` (3) | shallow clone | `b3e3bc5` (2026-10-24) |
| `hotel-ai-handoff` (4–5) | shallow clone | `35c7ad1` (2026-10-24) |
| `resort-activities-concierge` (6) | shallow clone | `711803c` (2026-10-28) |
| `hotel-tools-mcp` (7) | shallow clone | `3e3e700` (2026-10-27) |
| `hotel-ops-analytics-agent` (8) | shallow clone | `270765e` (2026-10-28) |
| `agent-protocols-lab` | shallow clone | `2f6fea6` (2026-10-27) |
| `hotel-ai-platform` (shared library, no stage) | shallow clone | `9fb8746` (2026-10-25) |
| `vamsialladev` (profile README) | shallow clone | `76fd8f9` (2026-10-24) |
| Local video kit | read-only listing | `C:\projects\project1\video-kit` (not a Git repository) |

No existing repository was modified. Clones live only in the session scratchpad.

## 2. The engagement as published today

From `data/projects.json` (the one place the site keeps stage status):

| Stage | Name on the site | Status | Live link label |
|---|---|---|---|
| PS | Account Research Agent (pre-sales) | Live | Account Research (live) |
| 0 | Discovery & Scoping | Published | none (documents only) |
| 1 | Hotel Operations Knowledge Assistant | Live | Assistant (live) |
| 2 | Guest Request Agent | Live | Agent (live) |
| 3 | Eval Harness | Live | Dashboard (live) |
| 4 | Production Deployment | Live | Assistant (live), Agent (live) |
| 5 | Client Handoff | Live | Assistant (live), Agent (live), Daily health check (live) |
| 6 | Resort Activities Concierge | Live | Concierge (live) |
| 7 | Hotel Tools MCP Server | Live | MCP endpoint (live) (links to a connect page) |
| 8 | Ops Analytics Agent | Live | Ops Analytics (live) |
| **9** | **Loyalty Support Modernization** (this repo) | not on the site yet | none until deployed and verified |

Engagement sentence used on the site: "One independent, simulated engagement for a fictional hotel group with two
properties and synthetic data."

## 3. Hotel group, properties and the second customer

- **Primary customer:** the site never names the group. It is "a fictional hotel group" (README quote blocks:
  "a fictional hotel group (Beach Resort, Mountain Lodge)"). Stage 7 gives it the tenant ID `hg-demo`, display
  name "Simulated hotel group (stages 0-8)". Stage 9 keeps it unnamed and uses `hg-demo` as its customer ID.
- **Properties:** `beach-resort` (Beach Resort) and `mountain-lodge` (Mountain Lodge), plus brand-wide documents
  in `shared/`. Booking IDs use `BR-####` (Beach Resort) and `ML-####` (Mountain Lodge).
- **Existing second group:** stage 7 has `hg-other` ("A second simulated hotel group, used only to prove tenant
  isolation") with one property, `city-hotel`. It is not Cedarpoint Inns.
- **Stage 9's second customer:** **Cedarpoint Inns**, a new fictional group (spec B.4). It is a separate
  deployment profile and database, not a tenant row. Recorded in `docs/decisions.md` (ADR-0012).

## 4. Loyalty program (already defined; Stage 9 reuses it)

The spec says to define a program only if none exists. One exists in stages 1 and 2:
`data/raw/shared/loyalty_program.md` (hotel-ops-assistant) and `data/policy/raw/shared/loyalty_program.md`
(guest-request-agent), **"Guest Rewards Loyalty Program"**, effective 2026-01-01, status current.

| Tier | Nights per year | Late check-out | Welcome amenity | Room upgrade |
|---|---|---|---|---|
| Silver | 5+ | 1:00 PM (free) | Bottled water | No |
| Gold | 15+ | 2:00 PM (free) | Drink voucher | Subject to availability |
| Platinum | 40+ | 4:00 PM (guaranteed) | Bottle of wine | Guaranteed one category |

- **Earning:** 10 points per US dollar spent on the room rate. Taxes, resort fees and pet fees do not earn points.
- **Verification:** always confirm the member number in the guest's PMS profile; never grant tier benefits on a
  verbal claim alone.
- **Member numbers:** `GR-` plus five digits (for example `GR-55120`). Stage 2's generator gives tiers with weights
  none 10 : Silver 4 : Gold 3 : Platinum 1.
- **What the existing program does not define:** a waiting period before missing-points requests, eligible
  booking channels, a missing-points request process, adjustment approval limits, or earlier versions. Stage 9 adds
  these as **new, versioned fictional policy documents** (spec B.6, Appendix B) that extend Guest Rewards without
  contradicting the earning rule above. Version 1 of the earning section keeps "10 points per US dollar on the room
  rate"; any change is a later version with its own effective date.
- **Existing money thresholds to stay consistent with** (brand standards, stage 0 discovery): front desk courtesy
  credits up to $50 without approval; refunds or credits over $200 need the Manager on Duty. Points adjustments are a
  different action; Stage 9 sets its own points approval limits and states how they relate.

## 5. Writing tone (observed)

- Plain English, short sentences, first person in narration and notes ("So I built this: she just asks.").
- Opens with a person and a concrete problem ("It's Monday morning and the revenue manager has a board pack due.").
- Numbers always with counts and denominators, version and date: "99% (167/168)", "version 1.3.0 (2026-10-26)".
- Failures and corrections reported next to successes: "The first recorded run scored 84%. Half the failures were
  the grader"; "one real miss reported"; "Hotel-policy questions 15/15 (11/15 before a grader fix)".
- No hype words. "Simulated" appears on the first screen of every README, card and case study.

## 6. How metrics are presented

- **Cards** (`projects.html`, feature article): exactly three `<dl class="stats">` items. The `<dt>` is the
  headline number (`99%`, `183/183`, `5/6`, `$0.76`); the `<dd>` gives the denominator, runs, held-out result,
  and what a latency figure measures. Examples:
  - "183/183 · dev checks, 61 cases × 3 runs (43/45 held out, one real miss reported)"
  - "$0.76 · per 1,000 messages; p95 6.7 s model + tools, median 7.8 s in the browser on the live app"
  - "99% · execution accuracy on 56 dev questions × 3 runs (100% held out); $0.28 per 1,000 questions, p95 4.31 s
    plan + query + answer, p50 4.28 s / p95 5.47 s in the browser on the live app"
- **Case-study results:** a table per eval with `Dev | Held-out` columns, each cell `NN% (n/N)`; a caption naming
  the model, version, date and run count ("Claude Haiku 5.5, version 1.3.0 (with the hotel-policy step,
  2026-10-26), 3 runs each"); the first published run kept below for honesty; report file names given.
- **README "At a glance":** a two-column table with rows Problem, Solution, Measured quality, Cost.
- **Latency:** always labelled with what it measures (model + tools / plan + query + answer vs. in the browser on the
  live app) and both are reported.
- **Cost:** per 1,000 requests (questions, messages, emails, calls); "$0.00 per 1,000 calls: the server calls no
  model" when no model is used.
- **Business value:** labelled "projection", pessimistic / base / optimistic.

## 7. Status vocabulary

- **Public (site):** `Live` (at least one verified live link labelled "<name> (live)"), `Published` (document-only
  stage), `Built` (code and case study public, no live link yet), `Next`, `Planned`. Stage 9 shows **Built** until
  a live link is deployed and verified, then **Live** (addendum item 1).
- **Internal (this repo):** the spec Part 0.4 labels (Implemented and verified, Implemented but unverified,
  Configured but untested, Simulated, Documentation-only, Manual step required, Blocked, Deferred, Not applicable),
  plus `Planned (M#)` for requirements no milestone has reached yet.

## 8. Exact site conventions for the Stage 9 card and pages (addendum items 1–4)

**Stage list entry** (`projects.html` `#stages`, `index.html` compact list; both generated from `projects.json` by
`assets/site.js`, with a no-JavaScript copy written by `scripts/site_sync.py`):
`<li class="stage" data-status="…">` → `stage-num` → `tag` (`tag live` for Live) → `<h3>` name → `<p>` the
`delivers` text → `.links` (Case study →, "<App> (live) →", GitHub →) → `p.small.wake-note` "Free hosting: if the
app is asleep, click ‘wake up’ and give it about 30 seconds." (only when a free-hosted live link is present).

**projects.json fields:** `stage`, `name`, `status`, `summary`, `delivers`, `links[{label, url}]`.

**Feature card** (`projects.html`, `<article class="feature">`): `<!-- DEMO-VIDEO -->` slot → `figure.slip` with
`aria-label="Real output from …"`, a `p.q` line naming the input and "(real output …, synthetic data)" and a short
output line → `p.label` "Independent project · simulated hotel group, synthetic data" → `<h3>` → one-paragraph
description → `dl.stats` (three) → `.links`: "<App> (live) →" (only when live), "Case study →", "Watch the demo
(M:SS, AI-narrated) →" linking to `projects/<slug>.html#demo`, "GitHub →" → wake note when free-hosted.

**"How I work" table** (`projects.html` `#how-i-work-lifecycle`): rows Scope, Build, Deploy, Operate, Hand over,
each listing stage links. Stage 9 adds itself to Build, Deploy and Operate (write path, reconciliation, drills).

**Case study** (`projects/<slug>.html`): crumb "Projects › <short name>" → demo hero `#demo` with
`<h2>Watch the demo (AI-narrated, M:SS)</h2>`, `<video>` with poster `.webp`, `.mp4` source and `.vtt` captions,
the line "Narrated with a generated voice; captions included.", a one-sentence summary of what was recorded, a
`<details>` "Read the narration" transcript, "Try the live app" (or nothing if not hosted), "My own-voice recording
will replace the generated narration.", wake note → eyebrow "Case study · stage N" → `<h1>` → lede → the
simulated-engagement paragraph ("Every number below comes from a saved report or test run in the repository.") →
"Code on GitHub" → numbered sections: 01 Problem, 02 Approach, 03 Architecture, 04 A real output, 05 Results,
06 What the eval taught me, 07 Trade-offs, 08 Engineering, 09 Business case (projection), 10 Limitations,
11 What's next.

**Head tags:** `<title>` "<Name> | Case study | Vamsi Alla"; description, canonical, Open Graph and Twitter tags;
`og:image` `assets/og-<slug>.png` (1200×630) whose alt text repeats the three card numbers; JSON-LD
`SoftwareSourceCode`; the site-wide CSP meta tag (self, self-hosted fonts, GoatCounter only).

**Proposed Stage 9 names:** slug `loyalty-support-modernization`, page `projects/loyalty-support-modernization.html`,
OG image `assets/og-loyalty-support-modernization.png`, video `videos/loyalty-support-modernization-demo.mp4`.

## 9. README conventions (addendum item 5)

From stage 8 (the most recent), in order: title → badges (CI, Python 3.12, Ruff, MIT, coverage gate) → a bold
one-paragraph value statement → a quote block "**Stage N of a simulated client engagement** for a fictional hotel
group (Beach Resort, Mountain Lodge). All the data is synthetic… Discovery and scoping (stage 0): [hotel-ai-discovery]"
→ `<!-- DEMO-VIDEO -->` and an `AI-NARRATED-DEMO` block (thumbnail linking to the case-study player, "Demo video (M:SS,
AI-narrated)", MP4 download, captions, "The narrator is an AI voice (Kokoro); my own-voice version will replace it.")
→ "Try it live" line with "(free hosting: may take ~30 s to wake)" and caps → At a glance → The problem → What it
does → Architecture (Mermaid) → Results → Business value → Design at scale → Security & guardrails → Run locally →
Limitations and roadmap → Skills demonstrated → Configuration → Commands → Troubleshooting → Testing and quality →
Documentation → Author → License.

## 10. Existing synthetic data shapes

- **Bookings** (stage 2 generator, stage 7 `bookings.json`): `id`/`booking_id` (`BR-1042`), `hotel_group_id`,
  `property`, guest name, email (`@example.com` or `@mail.test`), phone (`+1 … 555 ….`), `check_in`, `check_out`
  (ISO dates), `room_type`, `room`, `tier`, `member_number`, `rate_usd`, rate plan (`Flexible`/non-refundable),
  status, notes. Stage 2 seed 42, simulated today Monday 2026-11-02. Stage 8's bookings database has a `channel`
  column.
- **Policy documents:** Markdown with YAML front matter (`title`, `effective`, `status`), one folder per property
  plus `shared/`; an outdated `policies_2024_OLD.md` exists in stage 1 to test stale documents.
- **Eval cases** (`eval-harness` schema): `id`, `project`, `property`, `category`, `split` (`dev`, `held-out`,
  `visitor`), `input`, `expected` (with `behaviour` in `answer`, `refuse`, `escalate`, `greeting`, `off_topic`),
  `categories`, `tags`, `origin`, `notes`.
- **Synthetic PII conventions:** made-up names, `example.com`/`.test` emails, `555` phone numbers. Stage 9 follows
  them so redaction tests look like the other stages'.

## 11. CI and eval conventions

- **CI** (`.github/workflows/ci.yml`, stage 8): ruff lint + format check; pytest with a coverage gate (80% in stage
  8, 70% minimum portfolio-wide) and the model replaced so no API key is needed; free eval gates that re-score saved
  runs without calling the model; a red-team gate using the shared corpus from `hotel-ai-platform`; `pip-audit`;
  CycloneDX SBOM; lychee link check; gitleaks over full history.
- **Evals:** labelled dev and held-out sets; 3 runs for dev; held-out written last and never tuned on; reports saved
  as `eval/reports/<kind>-<date>-<split>[-label].{jsonl,md}` with raw outputs kept so a grader fix re-scores old runs;
  cost per 1,000, p50/p95, prompt-injection and refusal cases; grader false positives re-scored and disclosed.
- **Harness registration:** `eval-harness`'s `schema.py` has a fixed `PROJECTS` allowlist (p1, p2) and
  `PROPERTIES = ("beach-resort", "mountain-lodge")`. Registering Stage 9 (and any Cedarpoint case) needs a small,
  reviewed change to `eval-harness`, prepared as a separate PR for the owner (Milestone 10, requirement `REUSE-03`).
- **Default model:** Claude Haiku 5.5 in every stage. Stage 9's live-model default is the same; anything else is
  justified in `docs/decisions.md`.

## 12. Differences between the spec and the site (site wins)

| Topic | Spec says | Site / repos show | Stage 9 follows |
|---|---|---|---|
| Loyalty program | Define one if none exists | Guest Rewards exists (tiers, earning rule) | Reuse Guest Rewards; add only missing-points rules as new versioned documents |
| Hotel group name | "the same fictional hotel group" | Unnamed; tenant `hg-demo` | Keep it unnamed; `hg-demo` |
| Second group | Cedarpoint Inns | Stage 7 has an unnamed `hg-other` / `city-hotel` | Cedarpoint Inns is new and separate; `hg-other` is not reused |
| Video label | "Narrated with a generated voice; captions included." | Case study uses that line; card link says "(M:SS, AI-narrated)"; README says "AI-narrated" and names Kokoro | Use all three exactly as the site does |
| Status badge | Live or Built | Also `Published` for document-only stages | Built until verified live, then Live |
| Repos | List of 11 | Also `hotel-ai-platform` (shared guardrails, PII, red-team corpus; pinned by tag) and `streamlit-keep-awake` | Consider `hotel-ai-platform` for PII redaction and the red-team corpus (`REUSE-08`) |
| Protocol demos | Stage 9 builds MCP, A2A, AG-UI plus labs | `agent-protocols-lab` already has one small demo per protocol (MCP, A2A, ACP, ANP, Agora, AG-UI, A2UI, AP2, UCP, x402) | Stage 9's protocol work must connect to the loyalty domain and cite the lab, not repeat it (`REUSE-09`) |
| Hosting | FastAPI + Postgres; AWS / Supabase / Vercel | Every live app runs on Streamlit Community Cloud (free); stage 7 on Vercel | A FastAPI + Postgres app does not fit Streamlit Cloud; hosting options and costs go to the owner before anything is created (Appendix L1) |
| Retrieval | Postgres full-text search baseline | Stages 1–2 use BM25 (+ optional hybrid) | Postgres FTS as the spec says; reuse stage 1's citation and "check with a manager" refusal conventions, not its index |

## 13. Reuse map (spec 0.7), with concrete pointers

| Existing stage | What Stage 9 reuses | Where | Milestone |
|---|---|---|---|
| 0 Discovery | Four-check test (felt it, would pay, first version in a week, know the first user); discovery Q&A format; SOW, pricing, security-questionnaire structure | `hotel-ai-discovery/docs/PROBLEM_SELECTION.md`, `DISCOVERY.md`, `SOW.md`, `PRICING.md`, `SECURITY_QUESTIONNAIRE.md` | 2 |
| 1 Knowledge Assistant | Citation style and the "check with a manager" refusal; the Guest Rewards document | `hotel-ops-assistant/data/raw/shared/loyalty_program.md` | 6–8 |
| 2 Guest Request Agent | Approval UX ("needs manager approval", staff approve before anything happens); booking and member-number shapes. **The difference: stage 2 only proposes, while stage 9 executes money-like actions, with idempotency and reconciliation** (M7, `templates/case_b.html`; RFC-0001) | `guest-request-agent/scripts/make_data.py`, `views/` | 3, 7 |
| 3 Eval Harness | Case schema, report format, Wilson intervals, judge-calibration approach; register Stage 9 via a reviewed PR | `eval-harness/src/hoteleval/` | 10 |
| 4–5 Production & Handoff | Runbook, SLO, budget and handoff templates | `hotel-ai-handoff/` | 12–13, 18 |
| 7 MCP Server | Role decides tools and fields, tenants invisible to each other, every call audited | `hotel-tools-mcp/` | 11 |
| 8 Ops Analytics | Optional: make the synthetic legacy history queryable for the day-one analysis | `hotel-ops-analytics-agent/` | 3 (optional) |
| Shared library | PII redaction and red-team corpus | `hotel-ai-platform/` | 9 |
| Video kit | Playwright storyboard recording, Kokoro narration (`af_heart`, 0.95), captions, audio audit (`audio_audit.py --live`), `numbers_check.py`, `og_render.py`, `check_live_links.py` | `C:\projects\project1\video-kit` | 19 |
