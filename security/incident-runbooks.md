# Incident runbooks (spec C.10)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

**Not exercised as a team:** written and tabletop-checked by the author only, except where a step says it was run. Each covers containment, revocation, investigation, recovery and improvement.

| Incident | Contain | Revoke | Investigate | Recover | Improve |
|---|---|---|---|---|---|
| Leaked model key | Set `FEATURE_LIVE_AI=false`; restart the worker. Arm C falls back to arm B | Revoke it in the provider's console; prove the old one fails | `ai_runs`, `ai_spend`, the provider's usage page; `gitleaks` over the history | New key in `.env`; run the smoke test | Find how it leaked; add a scan rule |
| Compromised integration credential | Engage the kill switch | Rotate `MOCK_API_TOKEN` (`docs/credential-rotation.md`, exercised); restart | `case_events`, the platform's own log, by adjustment ID | Reconcile adjustments against the ledger | Shorter-lived credentials |
| Unauthorized data access | Deactivate the account (`/admin/users`), which ends its sessions | Issue recovery; revoke API tokens | `system_events` (`authorization_denied`, `sign_in_failed`), access review CSV | Tell the privacy owner; assess notification with legal | A test for the path used |
| Malicious policy document | Stop publishing; engage the kill switch if rules changed | Remove the publisher's access | Compare checksums in `policy_versions`; approvals ended by the change | Publish a corrected version; a version is never edited | More regression cases |
| Unexpected agent action | `FEATURE_LIVE_AI=false`; cancel runs | | `ai_steps` by run; `ai_runs.stop_reason` | Re-investigate on arm B | Add the case to `tests/test_red_team.py` |
| Compromised dependency | Pin the last good version; rebuild | Rotate anything the process could read | `pip-audit`, the lock file's history | Redeploy from a clean build | Review how it arrived |
| Excessive model spend | Lower `LLM_BUDGET_USD_*`, or turn live off | | `ai_spend`, `ai_runs` by cost | Restore the caps | Tune limits with the owner |
