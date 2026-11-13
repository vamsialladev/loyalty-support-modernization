# Portfolio coverage map

**Status:** first version, 2026-10-28 (requirement `P0-06`). Built from the continuity review of the live site and
repositories (`docs/continuity.md`). Stage 9 cells say **planned** until this repo has evidence; they become
**proven** with a link only when a test or stored report backs them. Final update in Milestone 19.

Legend: **proven** = shipped and measured in that stage (evidence in its repo or case study) · **partial** = present
but not the stage's focus · **planned (stage N)** · blank = not covered.

| Capability | PS | 0 | 1 | 2 | 3 | 4–5 | 6 | 7 | 8 | 9 (this repo) | 10 (future) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Discovery and scoping | proven | proven | | | | | | | | planned (loyalty addendum to stage 0) | |
| Retrieval and citations | proven (quotes re-checked) | | proven | partial (stage 1 search) | | | proven | partial | partial | planned (Postgres FTS, versioned policies) | |
| Agents and tool use | proven | | | proven | | | proven | partial | proven | planned (bounded state-machine loop) | |
| Human-in-the-loop | | | partial ("check with a manager") | proven (staff approve sends) | proven (owner labels) | partial (staff role) | proven (staff approve bookings) | proven (credits pending manager) | | planned (supervisor approval, no self-approval) | |
| Evals and judges | proven | | proven | proven | proven (judge vs labels) | proven | proven | proven | proven | planned (≥60 cases, 4 splits) | |
| Legacy benchmark (A vs B vs C) | | | | | | | | | | planned (Appendix F) | |
| Write-path integrity (binding, idempotency, reconciliation) | | | | | | | | | | planned (Milestone 6) | partial (outbox at scale) |
| Document AI (extraction, vision, review routing) | | | | | | | | | | planned (Appendix H) | |
| Classical ML / small-model baseline | | | | | | | | | | planned (Appendix I) | |
| Text-to-SQL and analytics | | | | | | | | | proven | planned (optional, legacy history) | |
| MCP and protocols | | | | | | | partial (AG-UI, AP2 sandbox docs) | proven | partial (policy over MCP) | proven: MCP and AG-UI with independent clients (MCP Inspector, `@ag-ui/client`); A2A verified with limitations (A2A TCK: 45 of the 47 required checks that ran pass; the 2 failures are scenarios rejected by design; auth not tested by the TCK, covered by our tests and a real-Keycloak run) | |
| Security and governance | partial | proven (questionnaire) | partial | partial | | proven (redaction, kill switch) | partial (red team) | proven (roles, audit) | proven (SQL guard, red team) | planned (threat model, red team on business effects) | |
| Enterprise identity (OIDC, SSO) | | | | | | partial (SSO documented) | | partial (API-key roles) | | planned (local Keycloak OIDC) | |
| Cloud IaC and deployment | | | partial (Streamlit Cloud) | partial (Streamlit Cloud) | partial | proven (Docker, Neon, budgets) | partial | partial (Vercel) | partial | planned (Terraform AWS, validate only) | |
| Production ops and handoff | | | | | | proven (runbooks, SLOs, health check) | | | partial (daily check) | planned (drills, measured restore) | |
| Event-driven systems and observability | | | | | | partial (logs, monitoring) | | | | planned (OpenTelemetry) | planned (Kafka, AIOps) |
| Workflow automation | | | | | | | | | | documentation only (decision guide) | planned |

**Covered by no stage:** model pretraining, ML research, speech (voice input or output in a product), mobile apps,
large-scale data engineering. The demo videos use a generated voice, but no stage builds a speech feature.

The "proven" cells for stages PS–8 describe what their case studies and READMEs present today; their evidence lives
in those repositories. This file does not re-measure them.
