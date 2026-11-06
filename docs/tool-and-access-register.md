# Tool and access register (SEC-04)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

**A: development assistants · B: runtime model services · C: customer system integrations · D: logs, traces, exports, evaluation data.** Approval status is never real here: nobody at a fictional company can approve anything.

| Cat. | Connection | Purpose | Account owner | Data | Scope | Environment | Credential storage | Retention assumption | Audit | Approval | Revocation | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | Claude Code | Builds this repo | Owner | Code, synthetic data | Read and write in this repo | Owner's PC | Owner's own login | Unverified | Commit trailers | Owner's own | Sign out | Implemented |
| A | GitHub (`gh`) | Source and CI | Owner | Code | Private repo | Owner's PC, Actions | `gh` store | GitHub's terms | GitHub's log | Owner's own | Revoke token | Implemented |
| B | Anthropic API | Arm C | Owner | Redacted request text, summaries, excerpts | Messages only | Worker | `.env`, not committed | **Unverified** | `ai_runs` | **Pending the owner's go-ahead** | Console | **Configured, never called** |
| C | Mock customer API | Stands in for the platforms | Project | Synthetic members, stays, ledger | Read; write adjustments | Local | `.env` token | Local volume | `case_events` | Not applicable | Rotate the token | **Simulated** |
| C | Keycloak | OIDC profile | Project | Synthetic users | Sign-in | Local, torn down | Random per run | None | Keycloak's log | Not applicable | `down -v` | Implemented, local |
| D | App logs | Diagnostics | Project | IDs and statuses, no message text | | Local | | Container lifetime | | Not applicable | | Implemented |
| D | App database | Cases, audit, runs | Project | Synthetic personal data | | Local volume | `.env` | 365 days for closed cases | `case_events` | Not applicable | Volume removal, with the owner's OK | Implemented |
| D | Benchmark data | Evaluation | Project | Synthetic, with labels | Never in the app or images | Repo and CI | | Git | Git | Not applicable | | Implemented |
