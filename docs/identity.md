# Identity (SEC-07, SEC-08, SEC-10; ENT-24, ENT-25)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

| | Local demo | OIDC profile |
|---|---|---|
| Set by | `AUTH_MODE=local` (default) | `AUTH_MODE=oidc`, `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `APP_BASE_URL` |
| Passwords | argon2id, here | The provider's. An OIDC account has no usable password here |
| Rate limits | 5 failures per account and 30 per address in 5 minutes | The provider's, plus the console's request limit |
| Recovery | One-use link from an administrator, 30 minutes | The provider's |
| Roles | Stored on the account | From groups on each sign-in (`config/customers/hg-demo.yaml`); no mapped group means no access |
| MFA | **None** | **The provider's. Not enforced or tested here** |

**Try the real thing:** `powershell -ExecutionPolicy Bypass -File scripts\oidc_check.ps1`. It's free and removes itself afterwards.

**Local limits:** no MFA, an administrator hands over recovery links, and the demo accounts share one password. It isn't meant for production, and the preflight's profiles say so.

**MFA (SEC-10), as a guide only:** in Keycloak, make `CONFIGURE_TOTP` a required action for the admin and supervisor groups through an authentication-flow condition on group membership. **Don't claim this is enforced until it's turned on and tested.**

**SCIM (ENT-24):** not implemented. Local Keycloak has no built-in SCIM server. What's demonstrated instead: a user disabled at the provider can't sign in again (`scripts/oidc_check.ps1`), and one deactivated here is out at once, whatever the provider says (`tests/test_oidc.py`). With a provider that pushes SCIM, map `active=false` to `accounts.set_active`.

**Workload identity:** people and machines are separate. Machines use read-only tokens that last 7 days. The customer systems use a static token here; a real platform should issue short-lived ones (`docs/real-system-swap-guide.md`).

**Supabase Auth profile:** not built. Its rows in the matrix stay open.
