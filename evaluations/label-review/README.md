# Label review (spec E.1, requirement EVAL-04)

The owner, Vamsi Alla, agreed on 2026-10-28 to review a stratified sample of about 30 labels. This folder holds the
instructions, the sheet and the recorded result. **The application never reads this folder**; a Milestone 3 test
enforces that, so expected answers can't leak into any arm.

## Review status

| Field | Value |
|---|---|
| Reviewer | Vamsi Alla (project owner; not independent of the project, but independent of the label generator) |
| Status | **Not started.** Waiting for Milestone 3 to generate the cases and fill `review-sheet.csv` |
| Sample | 30 cases (plan below), seed recorded when drawn |
| Result | Not yet recorded |
| Recorded by | Claude Code, after the owner returns the filled sheet |

Allowed status values: Not started · Sheet ready · In progress · Done (with agreement counts) · Done, corrections
pending · Done, corrections applied.

## Why this review matters
Labels decide every benchmark number. They come from the generator's scenario facts and the written policy, never
from a model, but Claude Code wrote both the generator and the rules. A second pair of eyes on a sample is the only
check that the labels mean what the policy says. Reports will state the outcome exactly: how many labels were
reviewed, how many agreed, what was corrected. If the sample shows systematic errors, the whole label set is
regenerated and the sample redrawn.

## Sampling plan (stratified, seeded)

| Stratum | Cases | How chosen |
|---|---|---|
| Controls K01–K06 | 6 | One of each |
| Defects AI may help with: D16, D18, D19, D20, D22, D23 | 6 | One of each |
| Not fixable: D24, D25 | 2 | One of each |
| Policy-date and boundary defects: D04, D06, D08, D09, D15 | 5 | One of each |
| Other defects: D01, D02, D03, D05, D07, D10, D12, D13, D17, D21 | 6 | 6 of the 10, drawn with a fixed seed |
| Safety scenarios S01–S05 | 5 | One of each |
| **Total** | **30** | About 15 from held-out, 10 from dev, 5 from stress (held-out labels decide the hypotheses) |

D14 (evidence on four screens) is structural and has no label of its own. Reviewing held-out labels does not
contaminate the held-out split: the reviewer is not building any arm.

## How to review (about 45 minutes, roughly 1.5 minutes per case)

1. Open `review-sheet.csv` in Excel (or any spreadsheet). One row per case.
2. Read, left to right: the member's request (`request_text`, `attachment_summary`), then the facts the systems hold
   (`member_facts`, `stay_facts`, `ledger_facts`), then `policy_version_applied`. The policy documents are in
   `policies/` (Milestone 3); `docs/legacy-defect-catalog.md` section 1 has the short version.
3. Decide yourself what should happen **before** reading the `label_*` columns. Then compare.
4. Fill in three columns only:
   - `reviewer_verdict`: **agree**, **disagree** or **unsure**.
   - `reviewer_corrected_fields`: for disagree, which label columns are wrong and what they should say, for example
     `label_expected_points=2890; label_next_action=adjust`.
   - `reviewer_note`: anything else, in a few words. For unsure, say what's unclear (often the policy wording is the
     real problem, which is worth knowing).
5. Don't edit any other column. Save as CSV with the same name and tell Claude Code it's done.

### What each label means
| Column | Meaning |
|---|---|
| `label_eligibility` | `eligible`, `ineligible`, `insufficient_evidence` or `needs_escalation` (spec B.7) |
| `label_expected_points` | Points owed for each claimed stay after the settlement horizon, `stay=points` pairs; 0 when none |
| `label_existing_credit` | `none`, `credited`, `pending_posting` or `partial` |
| `label_required_evidence` | What an agent must have looked at to decide correctly |
| `label_next_action` | `adjust`, `no_adjustment_credited`, `no_adjustment_pending`, `wait_until:<date>`, `not_checked_out`, `deny:<reason>`, `request_info:<what>`, `escalate:<reason>` |
| `label_clarification_needed` | `yes` / `no` |
| `label_escalation_needed` | `yes` / `no` |
| `label_rationale` | One or two sentences from the generator: which facts and which policy section produce the label |

### Judgement calls to apply consistently
- **Identity:** two matching identifiers (member number, email, phone, date of birth) are enough; a name alone is not.
- **Dates:** the policy version is the one in force on the checkout date in Eastern time.
- **Attachments are evidence, not records.** A folio can lead to a stay in the system; it can't replace a missing one.
- **When two stays fit a vague description**, the correct action is to ask, not to pick one.
- **Safety cases:** judge the business effect (points, approvals, data shown), not the wording of a reply.

## What happens after the review
1. Claude Code counts the verdicts and records them in the status table above, in `docs/verification-log.md` and in
   requirement EVAL-04 (`docs/requirements-matrix.md`).
2. Every disagree and unsure is investigated. A wrong label is fixed at its source (the generator rule or the policy
   text), the affected cases are regenerated, and the change is logged with its reason. A wrong label is never fixed
   by hand in the dataset.
3. If corrections touch held-out cases after any benchmark run, that run is marked superseded and re-run.
4. Reports say "30 of N labels reviewed by the project owner; X agreed, Y corrected, Z unclear", never "labels
   verified".
