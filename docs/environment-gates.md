# Release gates per environment

Spec C.10; SEC-22; ADR-0085. What must be true before a release reaches each environment. A gate is passed by
evidence (a green CI run, a check's output, a signed-off decision), never by someone saying so. Today only
**local/demo** exists. The staging and production rows are what a customer's deployment would hold to, and nothing
here claims they've been passed.

| Criterion (spec C.10) | Local / demo | Staging | Production |
|---|---|---|---|
| Authorization tests pass | CI `checks` (authorization, CSRF, red-team suites) | the same, on the release commit | the same, on the release commit |
| Approval and idempotency tests pass | CI `checks` + `postgres` (real Postgres) | the same | the same |
| No exposed secrets | gitleaks over the full history (CI `secrets`); GitHub secret scanning and push protection | the same | the same |
| Validated configuration | `python -m app.preflight --profile portfolio` | `--profile staging` (refuses defaults and short secrets) | `--profile approved` (also refuses shared demo accounts; execution off unless approved) |
| Images clean | CI `images`: Trivy, 0 fixable HIGH/CRITICAL; SBOM | the same image, by digest | the same image, by digest, with its provenance attestation verified |
| AI changes | release gate (`docs/release-gate.md`) | the same | the same, plus the AI operations owner's sign-off |
| Triaged findings | known limitations kept current | every open finding has an owner and a date | no open HIGH finding without an accepted-risk decision |
| High-impact risks with accountable decisions | ADRs | the sponsor's sign-off on the risk register | the sponsor's sign-off, recorded |
| Rollback ready | `docs/rollback.md` | a rehearsed image rollback | a rehearsed image rollback and a restore drill (Milestone 13) |
| Who approves | the engineer | a second engineer | the customer's change approver (the `production` environment's reviewers, `deploy.yml`) |

## Honest wording
- "Passed CI" means the listed jobs were green on that commit, no more.
- "Production-ready" isn't said anywhere in this repository: no production exists.
- A gate that can't be checked (no environment yet) is shown as **not reached**, never as passed.
