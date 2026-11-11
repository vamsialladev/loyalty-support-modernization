# Session handoff

**Updated:** 2026-11-11, after Milestone 11 was built. It isn't merged yet: see "Waiting on the owner", items A and B.

## Where things stand
- Milestones 1-10 are on `main` in the **private** GitHub repository. The owner's filled review sheet merged as PR #30; Milestone
  11's research and RFC-0004 merged as PR #31.
- **Milestone 11 is in five stacked pull requests**, each showing only its own step: #32 foundation (base `main`) → #33 MCP
  → #34 A2A → #35 AG-UI → #36 close-out. #32 is green; the others run CI on push. Latest results: `docs/verification-log.md`,
  section "Milestone 11".
- **Work on a branch and open a pull request.** Merge with a merge commit, not squash or rebase, so cited hashes stay valid. Push with:
  `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push` (two accounts are signed in to `gh`).
- This repo's `user.email` is the noreply address. Run gitleaks before pushing; the command is in `docs/fde-tool-map.md`.
- Commit messages from PowerShell: use `git commit -F <file>`. Anything with backslashes goes through the editor tools, never a shell heredoc.

## Waiting on the owner
A. **Merge Milestone 11, in order: #32, #33, #34, #35, #36.** Claude Code's auto mode refused `gh pr merge` ("Merge Without
   Review"), even with the standing permission in `CLAUDE.md`, so it wasn't worked around. After merging one, change the next
   PR's base to `main` on GitHub (or merge it into its base: the history is the same), and wait for its CI to go green.
B. **Say yes or no to three downloads** for the independent-peer runs that Appendix C asks for. Each is free, pinned, run from a
   scratch folder, against synthetic data only. Auto mode refused the first without your OK:
   - MCP Inspector CLI 2.14.0 (`npx @modelcontextprotocol/inspector@2.14.0`): the test is ready, `tests/interop/test_mcp_inspector.py`.
   - The A2A TCK (`git clone` of `a2aproject/a2a-tck`, then `uv pip install`).
   - `@ag-ui/client` from npm, for a small Node script that reads the stream.
   Until then, PROTO-03 to PROTO-05 stay "Implemented but unverified" and `docs/protocol-test-results.md` says NOT RUN.
C. Optional: connect your Claude Code to the local MCP server (`docs/mcp.md`, "Connect a client"). It changes your Claude Code
   config, so it's yours to do.
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
`scripts\protocol_token_check.ps1` against a real Keycloak; `docs/protocol-test-results.md` for the checklist.

**Common failure modes.** A token for the wrong audience (401 by design). A missing `A2A-Version` header (-32009). Floats
from protobuf breaking a hash. A live panel bound to an element htmx replaced. All in `docs/onboarding.md` §4j.

## The Milestone 11 exercise (K.1)
The protocol services check tokens themselves and don't ask Keycloak about each one. So when you disable a client, its last
token still works until it expires (5 minutes by default; `security/evidence/protocol-token-check-2026-11-11.txt`).

**Say what someone holding a stolen MCP token could read in those 5 minutes, step by step, and which controls limit it. Then
say whether you'd add token introspection now (one call to Keycloak per request) or keep short lifetimes, and what would
change your answer.** Your answer goes in `docs/owner-exercises.md`.

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

## Milestone 12 scope (spec N.1 item 12; Appendix C)
- Performance and load tests, observability, CI/CD, Docker hardening, IaC (validate only), rollback, hosting options.
  Done when: the local CI equivalent passes, a load test report is saved, and Terraform validates.
- Carried in from Milestone 11: the protocol services as Compose services, with one issuer hostname (TD-52); load the AG-UI
  stream and MCP (`docs/scaling-and-limits.md`, Protocols).
- Hosting options and costs go to the owner before anything is created (Appendix L1).

## Trying arm B on your own stack
`stack.ps1 -Action up` rebuilds and migrates to `0010`; your data stays. Then load cases with
`uv run python -m benchmarks.intake --split dev --limit 10 --arm B`. Steps are in `docs/onboarding.md` §4f.

## Blockers
None for Milestone 12. Milestone 11's interop runs wait on item B above.
