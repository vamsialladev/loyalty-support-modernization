# Data-flow map (SEC-04)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

| From | To | Carries | Protection | Not carried |
|---|---|---|---|---|
| Browser | App | Forms, session cookie | HttpOnly, SameSite=Strict, CSRF, CSP. TLS at hosting (M12) | |
| App or worker | Customer systems | Member, stay and ledger reads; adjustments | Bearer token, typed adapter, timeouts | Message text |
| Worker | Model provider | Redacted message and document text; stay and ledger summaries; excerpts; first and last name | Redaction, tools scoped to the member, live off by default | Email, phone, birth date, secrets, hidden reasoning stored back |
| App | Identity provider | Code, client secret, PKCE verifier | Configured destination only, no redirects | Passwords: the provider handles those |
| App or worker | Logs | IDs, statuses, error classes | No message text; secrets masked | Personal data, by design: verify in a pilot |
| Any | Backups | Everything in the DB | None configured locally | Erasure doesn't reach backups |
