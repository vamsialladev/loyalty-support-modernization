# Role coverage map

> PURP-07. One row per role from the project purpose (lens 11). **Shown** only with real evidence in this repo;
> otherwise **planned** (with the milestone) or **not covered**. Updated at the end of every milestone.

| Role | Evidence in the repo | Milestone | Status | Questions this role would ask (and where the answer lives) |
|---|---|---|---|---|
| Forward Deployed / Solutions Engineer | `docs/customer-discovery.md`, `docs/stage0-loyalty-addendum.md`, `docs/continuity.md`, `docs/day-one-discovery.md`, `docs/problem-statement.md` | 1–3 | Shown (discovery, day-one analysis); integration, demo and handover planned (M4, M19, M18) | How did you scope it? (addendum §2) · What would make the client stop? (discovery §6) |
| AI / Applied AI Engineer | `docs/product-requirements.md` §3 (AI boundary), ADR-0019 | 2 | Planned (M8) | What can the model never do? (product requirements §3) · How is the loop bounded? (M8) |
| ML Engineer / Applied Scientist | `docs/hypotheses.md` (decision rule, paired bootstrap), `docs/experiment-plan.md`, grouped and temporal splits with leakage tests (`tests/test_generator.py`), `benchmarks/datasets/v1/composition.md` (re-weighting factors) | 2–3 | Shown (experiment design, dataset splits); classical-ML baseline planned (M8) | How do you avoid tuning on held-out? (hypotheses §2) · How do you prevent leakage between splits? (`test_no_member_stay_or_text_crosses_splits`) · Why re-weight held-out? (composition.md) |
| MLOps / LLMOps Engineer | — | — | Planned (M10, M12) | How is a model change gated? (M10) |
| Data Engineer | `seed_data/generator/` (deterministic generator, canonical models), `docs/data-dictionary.md`, `benchmarks/datasets/v1/manifest.json` (checksums), `config/customers/hg-demo.yaml` (field mapping), referential-integrity tests | 2–3 | Shown | Is the data reproducible? (`test_committed_manifest_is_reproduced`) · How would a real export replace it? (swap guide, M3 section) · Where is each field defined? (data dictionary) |
| Backend / Platform Engineer | `mock_customer_api/` (FastAPI, SQLAlchemy, Alembic), `app/adapters/mock_customer_api.py`, `docker-compose.yml`, real-Postgres tests (`tests/test_mock_api_postgres.py`) | 2, 4 | Shown (service, persistence, idempotency, containers); durable jobs and the app's write path planned (M6) | What happens if 20 requests arrive with one idempotency key? (`test_twenty_concurrent_requests_with_one_key_apply_once`) · What if the response is lost after commit? (ADR-0039, `test_commit_then_lost_is_uncertain_and_then_found`) |
| Site Reliability Engineer | `/healthz` and `/readyz` on both services, compose health checks, resource limits | 4 | Shown (health and readiness only); SLOs, alerts and drills planned (M12, M13) | How do you know the stack is ready? (`/readyz`: database migrated, mock seeded, customer systems reachable) |
| Security Engineer | `security/threat-model.md`, `app/preflight.py`, `app/env_leaks.py`, `tests/test_secrets_hygiene.py` | 1–2 | Shown (secret hygiene, threat model draft); authorization and red team planned (M9) | Where could points move without approval? (threat model T01–T04) · How are secrets kept out of Git? (secrets tests) |
| Solutions / Enterprise Architect | `docs/architecture.md`, `docs/real-system-swap-guide.md` (endpoint-by-endpoint swap table), `customer_shapes` + `config/customers/` | 2–4 | Shown (target architecture, integration pattern, swap paths) | How would the real loyalty platform plug in? (swap guide) |
| Staff / Principal Engineer | `docs/decisions.md`, `docs/technical-strategy.md` | 1–2 | Shown (ADRs, strategy draft); RFCs planned (M6) | What would make you reverse a decision? (ADRs) · What breaks first at 10×? (scaling and limits) |
| Engineering Manager / Tech Lead | `docs/implementation-plan.md`, `docs/registers.md`, `docs/onboarding.md` | 1–2 | Shown (plan, risks, dependencies, onboarding) | What's blocked and on whom? (registers §1) |
| Product Manager | `docs/business-requirements.md`, `docs/product-requirements.md` | 2 | Shown | What are you not building? (business requirements §5) · How do you roll out? (§7) |
| Technical Program Manager | `docs/implementation-plan.md`, `docs/implementation-status.md`, `docs/requirements-matrix.md` | 1–2 | Shown | Where are we against plan? (status) |
| QA / Test Engineer | `tests/` (guidance, matrix, secrets, pre-registration, discovery docs, generator: reproducibility, integrity, leakage, label independence) | 1–3 | Shown (document, config and data tests); product test strategy planned (M6–M7) | How do you know a test isn't passing for the wrong reason? (verification log, M1 row 14) · How are labels checked? (ADR-0029, `test_labeler_recomputes_every_stored_label`) |
| Customer Success / Support Lead | — | — | Planned (M18) | How are agents trained? (M18) |
| Responsible AI / Governance | `docs/governance.md`, pre-registration (`docs/hypotheses.md`), fairness set of counterfactual pairs (`benchmarks/datasets/v1/fairness.jsonl`, ADR-0031), owner label review | 2–3 | Shown (governance, pre-registration, fairness data); fairness results and system card planned (M8, M10) | Who can approve an adjustment? (governance §2) · Do equivalent facts get the same outcome? (`test_fairness_pairs_get_the_same_outcome`; results in M10) |
| Executive sponsor | `docs/executive-brief.md` | 2 | Shown (phase 1 brief) | What decision do you need from me? (executive brief) |

## Roles exercised by milestone
- **M1:** Security Engineer, Engineering Manager / Tech Lead, Technical Program Manager, QA, Staff / Principal (ADRs).
- **M2:** Forward Deployed Engineer, Product Manager, ML Engineer / Applied Scientist (experiment design), Solutions
  Architect, Security Engineer (threat model), Responsible AI (governance), Executive sponsor (brief).
- **M4:** Backend / Platform Engineer (mock service, idempotency, containers), QA (contract tests, fault matrix),
  Solutions Architect (swap table, mapping layer), Security Engineer (per-system roles, non-root read-only images, no
  labels in images), SRE (health and readiness).
- **M3:** Data Engineer (generator, dictionary, checksums, mapping), ML Engineer / Applied Scientist (splits, leakage,
  re-weighting), QA (data tests, label cross-check), Responsible AI (fairness set), Forward Deployed Engineer (day-one
  analysis), Executive sponsor (phase 2 brief), Solutions Architect (swap path for real data).
