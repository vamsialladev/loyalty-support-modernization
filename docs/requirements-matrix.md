# Requirements matrix

Every requirement in `docs/MASTER-SPEC.md` and `docs/portfolio-presentation-addendum.md` has an ID here, mapped to
its tier (spec Part 0.7), milestone (Part N.1), completion-score category (Part 0.5), implementation, evidence and
status.

- **Status** uses the Part 0.4 labels. `Planned (M#)` means no milestone has reached the requirement yet.
- **Score** is the Part 0.5 completion-score category: `core` (core product functionality), `bench` (benchmarks
  and evaluation), `tools` (actual-tool exercises), `proto` (protocol labs), `sec` (security controls),
  `personal` (the owner's demonstrated understanding), `other` (tracked, not in the six scores).
- `python scripts/matrix_scores.py` counts the scores from this table; `docs/implementation-status.md` shows the
  latest output. A row counts as done only when its status is "Implemented and verified" (or "Not applicable").
- Rows are added, never silently removed. A deferred or dropped requirement keeps its row with the reason.

## Part 0: working rules, tracking, continuity (Tier 1 unless noted)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| P0-01 | Tracking files exist and are kept current (plan, status, matrix, checklist, verification log, decisions, limitations, handoff) | 0.5 | 1 | 1 | other | `docs/*.md` | `tests/test_repo_guidance.py::test_tracking_files_exist` | Implemented and verified |
| P0-02 | Six separate completion scores maintained | 0.5 | 1 | 1 | other | `scripts/matrix_scores.py`, `docs/implementation-status.md` | `tests/test_matrix_scores.py` | Implemented and verified |
| P0-03 | Resolved design decisions (0.6) recorded ADR style | 0.6, A.3 | 1 | 1 | other | `docs/decisions.md` ADR-0001–0010 | `tests/test_repo_guidance.py::test_decisions_cover_resolved_topics` | Implemented and verified |
| P0-04 | Part 0.4 status labels used everywhere | 0.4 | 1 | 1 | other | this file, `docs/implementation-status.md` | `tests/test_matrix_scores.py::test_every_status_is_a_known_label` | Implemented and verified |
| P0-05 | Backlog with proposed tiers; Stage 10 items recorded as "Stage 10" | 0.7 | 1 | 1 | other | `docs/backlog.md` | `tests/test_repo_guidance.py::test_backlog_lists_stage_10` | Implemented and verified |
| P0-06 | Portfolio coverage map, stages 0–10 × capability categories, proven / planned / not covered | 0.7 | 4 | 1, 19 | other | `docs/portfolio-coverage-map.md` (first version) | — | Implemented but unverified |
| P0-07 | Scope tiers enforced: no higher tier while a lower tier's checks fail | 0.7 | 1 | all | other | `CLAUDE.md` rules | reviewed at each milestone | Planned (M2) |
| P0-08 | Session handoff carries exact state, blockers, next commands | 0.3, 0.5 | 1 | all | other | `docs/session-handoff.md` | — | Implemented but unverified |
| P0-09 | Never push, publish, buy, deploy or message without explicit OK | 0.3 | 1 | all | other | `CLAUDE.md` | no push or remote exists (verification log 2026-10-28) | Implemented but unverified |
| GUIDE-01 | `CLAUDE.md` with the D.2 rules, a "Model and mode guidance" section and a reference to the addendum | D.2, owner | 1 | 1 | other | `CLAUDE.md` | `tests/test_repo_guidance.py::test_claude_md_has_mode_guidance` | Implemented and verified |
| GUIDE-02 | `AGENTS.md` and Cursor rules point to the same standard, no contradictions | H.2, D.2 | 1 | 1 | other | `AGENTS.md`, `.cursor/rules/project-standard.mdc` | `tests/test_repo_guidance.py::test_agent_guides_point_to_claude_md` | Implemented and verified |
| GUIDE-03 | Development harness for sessions (inspect → status → pick → checks → bounded change → diff → validate → record) | H.2 | 1 | 1 | other | `CLAUDE.md` "Every session", `AGENTS.md` | — | Implemented but unverified |
| TOOLMAT-01 | Workspace, repo and access audit; tool access matrix | N.1 (1), H.1 | 1 | 1 | other | `docs/tool-access-matrix.md` | verification log 2026-10-28 (tool version checks) | Implemented and verified |
| CONT-01 | Hotel group and property names recorded | 0.7 | 1 | 1 | other | `docs/continuity.md` §3 | verification log (repo clones, live diff) | Implemented and verified |
| CONT-02 | Loyalty tier names and benefits recorded (existing program reused) | 0.7 | 1 | 1 | other | `docs/continuity.md` §4 | verification log | Implemented and verified |
| CONT-03 | Writing tone recorded | 0.7 | 1 | 1 | other | `docs/continuity.md` §5 | verification log | Implemented and verified |
| CONT-04 | Metric presentation (counts, runs, held-out, dates, versions) recorded | 0.7 | 1 | 1 | other | `docs/continuity.md` §6 | verification log | Implemented and verified |
| CONT-05 | Status vocabulary recorded | 0.7 | 1 | 1 | other | `docs/continuity.md` §7 | verification log | Implemented and verified |
| CONT-06 | Existing synthetic data shapes recorded | 0.7 | 1 | 1 | other | `docs/continuity.md` §10 | verification log | Implemented and verified |
| CONT-07 | Existing CI and eval conventions recorded | 0.7 | 1 | 1 | other | `docs/continuity.md` §11 | verification log | Implemented and verified |
| CONT-08 | Spec-vs-site differences recorded; site followed | 0.7 | 1 | 1 | other | `docs/continuity.md` §12 | verification log | Implemented and verified |
| REUSE-01 | Stage 0 loyalty addendum: fictional stakeholder sessions, four-check test, SOW addendum, pricing from measured costs, security-questionnaire deltas | 0.7 | 1 | 2 | other | `docs/stage0-loyalty-addendum.md` (pricing is a method until M10 measures costs) | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| REUSE-02 | Stage 1 citation and "check with a manager" refusal conventions; stage 1 as a policy tool if its interface fits, else documented why not | 0.7 | 1 | 6–8 | core | — | — | Planned (M6) |
| REUSE-03 | Stage 9 cases and results exported in eval-harness format; Stage 9 registered with regression gates (reviewed PR to eval-harness, owner's OK) | 0.7 | 2 | 10 | bench | — | — | Planned (M10) |
| REUSE-04 | Stage 2 approval-UX conventions; explicit statement that stage 2 proposes and stage 9 executes with idempotency and reconciliation | 0.7 | 1 | 7 | core | — | — | Planned (M7) |
| REUSE-05 | Stage 4–5 runbook, SLO, budget, handoff templates reused; only new content added | 0.7 | 2 | 12–13, 18 | other | — | — | Planned (M12) |
| REUSE-06 | Stage 7 MCP conventions for loyalty read-only tools; extend vs. `protocols/mcp/` choice explained | 0.7 | 2 | 11 | proto | — | — | Planned (M11) |
| REUSE-07 | Optional: synthetic legacy history queryable by stage 8 | 0.7 | 2 | 3 | other | Not built (optional); history files are ready to load into stage 8 if wanted | — | Deferred: optional, waits for the owner's interest (backlog) |
| REUSE-08 | Evaluate `hotel-ai-platform` (PII redaction, red-team corpus) for reuse; adopt or record why not | continuity | 1 | 9 | sec | — | — | Planned (M9) |
| REUSE-09 | Protocol work connects to the loyalty domain and cites `agent-protocols-lab` instead of repeating it | continuity | 2 | 11, 16 | proto | — | — | Planned (M11) |
| STORY-01 | One headline sentence of measured results (A vs B vs C held-out, final-ledger accuracy, false approvals) | 0.7 | 4 | 19 | other | — | — | Planned (M19) |
| STORY-02 | One 3-minute demo: messy multi-stay request with receipt image → cited investigation → supervisor approval → execution → injected timeout and reconciliation, no duplicate → benchmark slide incl. where AI did not help | 0.7 | 4 | 19 | other | — | — | Planned (M19) |

## Project purpose (owner, 2026-10-28; `docs/project-purpose.md`)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| PURP-01 | Project purpose recorded and applied; `CLAUDE.md` section; ADRs record options considered and what would change the decision | Purpose | 4 | all | other | `docs/project-purpose.md`, `CLAUDE.md`, `docs/decisions.md` | `tests/test_repo_guidance.py::test_project_purpose_recorded` | Implemented and verified |
| PURP-02 | Real-system swap guide updated every milestone | Purpose | 4 | all | other | `docs/real-system-swap-guide.md` (early draft) | `tests/test_repo_guidance.py::test_purpose_documents_exist` | Implemented but unverified |
| PURP-03 | Onboarding guide updated every milestone | Purpose | 4 | all | other | `docs/onboarding.md` (early draft) | `tests/test_repo_guidance.py::test_purpose_documents_exist` | Implemented but unverified |
| PURP-04 | Principal artifacts kept current: technical strategy, scaling and limits, tech-debt register, TCO | Purpose | 4 | all | other | `docs/technical-strategy.md`, `docs/scaling-and-limits.md`, `docs/tech-debt-register.md`, `docs/tco.md` (early drafts) | `tests/test_repo_guidance.py::test_purpose_documents_exist` | Implemented but unverified |
| PURP-05 | One RFC per design-heavy milestone (6, 8, 10, 11) | Purpose | 4 | 6, 8, 10, 11 | other | `docs/rfcs/README.md` (template) | — | Planned (M6) |
| PURP-06 | Executive brief, one page per phase | Purpose | 4 | all | other | `docs/executive-brief.md` (phase 1) | `tests/test_repo_guidance.py::test_purpose_documents_exist` | Implemented but unverified |
| PURP-07 | Role coverage map: 17 roles, evidence-only status, interview questions, roles exercised per milestone | Purpose | 4 | all | other | `docs/role-coverage-map.md` | `tests/test_repo_guidance.py::test_role_coverage_map_lists_every_role` | Implemented but unverified |
| PURP-08 | Public-data option: licence, terms, no personal data, credit, synthetic stays default | Purpose | 4 | 3 | other | `docs/data-sources.md` | `tests/test_repo_guidance.py::test_purpose_documents_exist` | Implemented but unverified |
| PURP-09 | `portfolio/role-pitches/`: one file per role with pitch, verified evidence, interview questions | Purpose | 4 | 19 | other | — | — | Planned (M19) |
| PURP-10 | `portfolio/engagement-method.md` and a pilot/discovery offer template; never presented as past client work | Purpose | 4 | 19 | other | — | — | Planned (M19) |
| PURP-11 | `docs/using-at-a-company.md`: approvals, approved profile, real adapters, employer IP and personal-project policies | Purpose | 4 | 1 | other | `docs/using-at-a-company.md` | `tests/test_repo_guidance.py::test_purpose_documents_exist` | Implemented and verified |
| EVAL-06 | Model-written paraphrase stress slice (labels from facts, outputs stored), reported separately from template text so template wording can't flatter any arm (owner, 2026-10-28) | Owner | 3 | 15 | bench | — | — | Planned (M15) |

## Appendix K: credentials and access (Tier 1, Milestone 1)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| ACC-01 | `.env.example` kept from the supplied template, comments only, no values | K2.1 | 1 | 1 | sec | `.env.example` | `tests/test_secrets_hygiene.py::test_env_example_has_no_secret_values` | Implemented and verified |
| ACC-02 | `.gitignore` covers `.env`, `.env.*` (except the example) and key files | K2.2 | 1 | 1 | sec | `.gitignore` | `tests/test_secrets_hygiene.py::test_env_files_are_git_ignored` | Implemented and verified |
| ACC-03 | `.claude/settings.json` deny rules for reading `.env` | K2.3 | 1 | 1 | sec | `.claude/settings.json` | `tests/test_secrets_hygiene.py::test_claude_settings_deny_env` (file and rules only) | Configured but untested |
| ACC-04 | `docs/accounts-setup.md`: per tool sign-up link, free tier, minimal token, variable, spending limit, revocation | K2.4 | 1 | 1, 15 | other | `docs/accounts-setup.md` (first version) | — | Documentation-only |
| ACC-05 | Preflight readiness report: per variable set / missing / invalid format, never values; features unlocked | K2.5, B.2 | 1 | 1 | sec | `app/preflight.py` | `tests/test_preflight.py` | Implemented and verified |
| ACC-06 | gitleaks in CI and as a pre-commit hook | K2.6 | 1 | 12 | sec | First CI runs gitleaks v8.30.1 over the full history (ADR-0053); pre-commit hook in M12 | `.github/workflows/ci.yml` | Planned (M12) |
| ACC-07 | A test fails if any value from `.env` appears in tracked files | K2.6 | 1 | 1 | sec | `tests/test_secrets_hygiene.py` | `tests/test_secrets_hygiene.py::test_no_env_secret_value_in_tracked_files` | Implemented and verified |
| ACC-08 | Rotation procedure documented and exercised once with a test credential; old credential proven to fail | K2.7, PA-09 | 1 | 9, 18 | sec | — | — | Planned (M9) |
| ACC-09 | Every `(verify)` variable name checked against current vendor docs; source recorded | K1 | 3 | 15 | tools | — | — | Planned (M15) |
| ACC-10 | Never read or print `.env`; preflight is the only readiness check | K1 | 1 | all | sec | `CLAUDE.md`, `app/preflight.py` | `tests/test_preflight.py::test_output_never_contains_values` | Implemented and verified |

## Part A: discovery, business case, governance (Tier 1, Milestone 2)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| DISC-01 | Discovery package files: customer-discovery, business-requirements, product-requirements, workflow, architecture, legacy-discovery | A.2 | 1 | 2 | other | `docs/customer-discovery.md`, `business-requirements.md`, `product-requirements.md`, `workflow.md`, `architecture.md`, `legacy-discovery.md` | `tests/test_discovery_docs.py::test_document_covers_required_topics`, `::test_document_is_linked_from_readme` | Implemented and verified |
| DISC-02 | Fictional customer context, stakeholder map (sponsor, agent, supervisor, admin, auditor, IT, security, ops, data owner) | A.2 | 1 | 2 | other | `docs/customer-discovery.md` §1–2 | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| DISC-03 | Personas, interview guide, labelled FICTIONAL interview examples | A.2 | 1 | 2 | other | `docs/customer-discovery.md` §3–5 (labelled FICTIONAL) | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| DISC-04 | Current and proposed workflows: journey, boundaries, ownership, manual steps, handling costs | A.2 | 1 | 2 | other | `docs/workflow.md` | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| DISC-05 | Problem framing incl. when ordinary software suffices, what AI adds, stop/redesign conditions | A.2 | 1 | 2 | other | `docs/customer-discovery.md` §6 | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| DISC-06 | Business and nonfunctional requirements, MVP scope, exclusions | A.2 | 1 | 2 | other | `docs/business-requirements.md` §2–5 | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| DISC-07 | System inventory, integration contracts, data quality assessment | A.2 | 1 | 2 | other | `docs/legacy-discovery.md` §3–6 | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| DISC-08 | Access and dependency register, risk register | A.2 | 1 | 2 | other | `docs/registers.md` | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| DISC-09 | Success metrics and acceptance criteria | A.2 | 1 | 2 | other | `docs/business-requirements.md` §6 | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| DISC-10 | Pilot and rollout plan, milestone plan, scope-change template | A.2 | 1 | 2 | other | `docs/business-requirements.md` §7–9 | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| DISC-11 | RACI | A.2 | 1 | 2 | other | `docs/governance.md` §2 | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| DISC-12 | Architecture diagram, tradeoffs, prototype vs pilot vs production expectations | A.2 | 1 | 2 | other | `docs/architecture.md` | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| DEC-01 | Decisions: AI vs rules, build vs buy, managed vs self-hosted, integration options, REST vs MCP, FTS vs embeddings, single agent vs orchestration, data boundaries, operational ownership | A.3 | 1 | 2 | other | `docs/decisions.md` ADR-0019 to ADR-0027 | `tests/test_discovery_docs.py::test_decisions_cover_spec_a3_topics` | Implemented and verified |
| DEC-02 | Decision guide: managed backends, visual prototyping, external code review, workflow automation, self-hosted models | A.3 | 1 | 2 | other | `docs/decisions.md` decision guide | `tests/test_discovery_docs.py::test_decisions_cover_spec_a3_topics` | Implemented and verified |
| GOVN-01 | Responsibility boundaries (app/FDE, identity, platform, security, data owner, product, incident, vendor) | A.4 | 1 | 2 | other | `docs/governance.md` §1 | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| GOVN-02 | Templates: access request, security exception, risk acceptance (owner, rationale, controls, expiry) | A.4 | 1 | 2 | other | `docs/governance.md` §4 | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| GOVN-03 | Technical vs organizational controls distinguished; no fabricated sign-offs | A.4 | 1 | 2 | other | `docs/governance.md` §3 | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |

## Part B: core product (Tier 1)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| ARCH-01 | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Postgres 16 | B.1 | 1 | 4 | core | FastAPI, Pydantic v2, SQLAlchemy 2.1, Alembic 1.20, psycopg 3, `postgres:16.15-alpine` (pinned in `uv.lock` and compose) | `tests/test_compose.py::test_compose_binds_locally_pins_images_and_requires_secrets`, `tests/test_mock_api.py::test_migration_matches_the_table_definitions` | Implemented and verified |
| ARCH-02 | Ports and adapters: domain never imports web, DB session, HTTP or model SDKs (enforced by a test) | B.1 | 1 | 4 | core | `app/domain/` (dataclasses only), `app/ports/`, `app/adapters/` | `tests/test_app_shell.py::test_domain_code_imports_no_web_database_http_or_model_sdk` | Implemented and verified |
| ARCH-03 | Modular monolith plus separate mock customer API; no needless services, frameworks, vector DBs | B.1 | 1 | 4 | core | App placeholder + separate `mock_customer_api` service and database; no extra services | `tests/test_compose.py::test_compose_binds_locally_pins_images_and_requires_secrets`; compose check 2026-10-29 | Implemented and verified |
| PROF-01 | Six operating profiles (portfolio, live-model, discovery, staging, approved, enterprise-identity) | B.2 | 1 | 1, 6 | core | `app/preflight.py` profile table | `tests/test_preflight.py::test_all_six_profiles_defined` | Implemented but unverified |
| PROF-02 | UI banner: SYNTHETIC DATA · profile · AI mode (MOCK / LIVE model ID) · customer | B.2 | 1 | 7 | core | M5: banner on every page (SYNTHETIC DATA · profile · AI mode: none for arm A · customer · simulated time); MOCK/LIVE model ID with arm C | `tests/test_console_web.py::test_every_page_has_the_banner_and_security_headers` | Planned (M7) |
| PROF-03 | No silent fallback between providers or data destinations | B.2 | 1 | 1, 8 | core | `app/preflight.py` (provider without key is not ready) | `tests/test_preflight.py::test_selected_provider_without_key_is_not_ready` | Implemented but unverified |
| PROF-04 | `python -m app.preflight --profile X` reports readiness without printing secrets | B.2 | 1 | 1 | core | `app/preflight.py` | `tests/test_preflight.py` | Implemented and verified |
| PROF-05 | Four access types kept separate (dev assistant, runtime model, customer system, deployment) | B.2 | 1 | 1 | sec | `docs/tool-access-matrix.md` §2 | — | Documentation-only |
| MOCK-01 | Mock API endpoints: member, stay, ledger, ticket create, adjustment submit (idempotency key), adjustment status | B.3 | 1 | 4 | core | `mock_customer_api/api.py`: members, stays, ledger, posting queue, tickets, adjustments (Idempotency-Key required), status lookup | `tests/test_mock_api.py::test_adapter_reads_map_to_canonical_records`, `tests/test_mock_api.py::test_ticket_creation`, `tests/test_mock_api.py::test_missing_idempotency_key_is_rejected` | Implemented and verified |
| MOCK-02 | Versioned OpenAPI contracts and adapter interfaces | B.3 | 1 | 4 | core | `mock_customer_api/contracts/openapi-v1.json` (v1.0.0); port `app/ports/customer_systems.py` | `tests/test_mock_api.py::test_committed_contract_matches_the_service`, `tests/test_mock_api.py::test_contract_uses_the_customers_field_names` | Implemented and verified |
| MOCK-03 | Realistic IDs and timestamps, pagination, typed errors | B.3 | 1 | 4 | core | Generator IDs, `ADJ-`/`TCK-` IDs, UTC timestamps, cursor pagination (max 100), RFC 9457 problem+json | `tests/test_mock_api.py::test_ledger_pagination_is_complete`, `tests/test_mock_api.py::test_validation_errors_name_the_field` | Implemented and verified |
| MOCK-04 | Operation and idempotency record persisted atomically | B.3 | 1 | 4 | core | `mock_customer_api/service.py::submit_adjustment`: one transaction (ADR-0039) | `tests/test_mock_api_postgres.py::test_failure_before_commit_writes_nothing`, `tests/test_mock_api_postgres.py::test_twenty_concurrent_requests_with_one_key_apply_once` | Implemented and verified |
| MOCK-05 | Failure cases: auth, 429, timeouts, 503, malformed, schema change, duplicates, partial, completed-but-response-lost | B.3 | 1 | 4 | core | Faults: auth, 429, timeout, 503, malformed, schema change, duplicate, partial, commit-then-lost; typed adapter errors | `tests/test_mock_api.py::test_faults_raise_typed_errors`, `tests/test_mock_api.py::test_partial_ledger_is_never_returned_as_complete`, `tests/test_mock_api.py::test_commit_then_lost_is_uncertain_and_then_found` | Implemented and verified |
| MOCK-06 | Deterministic failure injection (header + seeded scenarios) | B.3 | 1 | 4 | core | `X-Mock-Fault` header + seeded rule file, only with `MOCK_API_FAULTS=true` (ADR-0038) | `tests/test_mock_api.py::test_unknown_fault_and_disabled_switches_are_refused`, `tests/test_mock_api.py::test_seeded_fault_rules_fire_a_limited_number_of_times` | Implemented and verified |
| MOCK-07 | Reset and seed control commands | B.3 | 1 | 4 | core | `python -m mock_customer_api.seed` (--reset, --cleanup), `/_control/seed`, `/_control/reset`; `app.seed` | `tests/test_mock_api.py::test_control_seed_and_reset`, `tests/test_app_shell.py::test_seed_command_migrates_then_calls_the_mock` | Implemented and verified |
| MOCK-08 | Contract tests incl. malformed and schema-changed responses | B.3, D | 1 | 4 | core | In-process contract tests incl. malformed and schema-changed responses; wire-level adapter tests | `tests/test_mock_api.py::test_schema_change_missing_field_and_extra_field`, `tests/test_mock_api.py::test_wrong_structure_is_malformed` | Implemented and verified |
| MOCK-09 | Reconciliation jobs against the mock API | B.3 | 1 | 6 | core | — | — | Planned (M6) |
| MOCK-10 | Seeded scenarios: the 12 listed in B.3 | B.3 | 1 | 4 | core | Data scenarios from the generator (M3) + API scenarios in `mock_customer_api/config/fault_rules.yaml` (timeout, rate limit, temporary failure, commit-then-lost) | `tests/test_compose.py::test_fault_rules_reference_known_faults`, `tests/test_generator.py::test_every_catalog_item_is_seeded` | Implemented and verified |
| CUST-01 | Two customers differ in policy rules, field mappings, waiting periods, approval limits | B.4 | 2 | 14 | core | — | — | Planned (M14) |
| CUST-02 | Adapt through config and adapters, never a code copy; separate profiles and databases | B.4 | 2 | 14 | core | — | — | Planned (M14) |
| CUST-03 | No tenant-isolation or multitenancy claim beyond what is implemented and tested | B.4 | 2 | 14 | sec | — | — | Planned (M14) |
| DATA-01 | Reproducible generator: fixed seeds, configurable scale, referential integrity, realistic timestamps (same seed → same checksum) | B.5 | 1 | 3 | core | `seed_data/generator/` (seed 20261102, `--scale`), `benchmarks/datasets/v1/manifest.json` | `tests/test_generator.py::test_committed_manifest_is_reproduced`, `tests/test_generator.py::test_same_seed_same_checksums_and_different_seed_differs` | Implemented and verified |
| DATA-02 | Generates members, stays, channels, ledger, policy versions, requests, notes, events, approvals, adjustments | B.5 | 1 | 3 | core | `seed_data/generator/world.py`, `scenarios.py`, `history.py` (members, stays, channels, ledger, policies, requests, notes, events, approvals, adjustments) | `tests/test_generator.py::test_referential_integrity` | Implemented and verified |
| DATA-03 | All B.5 scenarios incl. exact waiting-period boundary days and embedded injection text | B.5 | 1 | 3 | core | Scenario builders for D01-D25, K01-K06, S01-S05, B01-B02; exact boundary days (D04) | `tests/test_generator.py::test_every_catalog_item_is_seeded`, `tests/test_generator.py::test_waiting_period_boundary_in_eastern_time` | Implemented and verified |
| DATA-04 | Scenario proportions documented as configurable assumptions | B.5 | 1 | 3 | core | `seed_data/generator/config/scenario_mix.yaml` (labelled assumptions) | `tests/test_generator.py::test_history_frequencies_match_the_configured_mix` | Implemented and verified |
| DATA-05 | Seed, reset, cleanup commands | B.5 | 1 | 3 | core | `make data / data-reset / data-clean / data-verify`, `scripts/data.ps1` | `tests/test_generator.py::test_cli_verify_and_clean` | Implemented and verified |
| DATA-06 | `docs/data-dictionary.md` documents every field | B.5 | 1 | 3 | core | `docs/data-dictionary.md` (generated from the models) | `tests/test_generator.py::test_data_dictionary_is_up_to_date` | Implemented and verified |
| DATA-07 | Never derived from real records; fluency not claimed as realism | B.5 | 1 | 3 | core | Invented name lists and phrase banks in the repo; `docs/data-sources.md` | — | Implemented but unverified |
| POL-01 | Per source: authoritative source, freshness, mapping, owner, conflict rule; validation of missing/conflicting/stale/changed data | B.6 | 1 | 2, 6 | core | Source register in `docs/legacy-discovery.md` §5; data validation in M6 | — | Planned (M6) |
| POL-02 | Fictional versioned policies with IDs, effective dates, checksum, status, superseded versions; one set per customer | B.6, App. B | 1 | 3 | core | `policies/hg-demo/` (earning v1-v2, missing points requests v1-v2; rule parameters in front matter) | `tests/test_generator.py::test_labeler_recomputes_every_stored_label` | Implemented and verified |
| POL-03 | Ingestion: validate, chunk, store source text, Postgres FTS baseline | B.6 | 1 | 6 | core | — | — | Planned (M6) |
| POL-04 | Policy selected by business date (checkout); citations open exact excerpt and version; provenance and retrieval time | B.6 | 1 | 6 | core | — | — | Planned (M6) |
| POL-05 | Controlled publishing with regression checks; changed policy/evidence invalidates pending approvals | B.6 | 1 | 6 | core | — | — | Planned (M6) |
| POL-06 | Never invent policy; escalate when policy cannot support a recommendation | B.6 | 1 | 6, 8 | core | — | — | Planned (M6) |
| POL-07 | Authorization filters content before model context; derived data treated as sensitive | B.6 | 1 | 8 | sec | — | — | Planned (M8) |
| POL-08 | Retrieval approach and limitations documented | B.6 | 1 | 6 | core | — | — | Planned (M6) |
| ELIG-01 | Pure Python eligibility parameterized by customer config; typed result `eligible / ineligible / insufficient_evidence / needs_escalation` with points, reasons, policy refs | B.7 | 1 | 6 | core | `app/domain/eligibility.py`, `app/domain/policy.py`, `app/domain/business_time.py`, `app/services/customer_config.py`; used by arms B and C from M7 and M8 | `tests/test_eligibility.py`, `tests/test_eligibility_differential.py` (agreement with the independent labeler on the dev split; 5 wrong-rule checks) | Implemented and verified |
| ELIG-02 | Model can never override eligibility, calculation, permissions, approval or execution | B.7 | 1 | 8 | core | — | — | Planned (M8) |
| ARMA-01 | Arm A legacy: queue, separate member/stay search, ledger lookup, keyword policy search, rules, manual evidence, notes, escalation, approval, simulated adjustment; runnable end to end in the browser | B.8 | 1 | 5 | core | `app/arms/legacy/`, `config/legacy/hg-demo-legacy-rules.yaml`, `app/services/cases.py`, `app/services/write_path.py`, `app/web/` (queue, case, four evidence screens, approvals); closes need the evidence their code claims (ADR-0054) | `tests/browser/test_legacy_e2e.py::test_legacy_arm_completes_a_case_end_to_end_in_the_browser`, `tests/test_case_workflow.py::test_a_rule_based_close_is_refused_while_evidence_is_incomplete_whatever_the_note` | Implemented and verified |
| ARMA-02 | Legacy limitations documented by kind (functionality, missing, config, data, delays, UI friction); not made incompetent | B.8 | 1 | 5 | core | `docs/legacy-discovery.md` §1, §2, §2a (each limit → defect ID → file → test); limits only from the pre-registered catalog (ADR-0043, ADR-0050) | `tests/test_legacy_rules.py::test_rules_file_documents_every_deliberate_deviation` | Implemented and verified |
| ARMA-03 | Arm A benchmarked by a scripted agent that follows the legacy search and checklist steps, labelled "scripted, not human timing"; simulated supervisor with a documented policy | App. B, F7 | 1 | 5 | bench | `benchmarks/agents/legacy_scripted.py` (reading policy in its docstring; same services and permissions as the browser; ADR-0048); scoring in M10 | `tests/test_scripted_agent.py::test_every_dev_case_reaches_a_resting_state_without_errors` | Implemented and verified |
| ARMB-01 | Arm B improved conventional: corrected rules, consolidated evidence, filters, better search, validation, automated calculations, improved UI; doubles as manual fallback | B.8 | 1 | 7 | core | — | — | Planned (M7) |
| ARMC-01 | Arm C: B plus interpretation, targeted retrieval, summarization, cited explanation, missing-info detection, drafting, human review | B.8 | 1 | 8 | core | — | — | Planned (M8) |
| ARMS-01 | Identical safeguards across arms; no ground truth to AI; every arm difference documented; UI gains not credited to AI | B.8 | 1 | 5–8 | bench | M5: one shared `WritePath` and case service for every arm (ADR-0044); the app never reads labels or benchmark files; arms B and C in M7–M8 | `tests/test_arm_a_boundaries.py::test_nothing_in_the_app_imports_the_benchmark_tooling` | Planned (M7) |
| AI-01 | `docs/ai-engineering-matrix.md`: problem, location, exercise, tests, tradeoffs per discipline | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-02 | Prompt engineering: versioned templates, typed outputs, trusted/untrusted separation, no secrets, prompt regression suite on held-out | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-03 | Context builder with budget, provenance, freshness, minimization, compaction rules; tests for irrelevant/missing/conflicting/long context | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-04 | Tool engineering: narrow, validated schemas, authz, timeouts, structured errors, bounded size, correlation IDs; tests for malformed/unavailable/denied/oversized | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-05 | Read-only tools: get_member, get_stay, get_points_ledger, search_policy, evaluate_eligibility | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-06 | Resolution drafting is a validated application service that persists the recommendation | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-07 | No SQL, shell, filesystem, browser, network, payment or adjustment authority for the agent | B.9 | 1 | 8 | sec | — | — | Planned (M8) |
| AI-08 | Agent loop as an explicit state machine (8 steps) | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-09 | Ten stop conditions, each with a test; configurable limits with documented rationale | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-10 | Workflow: intake → evidence → policy → eligibility → validation → 4 branches → execution → reconciliation; persisted transitions; bounded parallel reads; tests for invalid transitions, duplicates, cancellation, restart | B.9 | 1 | 6, 8 | core | — | — | Planned (M6) |
| AI-11 | Runtime harness components (run/case IDs, caller, registry, provider, context, schemas, budgets, retry, cancellation, checkpoints, trace, final validation) | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-12 | Run metadata stored (prompt version, model, policy version, tool statuses, usage, timing, stop reason); secrets kept out of traces; exactly-once caveat documented | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-13 | Memory and state separation; DB is the source of truth; tests for stale state, concurrency, case separation, deletion | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-14 | Final-output validation and one bounded repair, then escalate or deterministic fallback | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-15 | Never request or store hidden chain-of-thought | B.9 | 1 | 8 | sec | — | — | Planned (M8) |
| AI-16 | Recommendation contents: summary, facts, deterministic eligibility, citations, missing info, action, escalation reason | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| AI-17 | No uncalibrated confidence percentages | B.9 | 1 | 8 | core | — | — | Planned (M8) |
| WP-01 | Case states and server-side transitions, diagram, reopening | B.10 | 1 | 6 | core | — | — | Planned (M6) |
| WP-02 | Roles: agent, supervisor, administrator, auditor | B.10 | 1 | 6 | core | M5: agent and supervisor (`app/domain/roles.py`); administrator and auditor in M6/M9 | `tests/test_case_workflow.py::test_an_agent_can_neither_approve_nor_execute` | Planned (M6) |
| WP-03 | Approval binding hash over member, stay, points, policy version, evidence snapshot, approver, expiry | B.10, App. B | 1 | 6 | core | — | — | Planned (M6) |
| WP-04 | Creator cannot approve their own adjustment | B.10 | 1 | 6 | core | `app/domain/roles.approval_refusal`, enforced in `SharedWritePath.decide` and `execute`; the UI also hides the buttons | `tests/test_case_workflow.py::test_the_requester_cannot_approve_their_own_adjustment` | Implemented and verified |
| WP-05 | Model, browser or user fields never grant approval or a role | B.10 | 1 | 6 | sec | M5: role from the server session only; form fields ignored; model part in M8 | `tests/test_console_web.py::test_a_role_in_the_form_is_ignored` | Planned (M6) |
| WP-06 | Any change to amount, member, stay, policy or evidence invalidates approval | B.10 | 1 | 6 | core | — | — | Planned (M6) |
| WP-07 | Revalidate eligibility and ledger immediately before execution | B.10 | 1 | 6 | core | M5: cross-case duplicate check on adjustments only (ADR-0044); eligibility revalidation decided in M6 | `tests/test_case_workflow.py::test_d10_a_second_case_for_the_same_stay_is_refused_at_execution` | Planned (M6) |
| WP-08 | Concurrency control plus upstream idempotency (key derived from approval ID) | B.10, App. B | 1 | 6 | core | M5: idempotency key derived from the approval's stored ID (`write_path.idempotency_key`); concurrency control in M6 | `tests/test_case_workflow.py::test_reconciled_as_not_applied_returns_to_approved_and_reuses_the_key` | Planned (M6) |
| WP-09 | Timeout → `Execution unknown` → status reconciliation before any retry | B.10 | 1 | 6 | core | M5: uncertain outcome → `Execution unknown` → lookup by key before anything else; reconciliation job and real-Postgres tests in M6 | `tests/test_case_workflow.py::test_commit_then_lost_is_reconciled_by_key_without_a_second_credit` | Planned (M6) |
| WP-10 | Emergency switch disables adjustments, keeps investigation; tested under concurrency | B.10 | 1 | 6 | core | — | — | Planned (M6) |
| WP-11 | Audit history, append-only DB role, integrity guarantees stated honestly | B.10 | 1 | 6 | sec | — | — | Planned (M6) |
| DB-01 | Alembic migrations for users/roles, cases, evidence, policies/chunks, recommendations, approvals, execution attempts, idempotency, jobs, audit, eval runs, feedback | B.11 | 1 | 4, 6 | core | Mock API schema migrated (`mock_customer_api/migrations/`); app revision 0002: users, sessions, cases, requests, evidence, notes, adjustment requests, approvals, execution attempts, case events (ADR-0046); policies, recommendations, idempotency, jobs, eval runs, feedback in M6+ | `tests/test_arm_a_boundaries.py::test_migration_0002_matches_the_table_definitions` | Planned (M6) |
| API-01 | APIs: cases CRUD/list, view, start investigation, supply info, recommendations/citations, approve/reject, execute, status, audit, metrics, feedback | B.11 | 1 | 7 | core | — | — | Planned (M7) |
| API-02 | Pagination, validation, consistent errors, OpenAPI docs, duplicate-investigation prevention | B.11 | 1 | 7 | core | — | — | Planned (M7) |
| JOB-01 | Postgres job queue: leases, heartbeats, abandoned recovery, bounded retries with backoff, dead jobs, duplicate prevention, graceful shutdown, correlation IDs | B.12, App. B | 1 | 6 | core | — | — | Planned (M6) |
| JOB-02 | No in-memory background tasks for critical work; transaction boundaries and failure semantics documented | B.12 | 1 | 6 | core | — | — | Planned (M6) |
| JOB-03 | Retries and restarts never duplicate business effects; caching only with defined invalidation | B.12 | 1 | 6 | core | — | — | Planned (M6) |
| UI-01 | Console: login, queue, create, detail, evidence panels, progress, cited recommendation, missing-info, approve/reject with reasons, execution/reconciliation status, audit timeline, metrics, feedback, mode indicator | B.13 | 1 | 5, 7 | core | M5: login, queue with filters, case creation, case detail, member/stay/ledger/policy screens, approve/reject with reasons, execution and reconciliation status, audit timeline, mode banner (`app/web/`); progress, cited recommendations, missing-info workflow, metrics and feedback in M7–M8 | `tests/test_console_web.py::test_every_page_has_the_banner_and_security_headers` | Planned (M7) |
| UI-02 | Evaluation-only A/B/C comparison dashboard, no cherry-picking, no ground truth to operational users | B.13 | 1 | 10 | bench | — | — | Planned (M10) |
| UI-03 | Responsive, keyboard, labels, AA contrast, loading/empty/error/retry states, time zones, every control works | B.13 | 1 | 7 | core | — | — | Planned (M7) |

## Part C: security, identity, data governance

Items needed for the core (auth, authorization, approval integrity, injection tests) are Tier 1 (Milestone 9); the
rest are Tier 2.

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| SEC-01 | Current NIST AI RMF + GenAI profile, SSDF, ASVS, OWASP GenAI/agentic, protocol security specs consulted; versions and dates recorded; no certification claims | C.1 | 2 | 9 | sec | — | — | Planned (M9) |
| SEC-02 | `security/` files: inventory, data flow, threat model (canonical), risk register, control matrix, test plan/results, evidence, residual risks, incident runbooks, production readiness; `docs/production-readiness.md` | C.1 | 2 | 2, 9 | sec | `security/threat-model.md` (draft); other `security/` files in M9 | — | Planned (M9) |
| SEC-03 | Threat model: trust boundaries, actors, threats, prioritization; updated when integrations change | C.2 | 1 | 2, 9 | sec | `security/threat-model.md` draft v0.1 (16 threats); completed in M9 | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented but unverified |
| SEC-04 | Tool and access register, data-flow map, data classification, customer access checklist, on/offboarding checklists (categories A–D) | C.3 | 2 | 9 | sec | — | — | Planned (M9) |
| SEC-05 | Data minimization before model calls; redaction of secrets and unnecessary personal fields | C.3, E3 | 1 | 8, 9 | sec | — | — | Planned (M8) |
| SEC-06 | Retention and deletion jobs incl. derived indexes and caches; backup-deletion limits documented | C.3 | 2 | 9 | sec | — | — | Planned (M9) |
| SEC-07 | Local demo auth: argon2/bcrypt, server sessions, CSRF, rate limits, expiry/revocation, deactivation, recovery | C.4 | 1 | 9 | sec | M5: argon2id, server-side sessions, CSRF on every POST, expiry and revocation, deactivated accounts refused (ADR-0045); rate limits and recovery in M9 | `tests/test_console_web.py::test_logout_revokes_the_session_on_the_server` | Planned (M9) |
| SEC-08 | OIDC profile (Keycloak): signature, issuer, audience, expiry, key rotation; maintained libraries only | C.4 | 1 | 9 | sec | — | — | Planned (M9) |
| SEC-09 | Supabase Auth profile with the same checks | C.4 | 3 | 15 | sec | — | — | Planned (M15) |
| SEC-10 | MFA for privileged users where the IdP supports it; no claim if only a guide exists | C.4 | 2 | 9 | sec | — | — | Planned (M9) |
| SEC-11 | Workload identity separated from human identity; short-lived workload credentials preferred | C.4 | 2 | 12 | sec | — | — | Planned (M12) |
| SEC-12 | Backend authorization on every operation; tests for object-level, role escalation, cross-user, cross-customer | C.5 | 1 | 9 | sec | — | — | Planned (M9) |
| SEC-13 | Supabase: privileged keys server-side, actual access path tested, RLS not assumed for elevated connections | C.5 | 3 | 15 | sec | — | — | Planned (M15) |
| SEC-14 | Secrets: env/secret manager, never in history/bundles/logs/screenshots/fixtures/prompts/errors; scanning; rotation | C.6 | 1 | 1, 9, 12 | sec | `.gitignore`, `app/preflight.py`, `tests/test_secrets_hygiene.py` | partial (M1 scope) | Implemented but unverified |
| SEC-15 | TLS and encryption at rest; local vs managed settings distinguished | C.6 | 2 | 12 | sec | — | — | Planned (M12) |
| SEC-16 | Outbound allowlist, private DB/admin, SSRF protection (internal nets, metadata, redirects, schemes, size, slow responses); no model-selected URLs | C.6 | 2 | 9, 11 | sec | — | — | Planned (M9) |
| SEC-17 | Untrusted inputs; ingestion controls; output schema validation, encoding, XSS, CSP, secure cookies, CSRF, restricted CORS; no stack traces to users | C.7 | 1 | 7, 9 | sec | M5: Jinja autoescape, strict CSP (`script-src 'self'`), HttpOnly SameSite=Strict cookies, CSRF, no stack traces in error pages | `tests/test_console_web.py::test_member_text_is_escaped_not_executed` | Planned (M7) |
| SEC-18 | Public demo mode: synthetic only, restricted admin, no shared admin, controlled reset, request and spend limits | C.8 | 2 | 12 | sec | — | — | Planned (M12) |
| SEC-19 | Red-team suite asserting on business effects (injection, secrets, cross-customer, adjustment execution, tool misuse, poisoned docs, SSRF, approval tampering, replay, expired creds, worker interruption, budget exhaustion, cross-user streams); repeated model tests; residual risks | C.9 | 1 | 9 | sec | — | — | Planned (M9) |
| SEC-20 | Security event logging with minimal content, restricted access, retention, alerts with owners and runbooks | C.10 | 2 | 12 | sec | — | — | Planned (M12) |
| SEC-21 | Incident exercises: leaked model key, compromised integration credential, unauthorized access, malicious policy, unexpected agent action, compromised dependency, excessive spend | C.10 | 2 | 13 | sec | — | — | Planned (M13) |
| SEC-22 | Release gates for local/demo, staging, production with the listed criteria and honest wording | C.10 | 2 | 12 | sec | — | — | Planned (M12) |
| SEC-23 | Maintenance schedule with owner and evidence per activity; changes trigger tests; no auto-deploy of prompt or feedback changes | C.10 | 2 | 12, 18 | sec | — | — | Planned (M12) |

## Part D: testing (Tier 1)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| TEST-01 | Unit tests: eligibility and date boundaries, policy version selection, state transitions, approval binding, redaction | D | 1 | 6 | core | — | — | Planned (M6) |
| TEST-02 | Real-Postgres integration tests: idempotency atomicity, concurrent approve/execute, duplicates, timeout after commit, reconciliation, worker restart, approval invalidation, object-level authz | D | 1 | 6, 9 | core | M4: idempotency atomicity, concurrent duplicates, conflicts, commit-then-lost on real Postgres; approval, execution and worker tests in M6/M9 | `tests/test_mock_api_postgres.py::test_twenty_concurrent_requests_with_one_key_apply_once` | Planned (M6) |
| TEST-03 | AI harness tests: every stop condition, malformed args, unauthorized tools, injection, citation provenance, missing/conflicting info | D | 1 | 8 | core | — | — | Planned (M8) |
| TEST-04 | Failure-injection tests: upstream failures, timeouts, rate limits, provider outage | D | 1 | 6, 8 | core | M4: upstream failures, timeouts, rate limits (contract + live checks); provider outage in M8 | `tests/test_mock_api.py::test_read_timeout_is_retried_then_raised`, `tests/test_mock_api.py::test_write_timeout_is_never_retried` | Planned (M8) |
| TEST-05 | Playwright: full happy path with a different supervisor, self-approval blocked, escalation, missing info, rejection, reopening, reconciliation | D | 1 | 7 | core | M5: happy path with a different supervisor and self-approval blocked (offline and against the stack); escalation, missing info, rejection, reopening, reconciliation in the browser in M7 | `tests/browser/test_legacy_e2e.py::test_a_supervisor_cannot_approve_an_adjustment_they_requested` | Planned (M7) |
| TEST-06 | Deterministic tests separate from model evals; one offline command (`make test` + PowerShell equivalent) | D | 1 | 1 | core | `Makefile`, `scripts/test.ps1` | verification log 2026-10-28 (`scripts/test.ps1` run) | Implemented and verified |

## Part E: evaluation, legacy measurement, benchmarking (Tier 1)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| EVAL-01 | ≥60 labelled cases; dev/validation/held-out/stress splits; grouped to prevent leakage; temporal/policy-family splits; versions and checksums | E.1 | 1 | 3 | bench | 280 cases: dev 100, validation 30, held-out 80, stress 30, fairness 40; member-grouped; temporal held-out; checksums in the manifest | `tests/test_generator.py::test_split_sizes_and_heldout_composition`, `tests/test_generator.py::test_no_member_stay_or_text_crosses_splits` | Implemented and verified |
| EVAL-02 | Labels from scenario facts: policy, eligibility, points, existing credit, evidence, next action, clarification, escalation; "insufficient evidence" is valid | E.1 | 1 | 3 | bench | `evaluations/labeler.py`; `CaseLabel` fields incl. expected final ledger | `tests/test_generator.py::test_labels_validate_and_inputs_match` | Implemented and verified |
| EVAL-03 | Evaluated AI never the sole labeler; expected answers inaccessible to the app | E.1 | 1 | 3 | bench | Labels by construction + independent labeler (ADR-0029); labels only under `benchmarks/datasets/v1/labels/` | `tests/test_generator.py::test_labeler_is_independent_of_generator_and_app`, `tests/test_generator.py::test_app_cannot_read_labels_or_generator_metadata` | Implemented and verified |
| EVAL-04 | Label-review file or interface with reviewer status; disclose if no independent human reviewed. Owner agreed 2026-10-28 to review a stratified sample of about 30 labels | E.1 | 1 | 3 | bench | `evaluations/label-review/review-sheet.csv` (30 cases, status Sheet ready); owner review pending | `tests/test_generator.py::test_review_sheet_has_the_stratified_sample` | Implemented and verified |
| EVAL-05 | Never tune on held-out; replace held-out if it becomes dev data | E.1 | 1 | 3–10 | bench | Held-out written with its own paraphrase families and dates; tuning discipline applies through M10 | `tests/test_generator.py::test_paraphrase_families_and_temporal_split` | Implemented but unverified |
| LEG-01 | Baseline measurement plan, root-cause analysis, experiment plan, error analysis docs | E.2 | 1 | 2, 10 | bench | `docs/baseline-measurement-plan.md`, `docs/experiment-plan.md` done; root-cause analysis and error analysis in M10 | `tests/test_discovery_docs.py::test_document_covers_required_topics` (two of four) | Planned (M10) |
| LEG-02 | Legacy arm instrumented (outcome, false approve/deny, escalation, missing info, times, steps, reopen, duplicates, overrides, errors); software metrics apart from human usability | E.2 | 1 | 5 | bench | `app/services/instrumentation.py`: one `case_events` row per step (actor, scripted/human, wall time, simulated time, searches, evidence, decisions, overrides, escalations, info requests, executions, system errors); outcome correctness scored in M10 outside the app | `tests/test_scripted_agent.py::test_k01_runs_end_to_end_and_is_labelled_scripted` | Implemented and verified |
| LEG-03 | Case-by-case RCA in the 11 categories with reproduction, expected vs actual, evidence, frequency, consequence, intervention; non-AI fixes named | E.2 | 1 | 10 | bench | — | — | Planned (M10) |
| BENCH-01 | `benchmarks/` dirs; `benchmark-thresholds.yaml` committed before any run | E.3, E.6 | 1 | 10 | bench | — | — | Planned (M10) |
| BENCH-02 | Config fields (dataset, arm, model, prompt, retrieval, tools, limits, timeouts, concurrency, repetitions, cost ceiling, environment, cache) | E.3 | 1 | 10 | bench | — | — | Planned (M10) |
| BENCH-03 | One command runs a benchmark (smoke/full); one compares runs; `evaluations.run` / `evaluations.compare` | E.3, App. B | 1 | 10 | bench | — | — | Planned (M10) |
| BENCH-04 | Layers benchmarked separately: component, agent, application, business | E.3 | 1 | 10 | bench | — | — | Planned (M10) |
| BENCH-05 | Metrics incl. false approvals and false denials separately, coverage with accuracy, unsupported claims, citations, duplicates, unauthorized actions, latency, cost | E.3 | 1 | 10 | bench | — | — | Planned (M10) |
| BENCH-06 | Counts, denominators, per-scenario breakdowns; weighted-loss weights documented | E.3 | 1 | 10 | bench | — | — | Planned (M10) |
| BENCH-07 | Fair paired runs, declared cache/dependencies, repeats, uncertainty, no unsupported significance claims | E.4 | 1 | 10 | bench | — | — | Planned (M10) |
| BENCH-08 | One-factor ablations (prompt, context, retrieval, model, loop limits, validation, revision, rules-only vs RAG vs agent) | E.4 | 1 | 10 | bench | — | — | Planned (M10) |
| BENCH-09 | LLM judge only if calibrated against human labels, disagreement documented, never sole measure | E.4 | 1 | 10 | bench | — | — | Planned (M10) |
| BENCH-10 | Mock vs live separated everywhere; live only with credentials and a cap, else NOT RUN; versions stored per run | E.5 | 1 | 8, 10 | bench | — | — | Planned (M8) |
| BENCH-11 | Thresholds defined before evaluation; business thresholds provisional; authz/approval/duplicate tests 100% | E.6 | 1 | 10 | bench | — | — | Planned (M10) |
| BENCH-12 | Improvement loop with failure classes; failing cases join regression; no automatic prompt changes | E.6 | 1 | 10 | bench | — | — | Planned (M10) |
| BENCH-13 | Regression eval before release on any change; known-good config for rollback | E.6 | 1 | 10, 12 | bench | — | — | Planned (M10) |
| BIZ-01 | Business metrics with pp and relative change, incremental AI cost, break-even; observed/estimated/assumed/unmeasured kept apart | E.7 | 1 | 10 | bench | — | — | Planned (M10) |
| BIZ-02 | Human timing protocol (`docs/timing-protocol.md`), counterbalanced, measured values only | E.7 | 1 | 10, 18 | bench | — | — | Planned (M10) |
| BIZ-03 | Satisfaction survey with real participants only, otherwise "unmeasured" | E.7 | 1 | 18 | bench | — | — | Planned (M18) |
| BIZ-04 | `docs/business-value-report.md` conclusion chosen by evidence | E.7 | 1 | 10 | bench | — | — | Planned (M10) |
| E2E-01 | End-to-end scenarios: changed policy, existing credit, missing evidence, duplicate submission, timeout after commit, incorrect AI recommendation, rejection, reopening | E.8 | 1 | 10 | bench | — | — | Planned (M10) |
| E2E-02 | The 10 required demonstrations recorded in `docs/demonstrations.md` with trace, expected, actual, test evidence | E.8 | 1 | 6–10 | core | — | — | Planned (M6) |

## Part F: performance, observability, deployment, operations (Tier 2)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| OPS-01 | Declared load profile and bounded load test report | F.1 | 2 | 12 | core | — | — | Planned (M12) |
| OPS-02 | `/healthz`, `/readyz`, structured logs with correlation IDs, OpenTelemetry with context propagation, sensitive-data filtering | F.1 | 2 | 6, 12 | core | M4: `/healthz`, `/readyz` on both services, correlation IDs on mock API responses; structured logs and OpenTelemetry in M12 | `tests/test_app_shell.py::test_readyz_needs_migrations_and_customer_systems`, `tests/test_mock_api.py::test_readyz_reports_seeded_and_empty` | Planned (M12) |
| OPS-03 | Metrics incl. per-case model usage and cost, provider spend tracking | F.1 | 2 | 12 | core | — | — | Planned (M12) |
| OPS-04 | Dashboards and actionable alerts linked to runbooks | F.1 | 2 | 12 | core | — | — | Planned (M12) |
| OPS-05 | Reliability: budgets, bounded concurrency, circuit breakers where justified, transient-only backoff, backpressure, provider-outage manual fallback, feature flags | F.1 | 2 | 8, 12 | core | — | — | Planned (M8) |
| OPS-06 | Proposed SLOs kept apart from measured results; no availability claims from local tests | F.1 | 2 | 12 | core | — | — | Planned (M12) |
| DEL-01 | Non-root containers with limits; Compose profiles demo/test/enterprise-identity/labs; quickstart works as written | F.2 | 1 | 4, 12 | core | M4: non-root (UID 10001), read-only containers, resource limits, quickstart (`up`, `app.seed`) verified by the compose check; Compose profiles (demo/test/enterprise-identity/labs) in M12 | compose check 2026-10-29 | Planned (M12) |
| DEL-02 | CI: lint/format, types, Postgres tests, migration on empty DB, static analysis, dependency/secret/container/IaC scans, build, SBOM, Playwright, provenance | F.2 | 2 | 12 | sec | First workflow: lint, format, types, offline tests with coverage gate, Playwright, real-Postgres mock tests, pip-audit, gitleaks (ADR-0053); the rest in M12 | `.github/workflows/ci.yml` | Planned (M12) |
| DEL-03 | CI rules: no paid key, least-privilege tokens, no secrets to untrusted PRs, scanner failures reported, never disabled | F.2 | 2 | 12 | sec | — | — | Planned (M12) |
| DEL-04 | Protected manual deploy workflow with environment approval and OIDC; not executed without authorization | F.2 | 2 | 12 | core | — | — | Planned (M12) |
| DEL-05 | Separate local/staging/production config; production checks (no debug, no default credentials) | F.2 | 2 | 12 | sec | — | — | Planned (M12) |
| DEL-06 | Terraform for one AWS path (ECS Fargate, RDS private, ALB/ACM, Secrets Manager, least-privilege roles, CloudWatch, backups, tags, teardown); fmt/validate/scan only | F.2, App. B | 2 | 12 | core | — | — | Planned (M12) |
| DEL-07 | Shared responsibility for Supabase, Vercel, AWS, model providers | F.2 | 2 | 12 | other | — | — | Planned (M12) |
| DEL-08 | Rollback: app, expand/contract migrations, compatibility with in-progress cases | F.2 | 2 | 12 | core | — | — | Planned (M12) |
| DEL-09 | Backup and restore instructions | F.2 | 2 | 12 | core | — | — | Planned (M12) |
| ROLL-01 | Rollout stages with stop and rollback criteria | F.3 | 2 | 13 | other | — | — | Planned (M13) |
| ROLL-02 | Drills with actual results in `docs/drills.md`, incl. measured restore | F.3 | 2 | 13 | core | — | — | Planned (M13) |
| ROLL-03 | Restore never replays actions or reinstates revoked access; proposed RTO/RPO apart from measured | F.3 | 2 | 13 | core | — | — | Planned (M13) |
| ROLL-04 | Runbooks, incident guide, example incident report from an executed drill, ownership matrix | F.3 | 2 | 13 | other | — | — | Planned (M13) |

## Part G: protocols

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| PROTO-01 | Protocol research docs from primary sources (catalog, selection, compatibility, adoption evidence, labs, test results); "ACP" always spelled out | G.1 | 2 | 11 | proto | — | — | Planned (M11) |
| PROTO-02 | Structure and isolation: per-protocol dirs, feature flags, independent start; core works with all labs off; adapters preserve identity, IDs, budgets, trace, audit, idempotency | G.2 | 2 | 11 | proto | — | — | Planned (M11) |
| PROTO-03 | MCP server (official SDK, streamable HTTP), read-only loyalty tools, auth per pinned spec, no token passthrough, tests for denied/expired/audience/scope/cross-record, independent client or Inspector | G.3 | 2 | 11 | proto | — | — | Planned (M11) |
| PROTO-04 | A2A: coordinator + reservation specialist services, Agent Card, task lifecycle, peer auth, timeouts, cancellation, REST comparison | G.4 | 2 | 11 | proto | — | — | Planned (M11) |
| PROTO-05 | AG-UI: pinned events, reconnect, dedup, run-access authz, no chain-of-thought or secrets | G.5 | 2 | 11 | proto | — | — | Planned (M11) |
| PROTO-06 | A2UI lab: allowlisted catalog, backend validation, static fallback | G.6 | 3 | 16 | proto | — | — | Planned (M16) |
| PROTO-07 | MCP Apps lab: read-only case viewer; host verification or "host integration unverified" | G.7 | 3 | 16 | proto | — | — | Planned (M16) |
| PROTO-08 | Agent Client Protocol dev lab, or recorded prerequisite | G.8 | 3 | 16 | proto | — | — | Planned (M16) |
| PROTO-09 | IBM/BeeAI Agent Communication Protocol historical comparison | G.9 | 3 | 16 | proto | — | — | Planned (M16) |
| PROTO-10 | ANP experimental lab with failed-verification tests | G.9 | 3 | 16 | proto | — | — | Planned (M16) |
| PROTO-11 | Commerce: UCP and Agentic Commerce Protocol adapters over one fictional merchant | G.10 | 3 | 16 | proto | — | — | Planned (M16) |
| PROTO-12 | AP2 sandbox: mandate structures and signatures, replay/alteration tests | G.11 | 3 | 16 | proto | — | — | Planned (M16) |
| PROTO-13 | x402 and MPP sandboxes: mocks/testnets only, no funding | G.12 | 3 | 16 | proto | — | — | Planned (M16) |
| PROTO-14 | Per-protocol verification tests, conformance tools, Protocol Lab page | G.13 | 2 | 11, 16 | proto | — | — | Planned (M11) |

## Part H and Appendix G: actual-tool learning track (Tier 3, Milestone 15 unless noted)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| TOOL-01 | Tool docs: access matrix, stack coverage, labs, evidence, experiment results, FDE tool map; per-tool fields from H.1 | H.1 | 3 | 1, 15 | tools | `docs/tool-access-matrix.md` (first version) | — | Implemented but unverified |
| TOOL-CC | Claude Code: primary implementer; work recorded; connect this project's MCP server and analyse the discovery history | H.2, App. G | 3 | 1–20 | tools | this repo's commits | — | Implemented but unverified |
| TOOL-CODEX | Codex: independent review or second implementation of reconciliation/idempotency; compare defects, time, cost | H.2, App. G | 3 | 6, 13 | tools | — | — | Planned (M6) |
| TOOL-CURSOR-01 | Cursor: current rules mechanism verified; owner's bounded change with two models; tests; diff review | H.2, App. G | 3 | 15 | tools | `.cursor/rules/project-standard.mdc` | — | Configured but untested |
| TOOL-CODERABBIT | CodeRabbit: repo-level install (owner's OK), PR findings tracked by category | H.2, App. G | 3 | 15 | tools | — | — | Planned (M15) |
| TOOL-SUPABASE | Supabase Postgres + Auth profile, local CLI, actual access path; pgvector only in the retrieval experiment | H.2, App. G | 3 | 15 | tools | — | — | Planned (M15) |
| TOOL-BOLT | bolt.new: brief, timed generation, code review, React frontend integration; never fabricated | H.2, App. G | 3 | 15 | tools | — | — | Planned (M15) |
| TOOL-VERCEL | Vercel: compatibility check; deploy only when authorized and verified | H.2, App. G | 3 | 15 | tools | — | — | Planned (M15) |
| TOOL-MONDAY | Monday.com: import file; with access, one automation and one reminder | H.2, App. G | 3 | 15 | tools | — | — | Planned (M15) |
| TOOL-MIRO | Miro: workshop package and importable assets; board only with access; simulated walkthrough | H.2, App. G | 3 | 2, 15 | tools | — | — | Planned (M15) |
| TOOL-EGOLITE | Egolite: verify product/OS first; Blocked if unverifiable or no macOS | H.2, App. G | 3 | 15 | tools | — | — | Planned (M15) |
| TOOL-MIRA | Mira: verify exact product; if unavailable ask the owner about a generic Telegram exercise | H.2, App. G | 3 | 15 | tools | — | — | Planned (M15) |
| TOOL-OPENMODELS | Kimi / GLM / Qwen: verify releases and licences; one provider behind the interface; same held-out eval; routing policy | H.2, App. G | 3 | 15 | tools | — | — | Planned (M15) |
| TOOL-INVOCO | Invoco: verify product/OS; dictation exercise; never a runtime dependency | H.2, App. G | 3 | 15 | tools | — | — | Planned (M15) |
| TOOL-MAP | `docs/fde-tool-map.md` per capability, replacement criteria, minimal vs full stack keep/drop/undecided | H.3, App. G | 3 | 15 | tools | — | — | Planned (M15) |

## Parts I–N (Tier 4 unless noted)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| UAT-01 | UAT scripts, training and admin guides, pilot feedback form, acceptance checklist, open issues, support handover, ownership matrix, release checklist, scope-change procedure, estimates | I | 4 | 18 | other | — | — | Planned (M18) |
| UAT-02 | Manual vs assisted measurement on the same cases; simulated users labelled | I | 4 | 18 | bench | — | — | Planned (M18) |
| UAT-03 | Real-customer validation plan (8 steps) | I | 4 | 18 | other | — | — | Planned (M18) |
| KIT-01 | `starter_kit/` with generic foundation only, extracted after the app works | J | 4 | 17 | other | — | — | Planned (M17) |
| KIT-02 | Scaffold command; generated project starts and passes a smoke test (recorded) | J | 4 | 17 | other | — | — | Planned (M17) |
| KIT-03 | Adaptation proof on a second small domain | J | 4 | 17 | other | — | — | Planned (M17) |
| KIT-04 | `docs/new-customer-playbook.md` | J | 4 | 17 | other | — | — | Planned (M17) |
| KIT-05 | `docs/new-requirement-playbook.md` (12 steps + templates) | J | 4 | 17 | other | — | — | Planned (M17) |
| KIT-06 | Redesign guidance and the explicit "no minutes" statements | J | 4 | 17 | other | — | — | Planned (M17) |
| PERS-01 | Milestone teaching (what, why, verify, failure modes, one exercise) at every milestone | K.1 | 4 | all | personal | session reports; `docs/owner-exercises.md` | M1 and M2 exercises answered by the owner (`docs/owner-exercises.md`) | Implemented but unverified |
| PERS-02 | Owner exercises (product/ops, explanation, security, protocols) completed and recorded | K.2 | 4 | 18 | personal | — | — | Planned (M18) |
| PERS-03 | Final practical assessment (5 tasks) | K.3 | 4 | 18 | personal | — | — | Planned (M18) |
| PORT-01 | `portfolio/` files (summary, case study, demo script, walkthrough, talking points, eval report, security summary, tool evidence, cost/time, starter kit, diagrams, metadata, real screenshots) | L.1 | 4 | 19 | other | — | — | Planned (M19) |
| PORT-02 | Case study content per L.2 incl. cases where AI didn't help | L.2 | 4 | 19 | other | — | — | Planned (M19) |
| PORT-03 | Five-minute demo and fifteen-minute technical walkthrough | L.3 | 4 | 19 | other | — | — | Planned (M19) |
| PORT-04 | Honesty labels; website page prepared, not published without OK | L.4 | 4 | 19 | other | — | — | Planned (M19) |
| REPO-01 | Directory layout per M.1 | M.1 | 1 | 1–20 | other | top-level folders created as milestones reach them | — | Planned (M4) |
| REPO-02 | README, lockfile, `.env.example`, Windows + macOS/Linux setup, command set, troubleshooting, hardware guidance, MIT licence, third-party notices, limitations list | M.2 | 1 | 1, 20 | other | `README.md`, `uv.lock`, `LICENSE`, `.env.example` (first versions) | — | Implemented but unverified |
| REPO-03 | Clean install verified from a fresh clone | M.3 | 4 | 20 | other | — | — | Planned (M20) |
| REPO-04 | Independent usability test, or recorded as pending | M.3 | 4 | 20 | other | — | — | Planned (M20) |
| DEF-01 | Make targets (`up`, `migrate`, `seed`, `reset-demo`, `test`, `eval`, `benchmark`, `preflight`, `down`, `clean`) each with a `scripts/*.ps1` equivalent | App. B | 1 | 1–6 | core | `Makefile` + `scripts/*.ps1`: test, preflight, data, up, down, migrate, seed, reset-demo, clean, logs, compose-check (eval, benchmark to come) | verification log 2026-10-29 (PowerShell equivalents run; `make` not installed here) | Implemented but unverified |
| DEF-02 | Tooling: uv + lockfile, ruff, mypy, gitleaks, pip-audit, syft, Trivy, Terraform | App. B | 1 | 1, 12 | other | `pyproject.toml`, `uv.lock` (uv, ruff, mypy, pytest so far) | verification log 2026-10-28 | Implemented but unverified |
| FINAL-01 | Final acceptance report (N.2) with every item classified | N.2 | 4 | 20 | other | — | — | Planned (M20) |

## Appendix E: enterprise AI practices (Tier 2; milestone per the spec's placement)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| ENT-01 | AI system card | E1 | 2 | 8 | other | — | — | Planned (M8) |
| ENT-02 | Use-case register entry and impact assessment, marked draft | E1 | 2 | 8 | other | — | — | Planned (M8) |
| ENT-03 | Regulatory applicability assessment (documentation only, not legal advice) | E1 | 2 | 9 | other | — | — | Planned (M9) |
| ENT-04 | Fairness slices (tier, region, channel, language, style) and counterfactual pairs | E1 | 2 | 10 | bench | Slice tags on every case and the separate fairness set (M3); reporting in M10 | — | Planned (M10) |
| ENT-05 | UI labels AI-generated text and separates deterministic from model-written content | E1 | 2 | 8 | core | — | — | Planned (M8) |
| ENT-06 | Anti-rubber-stamp UI: evidence and deterministic result before AI summary; review required; reasons for reject/override | E2 | 2 | 8 | core | — | — | Planned (M8) |
| ENT-07 | Automation-bias measurement with seeded wrong recommendations | E2 | 2 | 10, 18 | bench | — | — | Planned (M10) |
| ENT-08 | Reviewer workload, time per review, override rate per reviewer and scenario | E2 | 2 | 10 | bench | — | — | Planned (M10) |
| ENT-09 | Synthetic data-subject access export and erase workflow; retained records justified; backup limits | E3 | 2 | 9 | sec | — | — | Planned (M9) |
| ENT-10 | Legal hold flag with audit | E3 | 2 | 9 | sec | — | — | Planned (M9) |
| ENT-11 | Data residency and transfer map; configurable provider region | E3 | 2 | 12 | sec | — | — | Planned (M12) |
| ENT-12 | PII detection and redaction in free text before model calls and in logs; limits documented | E3 | 2 | 8, 9 | sec | — | — | Planned (M8) |
| ENT-13 | Enterprise endpoint adapter (Claude via Amazon Bedrock); configure only; Blocked without access | E4 | 2 | 12 | core | — | — | Planned (M12) |
| ENT-14 | Provider contract checklist | E4 | 2 | 12 | other | — | — | Planned (M12) |
| ENT-15 | Model lifecycle: pinned IDs, deprecation tracking, upgrade procedure; unknown model fails safe to manual | E4 | 2 | 8, 12 | core | — | — | Planned (M8) |
| ENT-16 | AI gateway pattern documented | E4 | 2 | 12 | other | — | — | Planned (M12) |
| ENT-17 | Cost controls: prompt caching measured, cheaper model only with no quality loss, cost attribution | E4 | 2 | 10, 12 | bench | — | — | Planned (M10) |
| ENT-18 | Online quality sampling for human QA | E5 | 2 | 12 | core | — | — | Planned (M12) |
| ENT-19 | Drift signals with configurable alert thresholds | E5 | 2 | 12 | core | — | — | Planned (M12) |
| ENT-20 | AI incident register | E5 | 2 | 13 | other | — | — | Planned (M13) |
| ENT-21 | Feedback-to-dataset pipeline after labeling review only | E5 | 2 | 12 | bench | — | — | Planned (M12) |
| ENT-22 | Canary/shadow for prompt and model versions | E5 | 2 | 12 | bench | — | — | Planned (M12) |
| ENT-23 | On-behalf-of authorization: agent cannot read what the user cannot (tested) | E6 | 2 | 8, 9 | sec | — | — | Planned (M9) |
| ENT-24 | SCIM provisioning documented; deprovisioning demonstrated if the local IdP supports it | E6 | 2 | 9 | sec | — | — | Planned (M9) |
| ENT-25 | Group-to-role mapping from IdP claims, per customer | E6 | 2 | 9 | sec | — | — | Planned (M9) |
| ENT-26 | Break-glass procedure (time limits, reason, alert, audit) | E6 | 2 | 13 | sec | — | — | Planned (M13) |
| ENT-27 | Periodic access review export | E6 | 2 | 9 | sec | — | — | Planned (M9) |
| ENT-28 | Systems-of-record mapping (CRM, loyalty, PMS, warehouse), documentation only | E7 | 2 | 12 | other | — | — | Planned (M12) |
| ENT-29 | Embedding in the agent's existing tool: options and tradeoffs | E7 | 2 | 12 | other | — | — | Planned (M12) |
| ENT-30 | Event-driven trigger options; signed webhook intake on the mock API if time allows | E7 | 2 | 12 | core | — | — | Planned (M12) |
| ENT-31 | SIEM-ready security and audit export with field mapping | E7 | 2 | 12 | sec | — | — | Planned (M12) |
| ENT-32 | Privacy-filtered daily analytics export | E7 | 2 | 12 | core | — | — | Planned (M12) |
| ENT-33 | Change approval template linking eval evidence, reviewer, rollback | E8 | 2 | 18 | other | — | — | Planned (M18) |
| ENT-34 | RACI for AI operations | E8 | 2 | 18 | other | — | — | Planned (M18) |
| ENT-35 | Support tiers L1–L3 with proposed targets | E8 | 2 | 18 | other | — | — | Planned (M18) |
| ENT-36 | Business continuity during provider outage; DR approach (documentation only) | E8 | 2 | 13 | other | — | — | Planned (M13) |
| ENT-37 | Communication plan for AI changes | E8 | 2 | 18 | other | — | — | Planned (M18) |
| ENT-38 | Multilingual slices or English-only with escalation | E9 | 2 | 10 | bench | — | — | Planned (M10) |
| ENT-39 | Long, multi-issue and mixed in/out-of-scope requests | E9 | 2 | 10 | bench | — | — | Planned (M10) |
| ENT-40 | Denial-of-wallet tests; budget stops hold | E9 | 2 | 10 | bench | — | — | Planned (M10) |
| ENT-41 | Consistency: identical case twice → same deterministic outcome, non-contradicting explanation | E9 | 2 | 10 | bench | — | — | Planned (M10) |
| ENT-42 | Portfolio additions: system card, fairness, automation bias, upgrade procedure, talking points incl. unfavourable results | E10 | 4 | 19 | other | — | — | Planned (M19) |

## Appendix F: legacy problem design and end-to-end proof (Tier 1)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| LGF-01 | Defect catalog and hypotheses committed before arms B and C are built or benchmarked (Git history is the evidence) | F1 | 1 | 2–3 | bench | `docs/legacy-defect-catalog.md`, `docs/hypotheses.md` | pre-registration commit 2026-10-28 (no arm code exists); `tests/test_preregistration.py::test_documents_are_marked_preregistered` | Implemented and verified |
| LGF-02 | Synthetic 12-month legacy operating history (volume, seasonality, handling times, outcomes, SLAs, backlog, event log, member text, notes, adjustment log, modeled satisfaction proxy) | F2 | 1 | 3 | bench | `seed_data/generator/history.py` (12 months, SYNTHETIC, satisfaction proxy formula documented) | `tests/test_generator.py::test_history_frequencies_match_the_configured_mix` | Implemented and verified |
| LGF-03 | `docs/legacy-defect-catalog.md` with all F3 columns and categories (data, config, search/UI, unstructured, unfixable, controls) | F3 | 1 | 2 | bench | `docs/legacy-defect-catalog.md` | `tests/test_preregistration.py::test_catalog_has_every_defect_with_all_columns` | Implemented and verified |
| LGF-04 | `docs/kpi-tree.md` (four layers) | F4 | 1 | 2 | bench | `docs/kpi-tree.md` | `tests/test_discovery_docs.py::test_document_covers_required_topics` | Implemented and verified |
| LGF-05 | `evaluations/financial_model.py` with labelled assumptions, outputs and sensitivity | F4 | 1 | 3, 10 | bench | `evaluations/financial_model.py` (inputs labelled, outputs labelled estimates, sensitivity); M10 adds measured AI cost | `tests/test_generator.py::test_financial_model_labels_everything_as_an_estimate` | Implemented and verified |
| LGF-06 | `docs/hypotheses.md` H1–H7 with metric, slice, threshold, decision rule | F5 | 1 | 2 | bench | `docs/hypotheses.md` | `tests/test_preregistration.py::test_hypotheses_h1_to_h7_complete` | Implemented and verified |
| LGF-16 | "A as-is" variant: legacy write path without shared safeguards, reported separately, excluded from H6, unreachable outside the benchmark runner | Owner (ADR-0018) | 1 | 10 | bench | pre-registered in catalog §2b, hypotheses §3a | — | Planned (M10) |
| LGF-07 | Simulated member journey per arm (contacts, days, correct points, satisfaction proxy) | F6 | 1 | 10 | bench | — | — | Planned (M10) |
| LGF-08 | End-to-end proof chain per held-out case per arm; final ledger-state accuracy as the primary metric | F7 | 1 | 10 | bench | — | — | Planned (M10) |
| LGF-09 | Failure funnel per arm | F7 | 1 | 10 | bench | — | — | Planned (M10) |
| LGF-10 | Simulated supervisor (deterministic review policy) plus an automation-bias variant, labelled simulated | F7 | 1 | 10 | bench | — | — | Planned (M10) |
| LGF-11 | Day-one discovery analysis and dashboard page (Pareto, cost of failures, handling time, rework loops, SLA/backlog) | F8 | 1 | 3 | bench | `docs/day-one-discovery.md` + charts (report verified); dashboard page moves to M7 with the console (ADR-0034) | `tests/test_generator.py::test_committed_day_one_reports_trace_to_the_data` | Deferred: dashboard page needs the M7 console (ADR-0034); the report part is verified |
| LGF-12 | One-page problem statement with the quantified synthetic baseline | F8 | 1 | 3 | bench | `docs/problem-statement.md` | `tests/test_generator.py::test_committed_day_one_reports_trace_to_the_data` | Implemented and verified |
| LGF-13 | Opportunity sizing (impact vs effort) with predicted improvement per arm | F8 | 1 | 3 | bench | Opportunity sizing in `docs/day-one-discovery.md` (impact, effort, predicted arm from the catalog) | `tests/test_generator.py::test_committed_day_one_reports_trace_to_the_data` | Implemented and verified |
| LGF-14 | Predicted vs actual improvement per intervention, explained | F8 | 1 | 10, 19 | bench | — | — | Planned (M10) |
| LGF-15 | Bias guards (held-out hidden from C development, same defects for all arms, fair B fixes, every slice where A/B beat C, catalog review status, post-hoc changes logged) | F9 | 1 | 3–10 | bench | Same defects in every split for all arms; catalog change log; review status recorded; held-out isolation from arm C enforced in M8/M10 | — | Implemented but unverified |

## Appendices H, I, J, L

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| DOC-01 | Synthetic folios (PDF layouts), noisy receipt images, OTA emails; some disagree or carry injection; ground truth from the generator | H1 | 2 | 3 | core | `seed_data/generator/documents.py`: 22 case attachments + 60-document extraction set (folio PDFs x3 layouts, noisy receipts, OTA emails; some disagree, some carry injection) | `tests/test_generator.py::test_document_ground_truth_matches_records`, `tests/test_generator.py::test_documents_are_deterministic` | Implemented and verified |
| DOC-02 | Extraction: OCR + rules baseline and model vision extraction (mock fixtures labelled) into a typed schema | H2 | 2 | 8 | core | — | — | Planned (M8) |
| DOC-03 | Field confidence from verifiable signals only; no percentages | H2 | 2 | 8 | core | — | — | Planned (M8) |
| DOC-04 | Review routing; extracted values are evidence only, never overwrite records or bypass approval | H2 | 2 | 8 | core | — | — | Planned (M8) |
| DOC-05 | Field-level metrics per variant, review rate, cost/latency, downstream final-ledger effect | H3 | 2 | 10 | bench | — | — | Planned (M10) |
| DOC-06 | File-ingestion controls, PII, embedded-injection tests on business effects | H4 | 2 | 8, 9 | sec | — | — | Planned (M8) |
| DOC-07 | Portfolio wording: a pattern, never employer numbers | H5 | 4 | 19 | other | — | — | Planned (M19) |
| ML-01 | Request routing classes (missing points, out of scope, complaint only, multi-issue, non-English, suspected injection) | I1 | 2 | 8 | bench | — | — | Planned (M8) |
| ML-02 | Rules vs TF-IDF + logistic regression vs LLM zero/few-shot on the same grouped splits | I2 | 2 | 8, 10 | bench | — | — | Planned (M8) |
| ML-03 | Seeded training, versioned artifacts, imbalance handling, confusion matrix, reliability curve, drift check, model card, cost/latency per 1,000 | I3 | 2 | 8 | bench | — | — | Planned (M8) |
| ML-04 | Decision rule against pre-set thresholds; labels from scenario facts only | I4 | 2 | 10 | bench | — | — | Planned (M10) |
| ML-05 | Optional embedding classifier or PEFT small model, or Blocked with prerequisites | I2 | 2 | 8 | bench | — | — | Planned (M8) |
| METH-01 | `docs/engagement-method.md` mapping neutral steps to Stage 9 artifacts | J1 | 4 | 17 | other | — | — | Planned (M17) |
| METH-02 | "Evidence-based adjustment with human approval" pattern: what changes and what stays per domain | J2 | 4 | 17 | other | — | — | Planned (M17) |
| METH-03 | Telecom billing-credit mini-domain from the scaffold: rules, mock API, 15 cases, mini A/B/C, smoke test, time and reuse recorded | J3 | 4 | 17 | other | — | — | Planned (M17) |
| METH-04 | `docs/domain-intake-checklist.md` | J4 | 4 | 17 | other | — | — | Planned (M17) |
| METH-05 | Explicit statement: method transfers, discovery/rules/validation/approvals must be redone | J5 | 4 | 17 | other | — | — | Planned (M17) |
| LIVE-01 | Two or three hosting options with sourced monthly costs and teardown steps, before anything is created | L1 | 2 | 12 | other | — | — | Planned (M12) |
| LIVE-02 | Deploy only after approval, from main; verify with the Playwright happy path; then the live link | L1, PA-10 | 2 | 12 | core | — | — | Planned (M12) |
| LIVE-03 | GenAI OpenTelemetry conventions checked; instrumented if usable; attribute names isolated; no prompt/response content by default | L2 | 2 | 12 | core | — | — | Planned (M12) |
| LIVE-04 | LLM observability tooling decision (adopt / not needed / revisit) | L3 | 2 | 12 | other | — | — | Planned (M12) |
| LIVE-05 | Daily and monthly spending caps stored in the database, persisted across restarts, tested before public deploy | PA-10 | 2 | 8, 12 | sec | — | — | Planned (M8) |

## Portfolio presentation addendum (Tier 4)

| ID | Requirement | Spec | Tier | M | Score | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| PA-01 | Stage card in house structure: real output on top; exactly three metrics (A vs B vs C final-ledger, a safety result, cost per 1,000 cases) with counts, runs, held-out, date + version; Live only with a verified link, else Built; link labels; simulated label | Addendum 1 | 4 | 19 | other | conventions in `docs/continuity.md` §8 | — | Planned (M19) |
| PA-02 | Case study with the current sections; leads with problem and measured outcome; includes where AI did not help | Addendum 2 | 4 | 19 | other | — | — | Planned (M19) |
| PA-03 | Website PRs (never merged without OK): stage list, "How I work" table, OG image + alt text matching the card, projects.json and no-JS copies in sync | Addendum 3 | 4 | 19 | other | — | — | Planned (M19) |
| PA-04 | Demo video via the video kit from the real app: first-person narration, captions, transcript, real duration, generated-voice line; audio audit; owner's OK in their player before any PR | Addendum 4 | 4 | 19 | other | — | — | Planned (M19) |
| PA-05 | README consistent with the other repos (label, CI badge, three dated metrics, real output, demo link, quickstarts, Mermaid, AI control boundary, A/B/C table, reproduce, security, limitations, stage links) | Addendum 5 | 4 | 19 | other | — | — | Planned (M19) |
| PA-06 | One honest notes post, draft only | Addendum 6 | 4 | 19 | other | — | — | Planned (M19) |
| PA-07 | LinkedIn post and 2–3 résumé bullets, drafts only, Stage 9 verified numbers only, labelled simulated | Addendum 7 | 4 | 19 | other | — | — | Planned (M19) |
| PA-08 | Plain-English tone; every shown number traces to a stored result file | Addendum 8 | 4 | 1–19 | other | `CLAUDE.md` "Portfolio writing" | checked at M19 with the video kit's `numbers_check.py` | Planned (M19) |
| PA-09 | Secrets only via `.env` and dashboard secrets; never shown; prove old credential fails after rotation | Addendum 9 | 4 | 1–19 | sec | `CLAUDE.md`, `app/preflight.py`, `.claude/settings.json` | `tests/test_preflight.py::test_output_never_contains_values` | Implemented but unverified |
| PA-10 | PS–8 lessons: narration matches reports; latency labelled (model + tools vs browser); deploy only from main; verify live links; same-change-set consistency; caps persisted in DB; TOML secrets block with a set/missing check | Addendum 10 | 4 | 1–19 | other | `CLAUDE.md`; LIVE-02, LIVE-05 | — | Planned (M12) |
