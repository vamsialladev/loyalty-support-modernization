# Customer access checklist (SEC-04)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

Fill in with the customer before any real connection. **Nothing here has been done with a real customer.**

- [ ] A written data agreement, and a named data owner
- [ ] Provider terms read: retention, training, region. Recorded as verified or unverified
- [ ] Least-privilege service accounts for each customer system, read and write separately
- [ ] Credentials in the customer's secret manager, not `.env`
- [ ] An outbound allowlist agreed with their network team
- [ ] Their identity provider connected; groups mapped to roles in `config/customers/`
- [ ] MFA required for supervisors and administrators, on their side
- [ ] Log, retention and backup periods agreed
- [ ] A sandbox with their test data before production
- [ ] Rotation and revocation owners named

## Onboarding someone
- [ ] Add them to the right group at the identity provider. Don't create local accounts in production
- [ ] Confirm the role on `/admin/users`
- [ ] Walk through the staff guide (Milestone 18)

## Offboarding someone
- [ ] Disable them at the identity provider
- [ ] Deactivate them on `/admin/users`, which ends their sessions at once
- [ ] Revoke any API tokens they issued
- [ ] Rotate shared credentials they could read
- [ ] Note it in the next access review
