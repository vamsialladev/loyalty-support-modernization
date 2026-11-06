# System inventory (SEC-02)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

| Component | What it does | Runs as | Reaches | Status |
|---|---|---|---|---|
| Web app (`app/main.py`) | Console and JSON API | `loyalty_app` DB role | App DB; customer systems | Implemented |
| Worker (`app/worker.py`) | Jobs: investigation, execution, reconciliation, retention | `loyalty_app` | App DB; customer systems; model provider | Implemented |
| Migrate job | Schema changes | `loyalty_owner` | App DB | Implemented; one-shot |
| PostgreSQL 16 | App data, audit, jobs, spend | | | Implemented, local |
| Mock customer API | Stands in for loyalty platform, PMS, ticketing | `mock_api` DB role | Its own DB | **Simulated** |
| Model provider | Claude, through the SDK | API key, worker only | Anthropic's API | **Configured, not called** |
| Identity provider | Keycloak, local | | | Implemented for the OIDC profile; local only |
| CI | GitHub Actions: tests, real Postgres, gitleaks | GitHub token | The private repo | Implemented |
