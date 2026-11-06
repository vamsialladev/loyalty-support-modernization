# Rotating a credential (ACC-08)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

**Exercised once with a test credential:** `tests/test_security_authz.py::test_rotating_the_customer_systems_token_makes_the_old_one_fail` runs in CI, and proves the old value fails. Other credentials follow the same steps, and haven't been exercised.

1. Make a new value. Never paste it into chat or a commit.
2. Put it in `.env` (or the secret manager). Run `python -m app.preflight --profile <name>`, which prints set or missing and no values.
3. Restart what reads it: `powershell -ExecutionPolicy Bypass -File scripts\stack.ps1 -Action up`.
4. **Prove the old value fails.** Don't assume it does.
5. Note the date in the verification log, without the value.

| Credential | Who reads it | Notes |
|---|---|---|
| `MOCK_API_TOKEN` | App, worker, mock API | Exercised in a test |
| `APP_SECRET_KEY` | App, worker | Rotating it voids approvals not yet executed, by design: they must be approved again |
| `APP_DB_PASSWORD`, `APP_OWNER_DB_PASSWORD` | Compose | `scripts\update-local-env.ps1`, and the role needs `ALTER ROLE` |
| `ANTHROPIC_API_KEY` | Worker | Revoke it in the provider's console |
| `OIDC_CLIENT_SECRET` | App | Regenerate at the provider |
| API tokens | Other systems | Issue a new one, then revoke the old by name on `/admin/users` |
