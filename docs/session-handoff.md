# Session handoff

**Updated:** 2026-11-10, after Milestone 10 and the owner's decisions. Milestone 11 is next, in a fresh session.

## Where things stand
- Milestones 1-10 are on `main` in the **private** GitHub repository, merged through pull requests #3 onward. Latest results:
  `docs/verification-log.md`, section "Milestone 10".
- **Work on a branch and open a pull request.** Merge with a merge commit, not squash or rebase, so cited hashes stay valid.
  **Standing permission for Milestones 7-20 (`CLAUDE.md`): push, open pull requests and merge when CI is green.** Push with:
  `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push` (two accounts are signed in to `gh`).
- This repo's `user.email` is the noreply address. Run gitleaks before pushing; the command is in `docs/fde-tool-map.md`.
- Commit messages from PowerShell: use `git commit -F <file>`. A here-string with double quotes gets mangled (it happened on
  step 7). Anything with backslashes goes through the editor tools, never a shell heredoc (it put a tab in the log on step 2).

## Waiting on the owner
0. **Eval-harness registers Stage 9** (merged as `ccbdcd4` after the review you asked for; verification log, Milestone 10, rows 23–28). Next, when you want it: tag a harness release, then add `hoteleval gate` to this repo's CI. The live dashboard still shows only Projects 1 and 2: adding Stage 9 to its pages is a separate change.
1. **Label review (you're doing this next):** the 30-label sheet (`evaluations/label-review/`).
2. Optionally, redo A-000010 with the new Reopen button. It's still `Resolved` as `deny_claim_window`.
3. **The Codex exercise**, whenever convenient: `docs/exercises/codex-reconciliation-review.md`. It needs your Codex account.
4. **The email block:** tick "Block command line pushes that expose my email" again, if not done already.

## Decided by the owner on 2026-11-10 (also in `CLAUDE.md`)
- `.env` is back on mock. Further live runs need a new approval.
- **H3:** keep the registered definition, and keep showing both readings in every report.
- **Measurement bugs:** before a freeze, with a known cause and a test, fix and log them. **After a freeze, stop and leave a note.**
- The Milestone 10 exercise is answered: `docs/owner-exercises.md`.

## The Milestone 10 exercise (K.1), answered
Arm C beat arm B by 78 to 71 of 80, and H3 is "supported". But if a person worked every escalation correctly, it would be 78 to 77, and H3 wouldn't be supported.

**Say which reading you'd give a hotel's operations director, in two sentences, and what you'd measure in a pilot to settle it. Then say what handoff cost would make arm C not worth running.** Your answer goes in `docs/owner-exercises.md`.

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

## Milestone 11 scope (spec N.1 item 11; Appendix C)
- MCP, then A2A, then AG-UI. Done when tests pass against an independent client or peer where available. **RFC first** (`docs/rfcs/`). SEC-01's remaining protocol specs and SEC-16's callbacks finish here.
- It needs no money and no accounts. A key isn't needed: protocols run on the mock.

## Trying arm B on your own stack
`stack.ps1 -Action up` rebuilds and migrates to `0010`; your data stays. Then load cases with
`uv run python -m benchmarks.intake --split dev --limit 10 --arm B`. Steps are in `docs/onboarding.md` §4f.

## Blockers
None for Milestone 11.
