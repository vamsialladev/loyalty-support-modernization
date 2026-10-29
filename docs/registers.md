# Registers: access, dependencies and project risks (spec A.2)

> Simulated client engagement. Requirement DISC-08. Security risks live in `security/threat-model.md` and, from
> Milestone 9, `security/risk-register.md`. This file holds delivery and project risks.

## 1. Access and dependency register

| ID | Dependency | Category (C.3) | Needed for | Owner | Status (2026-10-28) |
|---|---|---|---|---|---|
| AD-01 | Docker Desktop and Postgres 16 image | Local tooling | Milestone 4 onward | Owner's machine | Available |
| AD-02 | Claude API key and model ID in `.env` | B. runtime model | Live arm C (M8, M10) | Owner | Blocked: needs `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| AD-03 | GitHub repository and CI | A/D. dev and CI | CI gates (M12), PRs | Owner | Manual step required: approve repo creation |
| AD-04 | Terraform CLI | Local tooling | IaC validate (M12) | Owner's machine | Missing (free install) |
| AD-05 | Keycloak container | Local tooling | OIDC profile (M9) | This repo (Compose) | Not started |
| AD-06 | Playwright and browsers | Local tooling | Browser tests (M7), screenshots (M19) | This repo | Node available; browsers not installed yet |
| AD-07 | Hosting account for a public demo | Deployment | Appendix L1 (M12) | Owner | Not requested; options and costs first |
| AD-08 | Part H tool accounts (bolt.new, Supabase, CodeRabbit, Monday, Miro, Vercel, Cursor, Codex) | A/C | M15 | Owner | Blocked per `docs/tool-access-matrix.md` |
| AD-09 | eval-harness change to register Stage 9 | Existing repo | M10 | Owner's OK | Prepared as a separate PR later |
| AD-10 | Owner's time: label review (~45 min), UAT, timing protocol, exercises | People | M3, M10, M18 | Owner | Label review agreed 2026-10-28 |

## 2. Project risk register

| ID | Risk | Likelihood | Impact | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|
| PR-01 | The synthetic environment is built to make AI win | Medium | High (credibility) | Pre-registered catalog and hypotheses before any arm code (done); controls and unfixable cases; A as-is variant; every slice where A/B beat C reported | FDE | Mitigated in part |
| PR-02 | Labels are wrong because one author wrote the generator, rules and labels | Medium | High | Labels from scenario facts only; owner reviews ~30; disclosed in every report | FDE + owner | Open (review in M3) |
| PR-03 | Held-out sample too small for clear verdicts | High | Medium | 80 held-out cases; "inconclusive" is a valid outcome; intervals always shown | FDE | Accepted |
| PR-04 | Live model runs blocked (no key or budget) | Medium | Medium | Mock for development; H2–H5 reported as NOT RUN rather than inferred | Owner | Open |
| PR-05 | Scope is very large (20 milestones, many optional labs) | High | Medium | Tiers; no higher tier while lower-tier checks fail; backlog for new ideas | FDE | Open |
| PR-06 | Free hosting can't run this stack; a paid demo costs money | High | Low | Local first; hosting options and costs to the owner before anything is created | Owner | Open (M12) |
| PR-07 | Portfolio claims drift from stored results | Medium | High | Every shown number traces to a result file; numbers check before publishing (addendum 8, 10) | FDE | Open (M19) |
| PR-08 | Tool exercises can't run (accounts, OS) | High | Low | Precise Blocked status; core never depends on them | Owner | Accepted |
| PR-09 | Mermaid diagrams don't render where they're viewed | Low | Low | Syntax kept simple; check on GitHub once the repo exists | FDE | Open |
