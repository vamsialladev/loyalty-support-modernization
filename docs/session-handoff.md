# Session handoff

**Updated:** 2026-11-05, after Milestone 6, ready to start Milestone 7.

## Where things stand
- Milestones 1-6 are on `main` in the **private** GitHub repository, merged through pull requests #3 to #10. Latest
  results: `docs/verification-log.md`, section "Milestone 6".
- **Work on a branch and open a pull request.** Merge with a merge commit, not squash or rebase, so cited hashes stay valid.
  **The permission to push and merge covered Milestone 6's pull requests only (D10). Ask again for Milestone 7.** Push with:
  `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push` (two accounts are signed in to `gh`).
- This repo's `user.email` is the noreply address. Run gitleaks before pushing; the command is in `docs/fde-tool-map.md`.
- Commit messages from PowerShell: use `git commit -F <file>`. A here-string with double quotes gets mangled (it happened on
  step 7). Anything with backslashes goes through the editor tools, never a shell heredoc (it put a tab in the log on step 2).

## Waiting on the owner
1. **Upgrade your stack (D4).** Exact commands: `docs/onboarding.md` §4d. In short: `update-local-env.ps1`, preflight,
   `stack.ps1 -Action up`, `stack.ps1 -Action seed`. Your data stays. Not run for you: `.env` and your volume are yours.
2. **Label review:** the 30-label sheet (`evaluations/label-review/`).
3. **The Milestone 6 exercise** (below), and optionally redoing A-000010 with the new Reopen button.
4. **The Codex exercise**, whenever convenient: `docs/exercises/codex-reconciliation-review.md`. It needs your Codex account.
5. **The email block:** tick "Block command line pushes that expose my email" again, if not done already.

## The Milestone 6 exercise (K.1)
A supervisor approves an adjustment. The worker's submission times out; two lookups find nothing after the settle window, so the
job resubmits with the same key. That works. Then suppose it had instead run out of attempts, the approval expired, and an agent
requested again, which creates a new approval and a new key. **Why is the same-key retry safe while the new-key path isn't, and
what would you ask a real vendor to size that risk?** Then, if you like, a small change: turn the switch off on the Configuration
page, try Execute on an approved case, and read what the page and the job do.

## Known and open
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

3. **Before Milestone 7, say whether to use plan mode and wait for the owner.** `CLAUDE.md` lists it as optional.

## Milestone 7 scope (spec N.1 item 7; Appendix C)
- Arm B: corrected rules through `app/domain/eligibility.py`, consolidated evidence, better search (synonyms, D12), validation.
- It plugs in through `app/services/arm_review.py::review_for`, with arm B's view of the evidence in the hash.
- The complete server-rendered console (UI-01, B.13), and the JSON API moved here (API-01, API-02).
- Playwright: the happy path and the self-approval block for arm B, plus reopening and reconciliation in the browser (TEST-05).
- `docs/executive-brief.md` at the end of the core-build phase.

## Blockers
None for Milestone 7. Milestone 8's live run needs `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in `.env`.
