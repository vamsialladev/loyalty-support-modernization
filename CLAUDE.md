# Project: AI Loyalty Support Modernization Platform (portfolio simulation)

Stage 9 of the simulated hotel-group engagement on vamsialla.com. This folder is the repository root: create every
file here, run every command from here, and commit only in this repo. The parent folder's `CLAUDE.md`,
`HANDOFF.md` and `PROGRESS.md` belong to the portfolio project and do not apply here.

Source of truth: `docs/MASTER-SPEC.md`. Read the relevant Part before changing code.
Presentation rules: `docs/portfolio-presentation-addendum.md` (followed from Milestone 1, fully in Milestone 19).
Site and repo conventions to match: `docs/continuity.md`.
Shared standard for every coding assistant: `AGENTS.md` (Codex) and `.cursor/rules/project-standard.mdc` (Cursor)
point to the same rules as this file. If they ever disagree, this file and the spec win; fix the other file.

## Project purpose (owner, 2026-10-28; full text in `docs/project-purpose.md`)
Stage 9 is the owner's reusable, end-to-end FDE engagement: it must work like a real company engagement from
discovery to handover, connect to real tools through adapters, and teach a newly joined engineer how every role on
an AI engagement handles each part. Apply the 11 lenses (business, data, AI, engineering, security and governance,
operations, people, tools, reuse, principal engineering, every role) inside each milestone's existing work, without
adding scope. **End every milestone** by updating, proportionately to what was built: `docs/onboarding.md`,
`docs/real-system-swap-guide.md`, `docs/role-coverage-map.md` (roles exercised, with evidence only), the principal
artifacts (`docs/technical-strategy.md`, `docs/scaling-and-limits.md`, `docs/tech-debt-register.md`, `docs/tco.md`),
`docs/fde-tool-map.md` when tools change, an RFC in `docs/rfcs/` for Milestones 6, 8, 10, 11, and
`docs/executive-brief.md` at the end of each phase. ADRs record the options considered and what would change the
decision. Note what moves into the starter kit and what is customer-specific.

## Model and mode guidance (follow at the start of every milestone)
- The owner uses **Opus for all milestones**; quality matters more than speed or usage.
- **Before starting each milestone, say whether to use plan mode, then wait for the owner to confirm.**
- Recommend plan mode for design-heavy milestones: **6** (approvals, idempotency, reconciliation), **8** (AI loop
  and harness), **10** (benchmark design), **11** (protocols), and whenever a bug survives two fix attempts.
- Claude Code cannot switch models or modes itself. The owner switches models with `/model` and plan mode with
  Shift+Tab.

## Every session
1. Read `docs/implementation-status.md` and `docs/session-handoff.md`.
2. Run `make test` (or `scripts\test.ps1` on Windows) to see the current state before editing.
3. Work only on the milestone or task named in the prompt.
4. After changes: run the relevant tests, review `git diff`, update `docs/requirements-matrix.md`,
   `docs/implementation-status.md`, `docs/verification-log.md` and `docs/session-handoff.md`.
5. Commit with a descriptive Conventional Commits message when checks pass. Never push without the owner's OK.
6. End each milestone with the Part K.1 teaching notes: what changed, why, how to verify, common failure modes,
   one exercise, then ask the owner to explain the result or make a small change.

## Rules
- Part 0 rules are non-negotiable: no fabricated results, URLs, users, approvals, savings, or tool usage.
- Never weaken or delete a failing test to get green.
- Eligibility, authorization, approval, amounts, execution: deterministic Python only.
- Domain code never imports FastAPI, SQLAlchemy sessions, httpx, or model SDKs.
- Verify library, SDK and protocol APIs in official docs; pin versions with uv (`uv.lock` is committed).
- No paid resources, terraform apply, publishing, installs of GitHub apps, or messages without the owner's
  explicit OK.
- Record which tool did each piece of work (`docs/tool-stack-evidence.md` once it exists; until then the commit
  trailer and `docs/verification-log.md`).
- Ask only when blocked by a missing decision or authorization; batch questions.
- Every piece of work maps to a requirement ID in `docs/requirements-matrix.md`. New ideas go to
  `docs/backlog.md` and are not built until the owner approves them.
- Do not start a higher scope tier while a lower tier's verified checks fail (spec Part 0.7).

## Secrets (Appendix K)
- Never open, print or `cat` `.env`. Check readiness only with `python -m app.preflight --profile <name>`,
  which prints set / missing / invalid format and never a value.
- Never ask the owner to paste a secret into chat. Never write a real value into a committed file, log,
  screenshot, fixture or prompt.
- `.claude/settings.json` denies reading `.env` files; respect it.
- After any credential rotation, prove the old credential fails.

## Portfolio writing (addendum item 8)
Plain English, short sentences, specific numbers with counts and denominators, honest about limits. Every number
shown anywhere must trace to a stored result file in this repo. Label everything as an independent portfolio
simulation with synthetic data. Current title is Senior Software Engineer; "Forward Deployed Engineer" appears
only as a role being sought.

## Windows notes
- Python 3.12 via `uv`. `make` is not installed on the owner's machine: every make target has a
  `scripts\*.ps1` equivalent.
- Two GitHub accounts are signed in to `gh`. When pushing (only with the owner's OK), use
  `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push` so the vamsialladev
  credential is used.
- Never use shell heredocs containing backslashes on Windows; write files with the editor tools instead.
