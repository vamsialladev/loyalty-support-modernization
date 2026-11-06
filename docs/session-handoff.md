# Session handoff

**Updated:** 2026-11-06, after Milestone 8. Milestone 9 is next.

## Where things stand
- Milestones 1-8 are on `main` in the **private** GitHub repository, merged through pull requests #3 onward. Latest results:
  `docs/verification-log.md`, section "Milestone 8".
- **Work on a branch and open a pull request.** Merge with a merge commit, not squash or rebase, so cited hashes stay valid.
  **Standing permission for Milestones 7-20 (`CLAUDE.md`): push, open pull requests and merge when CI is green.** Push with:
  `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push` (two accounts are signed in to `gh`).
- This repo's `user.email` is the noreply address. Run gitleaks before pushing; the command is in `docs/fde-tool-map.md`.
- Commit messages from PowerShell: use `git commit -F <file>`. A here-string with double quotes gets mangled (it happened on
  step 7). Anything with backslashes goes through the editor tools, never a shell heredoc (it put a tab in the log on step 2).

## Waiting on the owner
0. **The live smoke test costs a few hundredths of a cent, and needs your go-ahead** plus `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL=claude-haiku-5-5` in `.env`: `scripts/live_smoke_ai.py`. Until then it's recorded as NOT RUN. It blocks nothing until Milestone 10, which needs real runs.
1. **Label review:** the 30-label sheet (`evaluations/label-review/`).
2. Optionally, redo A-000010 with the new Reopen button. It's still `Resolved` as `deny_claim_window`.
3. **The Codex exercise**, whenever convenient: `docs/exercises/codex-reconciliation-review.md`. It needs your Codex account.
4. **The email block:** tick "Block command line pushes that expose my email" again, if not done already.

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

## Milestone 9 scope (spec N.1 item 9; Appendix C)
- Done when: authorization, CSRF, rate-limit, redaction and red-team tests pass; OIDC profile login works locally.
- Started and noted in the matrix: SEC-05, SEC-17, ENT-12, ENT-23, DOC-06, TEST-01, TEST-02. Bearer tokens for the API (TD-32).

## Trying arm B on your own stack
`stack.ps1 -Action up` rebuilds and migrates to `0008`; your data stays. Then load cases with
`uv run python -m benchmarks.intake --split dev --limit 10 --arm B`. Steps are in `docs/onboarding.md` §4f.

## Blockers
None for starting Milestone 9. Milestone 8's live run needs `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in `.env`.
