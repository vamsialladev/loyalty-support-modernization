# Session handoff

**Updated:** 2026-11-13, during Milestone 12 (part 1 of a few larger pull requests).

## Milestone 12, so far (2026-11-13)
- **Owner's decisions** are in `CLAUDE.md` (hosting option A at $0; no live model calls; repository public; merges).
- **The repository is public** (2026-11-13, 22:07 UTC, `main` at `f76c1d6`); secret scanning and push protection are
  on. The minutes limit (ADR-0076) is lifted: normal CI triggers and PR sizes. Held-out labels are public from this
  date, so any later held-out claim needs a new split.
- **Part 1, PR #38, merged (`f76c1d6`):** multi-stage images, Compose profiles (demo, test, enterprise-identity,
  labs), protocol services in Compose with one issuer (TD-52, labs check 10 of 10), TD-51 and TD-53 paid, environment
  files and default-credential checks, gitleaks pre-commit, `scripts\ci_local.ps1`, `opentelemetry-api` 1.45.2 (a CVE).
- **Public-readiness check:** `docs/public-readiness.md` (no blocker; the flip is recorded there).
- **Still to do in Milestone 12:** observability (OTel, logs, metrics, alerts, security events), reliability
  (breakers, backpressure, execution flag), the load test, CI/CD additions, Terraform
  (validate only), rollback and backup docs, demo hosting prep and the Render + Neon setup steps for the owner.

## Before Milestone 12
**Updated:** 2026-11-12, at the end of Milestone 11: independent peers run, five pull requests merged in order.

## Where things stand
- Milestones 1-11 are on `main` in the **private** GitHub repository. Milestone 11 merged as five pull requests, in order,
  with merge commits: #32 foundation (`db6cbc6`), #33 MCP (`b81f60c`), #34 A2A (`c22b349`), #35 AG-UI, #36 close-out
  (this file's PR, so it's the last one in). Each was merged only with its CI green.
- **CI red on #34-#36 was the runner, not the code** (2026-11-12): apt couldn't resolve Ubuntu's mirrors during
  `playwright install --with-deps`, so the tests never started; one rerun then hit the 30-minute job limit, at 83% of the
  tests, with no failures, because apt took 13 minutes. Re-run, then green. Verification log, Milestone 11, row 22.
- **Independent peers, run with the owner's OK** (`docs/protocol-test-results.md`; all opt-in, `tests/interop/`):
  - MCP Inspector CLI 2.14.0: **pass**. It negotiated MCP 2025-11-25, so the 2026-07-28 handshake has same-SDK tests only.
  - A2A TCK at `70f6f73`: **verified with limitations** (owner's decision, 2026-11-12; ADR-0072). Limitations: 45 of the 47
    required (MUST) checks that ran pass; the 2 failures are TCK scenarios the specialist rejects by design; the TCK didn't
    test authentication (it can't send tokens at that commit), which our own tests and the real-Keycloak run cover instead.
    Run: 57 passed, 5 failed, 201 skipped. It found one real gap, no `Cache-Control` on the Agent Card, now fixed and
    tested. A wrong `Content-Type` isn't refused: TD-53. **Keep the three limits with the A2A result in any portfolio
    text** (`docs/known-limitations.md`).
  - `@ag-ui/client` 1.0.4: **pass**, 4 runs (watch, start, closed window, 401).
  - Found too: the Inspector test had never run (a fixture import bug); fixed. Row 24.
- PROTO-03 and PROTO-05 are "Implemented and verified"; PROTO-04 is "Implemented and verified: with limitations" (above).
  Protocol labs score: 6 of 16, PROTO-04 counted as done with its limits named under the table.
- The old untracked copy `evaluations/label-review/review-sheet1.csv` was deleted at the owner's request (2026-11-12);
  the committed `review-sheet.csv` is unchanged.
- **Work on a branch and open a pull request.** Merge with a merge commit, not squash or rebase, so cited hashes stay valid. Push with:
  `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push` (two accounts are signed in to `gh`).
- This repo's `user.email` is the noreply address. Run gitleaks before pushing; the command is in `docs/fde-tool-map.md`.
- Commit messages from PowerShell: use `git commit -F <file>`. Anything with backslashes goes through the editor tools, never a shell heredoc.

## Waiting on the owner
A. **Decided (2026-11-12):** PROTO-04 is "Implemented and verified: with limitations" (ADR-0072). The score table names it,
   and a test checks that any such row lists its limits.
B. Optional: connect your Claude Code to the local MCP server (`docs/mcp.md`, "Connect a client"). It changes your Claude Code
   config, so it's yours to do. It would also test the 2026-07-28 handshake, which the Inspector didn't use.
0. **Eval-harness registers Stage 9** (merged as `ccbdcd4` after the review you asked for; verification log, Milestone 10, rows 23–28). Next, when you want it: tag a harness release, then add `hoteleval gate` to this repo's CI. The live dashboard still shows only Projects 1 and 2: adding Stage 9 to its pages is a separate change.
1. **Label review: done (2026-11-10).** You kept HO-062 (its planted reply names only ML-8565) and HO-078; no label changed. The wording issues are known limitations. **Keep the disclosure that H2 rests on HO-062 alone** in every results text, including the Milestone 19 case study and any website or LinkedIn text (`docs/known-limitations.md`). Your filled sheet is committed (2026-11-11): 30 agree after your decisions, notes drafted with AI help.
2. Optionally, redo A-000010 with the new Reopen button. It's still `Resolved` as `deny_claim_window`.
3. **The Codex exercise**, whenever convenient: `docs/exercises/codex-reconciliation-review.md`. It needs your Codex account.
4. **The email block:** tick "Block command line pushes that expose my email" again, if not done already.

## Decided by the owner on 2026-11-10 (also in `CLAUDE.md`)
- `.env` is back on mock. Further live runs need a new approval.
- **H3:** keep the registered definition, and keep showing both readings in every report.
- **Measurement bugs:** before a freeze, with a known cause and a test, fix and log them. **After a freeze, stop and leave a note.**
- The Milestone 10 exercise is answered: `docs/owner-exercises.md`.

## Milestone 11, in K.1 form
**What changed.** Three optional doors onto the same services: an MCP server for AI clients, an A2A coordinator and
specialist, and an AG-UI live view. None can approve, credit or change a case. With every flag off, nothing changes.

**Why.** The client's roadmap names other AI clients and another team's agent. Building the safe version now, behind
flags, is cheaper than retrofitting it. `docs/protocol-selection.md` says when REST is enough (today, mostly).

**How to verify.** `uv run pytest tests/test_protocol_auth.py tests/test_mcp_server.py tests/test_a2a.py tests/test_ag_ui.py`;
`scripts\protocol_token_check.ps1` against a real Keycloak; the independent peers with `RUN_INTEROP=1` (setup commands at the
top of each `tests/interop/*.py`); `docs/protocol-test-results.md` for the checklist.

**Common failure modes.** A token for the wrong audience (401 by design). A missing `A2A-Version` header (-32009). Floats
from protobuf breaking a hash. A live panel bound to an element htmx replaced. All in `docs/onboarding.md` §4j.

## The Milestone 11 exercise (K.1), answered (2026-11-12)
A stolen MCP token can read one customer's case data, read-only, until it expires. Introspection or a revocation list would come
for a real deployment with personal data; short lifetimes are enough for this demo. Recorded in `docs/owner-exercises.md`. One
note added there: nothing alerts on read volume yet, so that control is Milestone 12's monitoring work, not one in place.

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
- **Making the repository public:** done 2026-11-13 with the owner's OK (see the Milestone 12 section above).

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

## Milestone 12 scope (spec N.1 item 12; Appendix C)
- Performance and load tests, observability, CI/CD, Docker hardening, IaC (validate only), rollback, hosting options.
  Done when: the local CI equivalent passes, a load test report is saved, and Terraform validates.
- Carried in from Milestone 11: the protocol services as Compose services, with one issuer hostname (TD-52); load the AG-UI
  stream and MCP (`docs/scaling-and-limits.md`, Protocols).
- Hosting options and costs go to the owner before anything is created (Appendix L1).

## Trying arm B on your own stack
`stack.ps1 -Action up` rebuilds and migrates to `0010`; your data stays. Then load cases with
`uv run python -m benchmarks.intake --split dev --limit 10 --arm B`. Steps are in `docs/onboarding.md` §4f.

- Carried in from the interop runs: alerting on unusual protocol read volume (the M11 exercise); TD-53 (`Content-Type`).

## Blockers
None for Milestone 12.
