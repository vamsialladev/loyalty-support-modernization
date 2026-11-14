# Maintenance schedule

Spec C.10; SEC-23; ADR-0085. Owners are **proposed roles**; a customer names people at handover. Each activity
leaves evidence, and any change it causes goes through the normal pull request and CI, including the release gate.
**Nothing deploys itself:** no prompt, policy or feedback change reaches a running system without a reviewed pull
request and, for production, the environment's approval.

| Activity | How often | Proposed owner | How | Evidence |
|---|---|---|---|---|
| Dependency updates | weekly | application team | Dependabot pull requests (`.github/dependabot.yml`), full CI | merged or closed PRs |
| Vulnerability audit | every pull request, and weekly | application team | `pip-audit` (CI `checks`), Trivy (CI `images`) | CI logs |
| Base image refresh | monthly, or when Trivy finds a fixable HIGH | application team | bump the `python:3.12.x-slim-bookworm` tag (ADR-0084) | the PR and its scan |
| Model status | monthly, and on any provider notice | AI operations owner | `python -m app.ai.lifecycle`; re-read the provider's deprecation and price pages; update `config/ai/` | the lifecycle output; `checked_on` dates |
| Release gate baseline | when an intended AI change lands | AI operations owner + a reviewer | re-baseline `c-mock-dev` (`docs/release-gate.md`) | the reviewed PR |
| QA review of samples | weekly | supervisors, auditors | `/api/v1/qa/samples` (`docs/qa-rubric.md`) | `qa_samples` rows |
| Drift check | weekly | AI operations owner | `python -m app.services.drift` (`docs/runbooks/ai-quality-drift.md`) | the JSON report |
| Feedback to dataset | monthly | AI operations owner + a labeler | `python -m evaluations.feedback_candidates` (`docs/release-gate.md`) | the reviewed sheet |
| Security event review | weekly | security | `python -m app.services.security_events --since …` | the export |
| Access review | quarterly | security + the sponsor | `/admin/access-review.csv` | the signed review |
| Secret rotation | every 90 days, and on any suspicion | security | rotate, then prove the old value fails (Appendix K) | the rotation note |
| Retention | daily (the worker), and the owner-run purge quarterly | application team | `retention_sweep`; `security_events --purge` | `retention_applied` events |
| Backup check | monthly | application team | restore into a scratch database (`docs/backup-restore.md`) | the restore note |
| Policy updates | when the loyalty program changes | the policy owner | draft, publish in `/admin`, with a policy-change test | `policy_published` events |
| Documentation links | quarterly | application team | a link check of `docs/` (lychee, with the Milestone 19 presentation work) | CI |
