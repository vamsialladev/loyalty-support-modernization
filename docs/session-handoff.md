# Session handoff

**Updated:** 2026-11-05, after Milestone 6 and the upgrade fix, with the owner's stack upgraded. Milestone 7 planning is next.

## Where things stand
- Milestones 1-6 are on `main` in the **private** GitHub repository, merged through pull requests #3 to #11 (#11 is the upgrade fix below). Latest
  results: `docs/verification-log.md`, section "Milestone 6".
- **Work on a branch and open a pull request.** Merge with a merge commit, not squash or rebase, so cited hashes stay valid.
  **Standing permission for Milestones 7-20 (`CLAUDE.md`): push, open pull requests and merge when CI is green.** Push with:
  `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push` (two accounts are signed in to `gh`).
- This repo's `user.email` is the noreply address. Run gitleaks before pushing; the command is in `docs/fde-tool-map.md`.
- Commit messages from PowerShell: use `git commit -F <file>`. A here-string with double quotes gets mangled (it happened on
  step 7). Anything with backslashes goes through the editor tools, never a shell heredoc (it put a tab in the log on step 2).

## Waiting on the owner
1. **Label review:** the 30-label sheet (`evaluations/label-review/`).
2. Optionally, redo A-000010 with the new Reopen button. It's still `Resolved` as `deny_claim_window`.
3. **The Codex exercise**, whenever convenient: `docs/exercises/codex-reconciliation-review.md`. It needs your Codex account.
4. **The email block:** tick "Block command line pushes that expose my email" again, if not done already.

## The Milestone 6 exercise (K.1)
Answered and recorded in `docs/owner-exercises.md`.

## Known and open
- **Upgrade tests must use a volume built by the old code.** A faked old state passed while the real one failed (ADR-0058,
  updated; verification log, Milestone 6, rows 45-50). Milestone 7's migrations get checked by `scripts\upgrade_check_m5.ps1`
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

3. Follow the standing instructions in `CLAUDE.md`. Milestone 7's choices are in ADR-0062.

## Milestone 7 scope (spec N.1 item 7; Appendix C)
- Arm B: corrected rules through `app/domain/eligibility.py`, consolidated evidence, better search (synonyms, D12), validation.
- It plugs in through `app/services/arm_review.py::review_for`, with arm B's view of the evidence in the hash.
- The complete server-rendered console (UI-01, B.13), and the JSON API moved here (API-01, API-02).
- Playwright: the happy path and the self-approval block for arm B, plus reopening and reconciliation in the browser (TEST-05).
- `docs/executive-brief.md` at the end of the core-build phase.

## Blockers
None for Milestone 7. Milestone 8's live run needs `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in `.env`.
