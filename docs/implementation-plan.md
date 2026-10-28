# Implementation plan

Order from spec Part N.1, "done when" from Appendix C, tiers from Part 0.7. A milestone starts only when the previous
milestone's checks pass, and a higher tier only when the lower tier's verified checks pass (Tier 3 items may stay
Blocked without blocking Tier 4). At the start of every milestone Claude Code says whether to use plan mode and
waits for the owner's confirmation (`CLAUDE.md`).

| M | Tier | Scope | Done when (Appendix C) | Plan mode? | Needs from the owner |
|---|---|---|---|---|---|
| 1 | 1 | Workspace, repo and access audit; continuity review; tool access matrix; tracking files; requirements matrix; guidance files; `.env` safety; preflight | Tracking files, matrix with IDs, tool access matrix exist and are linked | No (audit and docs) | — |
| 2 | 1 | Discovery package, stage 0 loyalty addendum, architecture, baseline measurement plan, threat model draft, **defect catalog, KPI tree, hypotheses (pre-registered)** | Discovery and architecture docs exist and are linked; catalog and hypotheses committed | Optional (docs; recommend no) | Miro access is optional |
| 3 | 1 | Synthetic data generator, legacy operating history, supporting documents, independent labels, ≥60 cases in 4 splits, day-one discovery analysis | Generator reproducible (same seed → same checksum) | Recommend yes for the label and split design | — |
| 4 | 1 | Mock customer API, Postgres, Alembic migrations, Compose, contract tests | `docker compose up`, migrate, seed succeed from scratch; contract tests pass | Optional | — |
| 5 | 1 | Legacy arm A, runnable end to end in the browser, instrumented | Arm A completes a case end to end in the browser | Optional | — |
| 6 | 1 | Eligibility, policy retrieval, state machine, approvals, execution, idempotency, reconciliation, durable worker, kill switch | Real-Postgres tests pass for idempotency atomicity, concurrent execute, duplicates, timeout-after-commit reconciliation, lease recovery, approval invalidation | **Yes** | Codex install if the Codex review runs here |
| 7 | 1 | Arm B and the full server-rendered UI vertical slice | Arm B works; Playwright happy path and self-approval block pass | Optional | — |
| 8 | 1 | Arm C: provider interface, mock + Claude providers, context builder, bounded loop, harness, validation; extraction; routing classifier | Every stop condition and injection test passes on mock; Claude live smoke test run or NOT RUN | **Yes** | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, a budget (in `.env`) |
| 9 | 1 | Local auth, OIDC (Keycloak), authorization, CSRF, rate limits, redaction, red-team suite | Authz, CSRF, rate-limit, redaction, red-team tests pass; OIDC login works locally | Optional | — |
| 10 | 1 | Benchmark runner, thresholds (committed first), A/B/C comparison, member journey, final-ledger proof, error analysis, business-value report | Thresholds committed before runs; A/B/C reports from actual runs; error analysis written | **Yes** | Live budget approval for arm C live runs |
| 11 | 2 | MCP, then A2A, then AG-UI | Tests pass against an independent client or peer where available | **Yes** | — |
| 12 | 2 | Load test, observability, CI/CD, Docker hardening, Terraform (validate only), rollback, hosting options | Local CI equivalent passes; load test report saved; Terraform validates | Optional | Approve creating the GitHub repo; choose a hosting option and budget (Appendix L1) |
| 13 | 2 | Drills, recovery, incident exercises | Drills recorded with actual results incl. measured restore time | Optional | — |
| 14 | 2 | Cedarpoint Inns configuration | Second-customer tests show different, correct outcomes from the same code | Optional | — |
| 15 | 3 | Actual-tool exercises (bolt.new/React, Supabase, CodeRabbit, Cursor, Monday, Miro, open models, others) | Each tool has evidence or a precise Blocked status | Optional | Account logins and tokens (batched) |
| 16 | 3 | Optional protocol labs | Each lab has evidence or a precise Blocked status | Optional | — |
| 17 | 4 | Starter kit, scaffold, telecom mini-domain, playbooks | Generated project starts and passes its smoke test | Optional | — |
| 18 | 4 | UAT, training, handover, owner exercises | UAT scripts and handover exist | Optional | Owner time for exercises and timing protocol |
| 19 | 4 | Portfolio package, real screenshots, video, website PR drafts (addendum in full) | Portfolio files exist; screenshots are real Playwright captures | Optional | OK on the video in the owner's player; OK before any website PR |
| 20 | 4 | Final clean-install verification and the Part N.2 report | Fresh clone → README quickstart → all offline tests pass | Optional | — |

Plan mode is also recommended whenever a bug survives two fix attempts.

## Known external dependencies (batched, asked only when the milestone needs them)
- Milestone 8: Claude API key and model in `.env`; spending limit in the Anthropic console.
- Milestone 12: creating the GitHub repository and pushing; a hosting option and monthly budget for the public demo.
- Milestone 15: browser logins and scoped tokens for the Part H tools.
