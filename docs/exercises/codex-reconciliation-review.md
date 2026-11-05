# Codex exercise: independent review of the reconciliation and idempotency module

> Spec Appendix G and H.2 (TOOL-CODEX). **Status: Manual step required.** Prepared by Claude Code; not run. The owner runs
> it with their own Codex account. Nothing here is a result. Nothing in this repository may claim Codex did anything until
> `codex-comparison-sheet.csv` holds real entries.

## What this measures
Whether a second tool, reviewing independently, finds defects in the write path that Claude Code's tests and review did not.
Appendix G's claim about Codex ("reasons through edge cases") is a hypothesis to measure, not a fact.

## The bias to keep in mind
Claude Code wrote this code and its tests, so its list below is the list of an author. Codex reviews after the fact, with the
RFC and ADRs to read, so this isn't a fair race between two authors. Report it as "what an independent review added", not as
"which tool is better". Record which model and settings each tool used.

## Before you start (about 5 minutes)
1. Install and sign in to the Codex CLI yourself. Check the current install steps in OpenAI's official docs. Don't paste any
   secret into chat, and don't use the repository's `.env`: this exercise needs no API key from this project and no database
   credentials beyond the throwaway ones the compose check generates.
2. Make a separate checkout at the pinned commit. Claude Code's list was committed **after** this commit, so it isn't there
   for Codex to read:

```powershell
git worktree add ..\lsm-codex-review 560e86dfcd6d7b1154cf11aae8fe01fb863ef774
```

3. Note the start time.

## The task (paste this to Codex, as it is)

```text
Review the reconciliation and idempotency module of this repository as an independent reviewer. This is a portfolio
simulation with synthetic data.

In scope: app/services/write_path.py, app/services/job_handlers.py, app/services/jobs.py, app/worker.py,
app/services/kill_switch.py, app/services/approvals.py, app/domain/approval_binding.py, app/domain/case_states.py and
migrations 0005 to 0007. Read docs/rfcs/RFC-0001-write-path-integrity.md and ADR-0059 to ADR-0061 in docs/decisions.md for
the intended behaviour. app/adapters/mock_customer_api.py and mock_customer_api/service.py are context.

Find defects that could cause any of these:
1. A stay credited twice, or a credit for an amount, member or stay other than the one approved.
2. A credit submitted without a valid approval, after the kill switch has committed, or by someone not permitted.
3. A case left in a state that hides an uncertain outcome.
4. A deadlock, a lost update, or a lock held across a call to a customer system.
5. A job that retries without bound, or that is lost.
6. An audit event that is missing, or that claims something that didn't happen.

For each finding give: the file and line, the sequence of events that triggers it, the effect, and your confidence. Where you
can, write a failing test in tests/ that proves it. Tests that need real concurrency go in a new file marked
@pytest.mark.postgres; see tests/test_execution_postgres.py for the fixtures. Do not change application code. Do not push.
Do not read or print .env. List what you checked and found no problem with, too.
```

## Bounds
- **Scope:** only the files above. Findings about other files go in the sheet as "out of scope" and don't count.
- **Time:** stop at 2 hours of your time, or when Codex says it has finished, whichever comes first. Record the real figure.
- **Cost:** set a spending limit in your OpenAI account first; suggested $10. Record the real figure from your usage page.
- **No pushes, no merges, no application changes** in this exercise. It runs in the separate checkout.

## Running its tests

Run its new offline tests in the separate checkout:

```powershell
uv sync
```

```powershell
uv run pytest <its new test file> --no-cov -rs
```

Run any new `postgres` tests through the compose check, from that checkout, with nothing heavy running. It starts its own
throwaway stack and doesn't touch your data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\compose_check.ps1
```

## Acceptance criteria for a finding

| Verdict | Meaning |
|---|---|
| **Confirmed** | A test fails on the pinned commit and shows the claimed effect, or you and a second reader agree the sequence of events is possible from the code alone (write down that sequence) |
| **Known** | It's on Claude Code's sealed list below, with the same cause. It counts as agreement, not as a new defect |
| **Not reproduced** | A test or a careful read shows it can't happen as described. Say why |
| **Out of scope** | Outside the listed files, or about style |

A finding with no sequence of events and no test is not a defect yet, however confident it sounds.

## How to compare results
Fill in `docs/exercises/codex-comparison-sheet.csv`, one row per finding, then answer in `docs/verification-log.md`:

1. How many **confirmed** findings, and how many were **not** on Claude Code's sealed list? This is the main number.
2. How many of Claude Code's sealed items did Codex find without being told?
3. How many false alarms (not reproduced)?
4. Time to a verified result, and cost, as you measured them.
5. Which confirmed defects would have reached Milestone 10's benchmark if nobody had looked?

Don't summarize this with a winner. Small counts from one review of one module don't support that. Decide keep, drop or
undecided for the tool map (Appendix G) only from what you actually saw.

## What happens to the findings
Each confirmed defect goes to Claude Code (or you) as a bug, on a branch, fixed with its failing test, and is attributed:
"found by Codex". Claude Code's fix is attributed to Claude Code. Commit trailers must name the tool that did the work (spec
H.1). If Codex finds nothing new, that's a result too, and it goes in the log as stated.

## Claude Code's sealed list
`docs/exercises/codex-sealed-list.md`, committed after the pinned commit, with its SHA-256 recorded in the verification log.
Don't open it until Codex has finished, so your reading of its findings stays independent as well.
