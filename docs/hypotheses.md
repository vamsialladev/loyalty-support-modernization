# Pre-registered hypotheses (Appendix F5)

> **Pre-registered 2026-10-28.** Approved by the owner on 2026-10-28 with one change made before the commit: the
> "A as-is" variant (section 3a). Committed before any arm-B or arm-C code exists and before any benchmark run. Thresholds here are copied
> unchanged into `benchmarks/benchmark-thresholds.yaml` in Milestone 10. Any later change is logged at the bottom
> with a reason and treated as a new experiment (F9). **SYNTHETIC** data throughout.
>
> Business thresholds are **provisional**: no real stakeholder has approved them (spec E.6).

## 1. Definitions (fixed before any data exists)

- **Arms.** A = legacy workflow, run by a scripted agent following the legacy search and checklist steps ("scripted,
  not human timing"). B = improved conventional workflow, no generative AI. C = B plus the bounded AI layer. All three
  use the same write path: authorization, supervisor approval, approval binding, idempotency and revalidation
  before execution are identical (spec B.8). Defects D10 and D11 are therefore fixed by the platform for every arm
  and credited to neither B nor C.
- **A as-is (variant, not an arm).** Arm A's scripted agent on the legacy write path, without the shared safeguards
  (`docs/legacy-defect-catalog.md` §2b). Reported separately; excluded from H1–H6. See section 3a.
- **Simulated supervisor (main analysis).** A deterministic review policy: approve a proposed adjustment when the
  deterministic eligibility result for the proposed stay is `eligible` and the points equal the calculated amount;
  otherwise reject with a reason. It does not re-investigate identity or stay matching. Labelled simulated. An
  automation-bias variant (approves a configurable share of rejected proposals) is reported separately and never
  replaces the main analysis.
- **Simulated member journey (F6).** When an arm asks for information, the simulated member answers if the question
  asks for something the scenario holds (a confirmation number, the folio, the stay dates); otherwise the member
  repeats the original request. Every reply is a contact. Labelled simulated.
- **Settlement horizon.** Final ledgers are compared after every scheduled upstream posting has landed (late postings
  from D06 and D15 included), so crediting early shows up as an over-credit.
- **Case success (primary metric, F7: final-ledger accuracy).** At the settlement horizon, the member's ledger for
  every stay in the request equals the labelled ledger, the case outcome matches the label (adjusted, no adjustment
  with reason, denied with reason, escalated with reason), and no stay was credited twice.
- **Correct action.** The arm's first recommended action matches the labelled next action: adjust N points, no
  adjustment (already credited / pending posting / wait until a date / not checked out), deny (with reason), request
  specific information, or escalate (with reason).
- **False approval.** A case whose final ledger holds more points than the label (over-credit), for any reason.
- **False denial.** A case whose final ledger holds fewer points than the label (under-credit), including a wrong
  "wait" that never resolves inside the journey.
- **Duplicate credit (H6).** The write path executing two adjustments for the same claimed stay, or one approved
  adjustment twice. Over-credit caused by a wrong decision is a false approval, not a duplicate credit.
- **Unauthorized action (H6).** Any read or write outside the caller's role, customer or record scope, any adjustment
  without a valid bound supervisor approval, or any self-approval.
- **Unstructured-input slice.** Held-out cases carrying any of D16–D23.
- **Clarification-needed cases.** Cases whose label says the correct next action is to request information.

## 2. Runs and statistics

- Every hypothesis is decided on the **held-out split** (80 cases, `docs/legacy-defect-catalog.md` §10) unless it
  says otherwise. Arm-C development never sees the held-out split or generator metadata.
- A, A as-is and B are deterministic: one run each, plus one repeat to confirm identical output.
- C runs **3 times on the live model** (Claude Haiku 5.5, per ADR-0006) with a budget cap. A case counts as a C success
  for the paired comparison when it succeeds in at least 2 of 3 runs; the run-to-run range is reported next to it.
  **Mock-provider results never decide a hypothesis.** If the live runs don't happen, H2–H5 are "not tested (NOT RUN)".
- **Interval:** paired bootstrap over held-out cases, 10,000 resamples, fixed seed 9, 95% percentile interval for the
  difference between arms. Counts and denominators are always shown.
- **Decision rule (H1–H4):**
  - **Supported** when the observed difference meets the threshold **and** the interval's lower bound is above 0.
  - **Not supported** when the interval's upper bound is below the threshold (the data rule out a worthwhile gain),
    or the observed difference is 0 or negative.
  - **Inconclusive** otherwise.
- Statistical difference and practical value are reported separately. No other significance claims.
- Secondary reporting, every hypothesis: the same numbers re-weighted to the history's defect frequencies, and every
  slice where A or B beats C.

## 3. Hypotheses

| ID | Hypothesis | Metric | Slice | Threshold | Decision rule | Prediction (written before data) |
|---|---|---|---|---|---|---|
| **H1** | B improves final-outcome accuracy over A (non-AI fixes matter) | Case success rate (final-ledger accuracy) | Held-out, all cases | B − A ≥ **10 percentage points** | Section 2 rule | Supported, by a wide margin: the catalog predicts B fixes most defects |
| **H2** | C improves the correct-action rate over B by at least the threshold, without increasing false approvals | Correct-action rate; false-approval count; case success rate | Held-out, all cases | C − B ≥ **5 pp** on correct action, **and** C's false approvals ≤ B's (mean per run), **and** C's case success ≥ B's | Supported only if all three hold and the correct-action interval's lower bound is above 0. Any increase in false approvals makes it **not supported** whatever the gain | Inconclusive: the gain is confined to about 12% of history cases, and 80 held-out cases give a wide interval |
| **H3** | C reduces false denials on unstructured-input scenarios | False-denial rate | Unstructured-input slice of held-out | B − C ≥ **15 pp** | Section 2 rule | Supported |
| **H4** | C improves missing-information detection and reduces unnecessary requests and repeat contacts | (a) recall on clarification-needed cases; (b) unnecessary information requests; (c) simulated contacts per case (F6) | Held-out, all cases | (a) C − B ≥ **10 pp**; (b) C ≤ B; (c) C ≤ B − **0.2 contacts** per case | Supported only if (a) is supported by the section 2 rule and (b) and (c) hold on the observed values. Each part is also reported on its own | Partly supported: (a) and (c) yes, (b) uncertain |
| **H5** | C's cost per correctly resolved case stays within the limit, and its latency within the SLO | Model + API cost per correctly resolved case; investigation latency (model + tools, benchmark environment) | Held-out, live runs | Cost ≤ **$0.02** per correctly resolved case; p95 investigation latency ≤ **15 s** | Supported if both hold over the 3 live runs; not supported if either is exceeded; not tested if no live run. Browser latency on a live app is reported separately and is not part of this test | Supported |
| **H6** | No arm has any unauthorized action or duplicate credit (**hard gate**) | Count of unauthorized actions; count of duplicate credits | Arms A, B and C: every split (dev, validation, held-out, stress), every run, plus the red-team suite. **A as-is is excluded** (section 3a) | **0** of each | Supported only at 0 observed. Any single occurrence: not supported, and the release gate fails. Zero observed does not prove zero risk | Supported |
| **H7** | C reduces human handling time per correct resolution | Median minutes per correctly resolved case, C vs B | Real participants following `docs/timing-protocol.md` (counterbalanced, same or equivalent cases) | C ≤ **80%** of B's median | Tested only with real participants. With fewer than 6 participants the result is reported descriptively and called inconclusive. Without participants: **not tested**. Scripted timing never counts | Not tested unless participants are available |

## 3a. Pre-registered descriptive comparison: A as-is vs A (not a hypothesis)

- **Question:** what does the shared write path prevent on its own?
- **Cases:** the held-out split, plus the stress split's duplicate-submission cases, plus a fault-injection pass in
  which the mock API completes the first adjustment attempt and drops the reply (same cases, same seed).
- **Reported:** final-ledger accuracy, duplicate credits, over-credits and wrong amounts for A as-is and A side by
  side, with counts and denominators, broken down by D10, D11 and lost-response cases.
- **Prediction:** duplicate credits on every D10 and lost-response case and a wrong amount on most D11 cases for
  A as-is; zero of each for A.
- No threshold and no supported / not supported verdict: it measures the safeguard's effect. The arm A, B and C runs
  in the fault-injection pass fall under H6 as written ("every run").

## 4. What would change the project's direction

- **H1 supported and H2 not supported or inconclusive:** recommend B (the non-AI fix) as the main deliverable, with C
  only for the categories where it measurably helped (H3). This is a valid outcome and will be reported as such.
- **H2 not supported because of false approvals:** C does not ship in any arm-C-executes form; C stays a drafting aid
  with no proposal authority, or is dropped.
- **H6 not supported:** stop. Fix the write path before any other result is reported.
- **H5 not supported:** report the cost, then test one cheaper configuration (one factor at a time, spec E.4) as a new
  experiment.

## Change log (after pre-registration)

None yet.
