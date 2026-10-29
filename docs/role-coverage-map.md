# Role coverage map

> PURP-07. One row per role from the project purpose (lens 11). **Shown** only with real evidence in this repo;
> otherwise **planned** (with the milestone) or **not covered**. Updated at the end of every milestone.

| Role | Evidence in the repo | Milestone | Status | Questions this role would ask (and where the answer lives) |
|---|---|---|---|---|
| Forward Deployed / Solutions Engineer | `docs/customer-discovery.md`, `docs/stage0-loyalty-addendum.md`, `docs/continuity.md` | 1–2 | Shown (discovery only); integration, demo and handover planned (M4, M19, M18) | How did you scope it? (addendum §2) · What would make the client stop? (discovery §6) |
| AI / Applied AI Engineer | `docs/product-requirements.md` §3 (AI boundary), ADR-0019 | 2 | Planned (M8) | What can the model never do? (product requirements §3) · How is the loop bounded? (M8) |
| ML Engineer / Applied Scientist | `docs/hypotheses.md` (decision rule, paired bootstrap), `docs/experiment-plan.md` | 2 | Shown (experiment design); classical-ML baseline planned (M8) | How do you avoid tuning on held-out? (hypotheses §2) · What counts as inconclusive? (hypotheses §2) |
| MLOps / LLMOps Engineer | — | — | Planned (M10, M12) | How is a model change gated? (M10) |
| Data Engineer | `docs/legacy-discovery.md` §5–6 (source register, data quality) | 2 | Planned (M3 generator) | Which system is the source of truth for points? (legacy discovery §5) |
| Backend / Platform Engineer | `docs/architecture.md` | 2 | Planned (M4, M6) | How do you prevent duplicate credits? (architecture §4; M6) |
| Site Reliability Engineer | — | — | Planned (M12, M13) | What are the SLOs? (M12) |
| Security Engineer | `security/threat-model.md`, `app/preflight.py`, `app/env_leaks.py`, `tests/test_secrets_hygiene.py` | 1–2 | Shown (secret hygiene, threat model draft); authorization and red team planned (M9) | Where could points move without approval? (threat model T01–T04) · How are secrets kept out of Git? (secrets tests) |
| Solutions / Enterprise Architect | `docs/architecture.md`, `docs/real-system-swap-guide.md` | 2 | Shown (target architecture); swap paths grow each milestone | How would the real loyalty platform plug in? (swap guide) |
| Staff / Principal Engineer | `docs/decisions.md`, `docs/technical-strategy.md` | 1–2 | Shown (ADRs, strategy draft); RFCs planned (M6) | What would make you reverse a decision? (ADRs) · What breaks first at 10×? (scaling and limits) |
| Engineering Manager / Tech Lead | `docs/implementation-plan.md`, `docs/registers.md`, `docs/onboarding.md` | 1–2 | Shown (plan, risks, dependencies, onboarding) | What's blocked and on whom? (registers §1) |
| Product Manager | `docs/business-requirements.md`, `docs/product-requirements.md` | 2 | Shown | What are you not building? (business requirements §5) · How do you roll out? (§7) |
| Technical Program Manager | `docs/implementation-plan.md`, `docs/implementation-status.md`, `docs/requirements-matrix.md` | 1–2 | Shown | Where are we against plan? (status) |
| QA / Test Engineer | `tests/` (guidance, matrix, secrets, pre-registration, discovery docs) | 1–2 | Shown (document and config tests); product test strategy planned (M6–M7) | How do you know a test isn't passing for the wrong reason? (verification log, M1 row 14) |
| Customer Success / Support Lead | — | — | Planned (M18) | How are agents trained? (M18) |
| Responsible AI / Governance | `docs/governance.md`, pre-registration (`docs/hypotheses.md`) | 2 | Shown (governance, pre-registration); system card and fairness planned (M8, M10) | Who can approve an adjustment? (governance §2) |
| Executive sponsor | `docs/executive-brief.md` | 2 | Shown (phase 1 brief) | What decision do you need from me? (executive brief) |

## Roles exercised by milestone
- **M1:** Security Engineer, Engineering Manager / Tech Lead, Technical Program Manager, QA, Staff / Principal (ADRs).
- **M2:** Forward Deployed Engineer, Product Manager, ML Engineer / Applied Scientist (experiment design), Solutions
  Architect, Security Engineer (threat model), Responsible AI (governance), Executive sponsor (brief).
