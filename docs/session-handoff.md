# Session handoff

**Updated:** 2026-11-06, after Milestone 9. Milestone 10 is next.

## Where things stand
- Milestones 1-9 are on `main` in the **private** GitHub repository, merged through pull requests #3 onward. Latest results:
  `docs/verification-log.md`, section "Milestone 9".
- **Work on a branch and open a pull request.** Merge with a merge commit, not squash or rebase, so cited hashes stay valid.
  **Standing permission for Milestones 7-20 (`CLAUDE.md`): push, open pull requests and merge when CI is green.** Push with:
  `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push` (two accounts are signed in to `gh`).
- This repo's `user.email` is the noreply address. Run gitleaks before pushing; the command is in `docs/fde-tool-map.md`.
- Commit messages from PowerShell: use `git commit -F <file>`. A here-string with double quotes gets mangled (it happened on
  step 7). Anything with backslashes goes through the editor tools, never a shell heredoc (it put a tab in the log on step 2).

## Waiting on the owner
0. **Set a spending limit in the Anthropic Console,** if you haven't. Live runs are approved with a **hard cap of $5 total** (2026-11-06), and the settings are in `.env` (2026-11-07). The code stops itself at the cap, but the console's limit holds even if the code is wrong.
1. **Label review:** the 30-label sheet (`evaluations/label-review/`).
2. Optionally, redo A-000010 with the new Reopen button. It's still `Resolved` as `deny_claim_window`.
3. **The Codex exercise**, whenever convenient: `docs/exercises/codex-reconciliation-review.md`. It needs your Codex account.
4. **The email block:** tick "Block command line pushes that expose my email" again, if not done already.

## The Milestone 9 exercise (K.1)
Customer scope is enforced by our queries and tests, not by the database. The tests found one real gap already: the approvals list showed other customers' requests.

**Say what the worst outcome is if a new query forgets the scope, and who would notice. Then say whether you'd add Postgres row-level security now, or wait until two customers really share a deployment, and what it would cost.** Your answer goes in `docs/owner-exercises.md`.

## The Milestone 8 exercise (K.1)
Arm C's model can tell the system that a multi-issue message needs no person to read it first. An injected message could try to make it say so.

**Say what the worst outcome of that is, step by step, and which controls limit it. Then say whether you'd keep this power with the model, or take it away and accept a slower arm C.** Your answer goes in `docs/owner-exercises.md`.

## The Milestone 7 exercise (K.1)
Arm B wants two matching identifiers before it treats someone as the member. Arm A accepts an exact member number alone. So at
Milestone 10, arm B may do worse than arm A on some simple cases, by asking when arm A would just credit the points.

**Should we relax arm B's rule to one identifier when the number is exact, to raise its score? Give your reasoning, including what
could go wrong, and what fairness rule applies if we change it after seeing results.** Your answer goes in `docs/owner-exercises.md`.

## Known and open
- **Upgrade tests must use a volume built by the old code.** A faked old state passed while the real one failed (ADR-0058,
  updated; verification log, Milestone 6, rows 45-50). New migrations get checked by `scripts\upgrade_check_m5.ps1`
  through the compose check, which runs it automatically.
- **Local test runs are slow under load.** The offline suite took 35 min 6 s here, against about 3 min on CI, at 99-100% CPU.
  Another project's server and a screen recorder were using 3-4 cores. The compose check once failed on a health check because of
  it (ADR-0052, updated). Close heavy apps first if you can.
- **The whole offline suite didn't run locally after step 3**, because of that load: each step ran the affected files and the
  compose check locally, with the whole suite on CI before merging. Every step's CI was green before its merge.
- **Exactly-once isn't promised:** RFC-0001, risks; `docs/known-limitations.md`.
- **The owner's "unhealthy" run has no proven cause**, though the same symptom has now been seen under load (ADR-0052, updated).
- **Making the repository public** stays the owner's decision. When approved: `gh repo edit
  vamsialladev/loyalty-support-modernization --visibility public --accept-visibility-change-consequences`, then turn on secret
  scanning and push protection.

## Start the next session with
1. Read `CLAUDE.md`, `docs/MASTER-SPEC.md`, this file and `docs/implementation-status.md`.
2. Run the checks, one at a time (regenerate data first after a fresh clone; install Chromium once):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\data.ps1 -Action generate
```

```powershell
uv run playwright install chromium
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\compose_check.ps1 -Browser
```

3. Follow the standing instructions in `CLAUDE.md`.

## Milestone 10 scope (spec N.1 item 10)
- Benchmark runner, thresholds, A/B/C comparison, error analysis, business-value report. **RFC first** (`docs/rfcs/`).
- Thresholds are committed before any aggregate score (ADR-0048). Held-out data isn't for tuning.
- SEC-19's repeated model tests belong with the real runs.
- Real runs are approved with a **hard cap of $5 total**, across the smoke test and the live evaluation. The runner must stop itself at the cap, and not rely on the settings alone. Keep mock and live results separate: different folders, and labelled in every report.

## Trying arm B on your own stack
`stack.ps1 -Action up` rebuilds and migrates to `0010`; your data stays. Then load cases with
`uv run python -m benchmarks.intake --split dev --limit 10 --arm B`. Steps are in `docs/onboarding.md` §4f.

## Blockers
None. The live smoke test passed on 2026-11-07 (`benchmarks/results/live/smoke/`). Milestone 10's live evaluation can run once its runner is ready and its configuration is frozen.
