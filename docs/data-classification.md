# Data classification (SEC-04)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

| Class | Examples | Handling |
|---|---|---|
| Secret | Keys, passwords, tokens, `APP_SECRET_KEY` | `.env` or a secret manager; hashes in the DB; never logged or sent to a model |
| Personal | Names, emails, phones, birth dates, stays, ledger, message text, documents | Staff only; minimized before a model; removed by retention and erasure |
| Financial record | Adjustments: member number, stay, points | Kept for audit; not removed by erasure |
| Audit | `case_events`, `system_events` | Append-only for the app role; no message text, by design |
| Business | Policies, rules, prompts | Versioned; publishing is controlled |
| Evaluation | Labels, benchmark data | Never reachable from the app or its images |

**Redaction reduces risk. It isn't anonymization.** All data here is synthetic. These rules don't make arbitrary client data permissible.
