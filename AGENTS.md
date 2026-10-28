# AGENTS.md: guidance for Codex and other coding agents

This repository is **Stage 9 (Loyalty Support Modernization)** of a simulated hotel-group engagement. It uses
fictional companies and synthetic data only.

**One shared standard.** `CLAUDE.md` holds the project rules; this file and `.cursor/rules/project-standard.mdc`
point to the same rules and must not contradict them. The binding specification is `docs/MASTER-SPEC.md`.

## Before you change anything
1. Read `docs/implementation-status.md`, `docs/session-handoff.md` and the spec Part for your task.
2. Run the tests (`make test`, or `scripts\test.ps1` on Windows).
3. Pick one requirement ID from `docs/requirements-matrix.md`. Make one bounded change.
4. Run the checks, review the diff, update the tracking files, record your work.

## Non-negotiable rules (same as CLAUDE.md)
- No fabricated results, URLs, users, approvals, savings or tool usage.
- Never weaken, skip or delete a failing test.
- Eligibility, authorization, approval, amounts and execution are deterministic Python. A model can interpret
  and explain, never decide them.
- Domain code (`app/domain/`) never imports FastAPI, SQLAlchemy sessions, httpx or model SDKs.
- Never read or print `.env`. Use `python -m app.preflight --profile <name>`.
- No pushes, paid resources, deployments, `terraform apply` or messages without the owner's explicit OK.

## Attribution
Record which tool did the work. **Never attribute one tool's work to another.** Codex exercises (spec Part H.2,
Appendix G) are logged in `docs/tool-stack-evidence.md` with the task, time to a verified result, defects found
and tests passed. Avoid editing the same files another tool is editing at the same time.
