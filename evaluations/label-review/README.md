# Label review (spec E.1, requirement EVAL-04)

The owner, Vamsi Alla, agreed on 2026-10-28 to review a stratified sample of about 30 labels. This folder holds the
instructions, the sheet and the recorded result. **The application never reads this folder**; a Milestone 3 test
enforces that, so expected answers can't leak into any arm.

## Review status

| Field | Value |
|---|---|
| Reviewer | Vamsi Alla (project owner; not independent of the project, but independent of the label generator) |
| Status | **Done (2026-11-10): 2 disagree, 1 unsure, 27 not flagged, 0 corrected.** On the evidence below the owner kept both disputed labels. Two wording issues are recorded as known limitations |
| Sample | 30 cases (plan below); drawn with seed 20261102, stream `label-review` (`seed_data/generator/review_sheet.py`) |
| Result | See "Result of the review" below |
| How it was done | **Human review, AI-assisted** (the owner's words). Which assistant was used, and how, isn't recorded. If it was a Claude model, the assistance isn't independent of the generator's author |
| Recorded by | Claude Code, 2026-11-10, from the owner's message. **The sheet's reviewer columns came back empty** (both `review-sheet.csv` here and the owner's copy in Downloads are byte-identical to the committed sheet), so per-row verdicts aren't on file; the counts come from the owner's summary |

Allowed status values: Not started · Sheet ready · In progress · Done (with agreement counts) · Done, corrections
pending · Done, corrections applied.

## Result of the review (2026-11-10)

30 of 280 labels reviewed by the project owner (human review, AI-assisted): **2 disagreed, 1 unsure, 27 not flagged,
0 corrected.** Each flagged item was checked against the labeler (`evaluations/labeler.py`), the case's planted facts
and the written policy. Re-scoring the stored held-out runs under each reading:
`benchmarks/reports/heldout/label-review-sensitivity.md` (`uv run python -m evaluations.label_review`).

| Case | Reviewer | What the investigation found | Label error? | If the reviewer's reading were used |
|---|---|---|---|---|
| HO-062 (D19, two stays fit) | Disagree: the final outcome presumes ML-8565 | The pre-registered simulated member (F6, `docs/hypotheses.md`) answers "which stay" with what the scenario holds. HO-062's planted reply is "It was the stay that checked out on 2026-04-02", and only ML-8565 checked out that day. All three arms asked and got that reply. **The sheet didn't show the reply.** | No, on the written rules | **H2 flips from supported to not supported.** C credited ML-8565 after the reply in 3 of 3 runs; without the reply in the label that counts as a false approval, and H2's rule allows C no more false approvals than B. So H2 rests on this one case |
| HO-078 (D15, late June checkout) | Disagree: the queued posting isn't recorded as `pending_posting` or `posting_queue` evidence | Checkout 2026-06-24, so **version 1** applies. v1 has no pending-posting rule (`pending_posting_blocks_adjustment: false`; section 5.1 exists only in v2). v1 section 3: before 30 days, tell the member the date they can claim, 2026-07-24. The claim came on 2026-07-17. | No, on the written rules | No verdict changes. B's correct first action 72 to 71 of 80, C's 80 to 79 |
| DV-070, HO-078 | Unsure: "ineligible" for waiting-period cases | Spec B.7 allows four values (`eligible`, `ineligible`, `insufficient_evidence`, `needs_escalation`) and no "not yet". The labeler and arm B's engine both use `ineligible` with `wait_until:<date>`. The policy says a member may claim no earlier than the waiting period after checkout. | No; a wording question | No verdict changes. Only the eligibility link of the proof chain moves (C, all links held: 78 to 73 of 80) |

**Notes from the reviewer, and what they mean:**
- **D20 refund routing isn't recorded:** the label does hold it (`out_of_scope_items: ["refund_request"]` on DV-051),
  but the sheet doesn't show that field. Case success doesn't score it either; a separate check does, on 4 cases
  (`benchmarks/results/live/out-of-scope-check.json`, known limitation).
- **S03 refusal isn't recorded:** true. The label marks the other member (`other_member_referenced`, ST-002) but has
  no field for "no data about them shown". The benchmark scores business effects only (points, approvals), and
  `tests/test_red_team.py` checks that such a request changes nothing on arms B and C. Whether a reply shows the
  other member's data isn't recorded anywhere in the benchmark.
- **Received dates are missing from the sheet:** true, and the waiting period and claim window depend on them.

**Sheet gaps the review found** (the likely cause of the HO-062 disagreement): the sheet leaves out the claim's
received date, the planted member reply, out-of-scope items and the other member referenced. They should be added
before a second labeler reviews (`seed_data/generator/review_sheet.py`).

**One thing found while checking, not flagged by the reviewer:** for a waiting-period stay the label's per-stay
`earned_points` is 0 while `expected_final_points` is the full amount (DV-070: 0 and 5,850), because the labeler
zeroes earned points for any `ineligible` stay. No metric reads `earned_points`; it isn't on the sheet. Not changed.

**The owner's decisions (2026-11-10):**
- **HO-062 stands as labelled.** The owner's test: if the planted reply clearly identifies ML-8565, the label
  stands; if it's missing or ambiguous, the label is wrong. The facts: `member_reply` is "It was the stay that
  checked out on 2026-04-02." The member, GR-52140, has exactly two stays in the seeded upstream data: ML-8565,
  checkout 2026-04-02 09:55 Eastern (13:55 UTC), and ML-7988, checkout 2026-04-12. The reply fits only ML-8565.
- **HO-078 stands as labelled.** The `existing_credit` and `ineligible` wording for waiting-period stays, and their
  0 `earned_points`, are known limitations, not label errors (`docs/known-limitations.md`).
- **The disclosure stays:** H2 rests on HO-062 alone. It appears in the hypotheses report, the business-value
  reports, the executive brief, and must appear in any website or portfolio text about Stage 9
  (`tests/test_label_review.py` checks the repo's copies).

No label changed, so `docs/hypotheses.md`'s change log still reads "None yet." and no new experiment started.

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
