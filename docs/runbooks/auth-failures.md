# Repeated sign-in failures

**Alert:** `loyalty-auth-failures`: more than 20 failed sign-ins in 15 minutes (`loyalty_security_refusals` with
`action="sign_in_failed"`). **Proposed owner:** security (L3). Synthetic data only.

**You notice:** the alert; staff report being locked out ("Too many requests").

1. Look at the events: `GET /api/v1/security/events?since=<today>` as an auditor, or
   `python -m app.services.security_events --since <today>`. A failed sign-in names no user (what was typed may be a
   password), so look at the time pattern and the rate-limit events (`rate_limited`).
2. Rate limits already slow it down: per username and per address (`app/services/rate_limit.py`).
3. **One person who forgot their password:** an administrator issues a recovery link (`/admin/users`). It's recorded
   as `recovery_issued`.
4. **Many tries from many places (a password-spraying pattern):** with OIDC (`AUTH_MODE=oidc`), check the identity
   provider's own sign-in log. With local accounts, consider deactivating the shared demo accounts.
5. Record what you saw and did as an incident (`docs/incident-response.md` once it exists, Milestone 13).

**Check it worked:** failures fall back below the threshold, the people affected can sign in, and the alert clears.
