# Security test plan (SEC-02, SEC-19)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

Owned environment only. Tests assert on business effects and access boundaries, never on refusal wording.

| Area (spec C.9) | Where |
|---|---|
| Broken authentication, role escalation | `tests/test_security_authz.py`, `tests/test_console_web.py`, `tests/test_oidc.py` |
| Unauthorized record access | `tests/test_security_authz.py`, `tests/test_arm_c.py` |
| Direct and indirect injection | `tests/test_red_team.py`, `tests/test_red_team_shared_corpus.py` |
| Tool misuse, unsupported claims | `tests/test_red_team.py`, `tests/test_ai_tools.py` |
| Secret extraction | `tests/test_red_team.py` |
| Malicious and poisoned documents | `tests/test_red_team.py`, `tests/test_extraction.py` |
| Unsafe generated output | `tests/test_red_team.py` |
| SSRF, malicious callbacks | `tests/test_security_authz.py` (callbacks don't exist until Milestone 11) |
| Approval tampering | `tests/test_red_team.py`, `tests/test_write_path_postgres.py` |
| Duplicate execution, replay | `tests/test_red_team.py`, `tests/test_execution_postgres.py` |
| Expired credentials | `tests/test_red_team.py`, `tests/test_security_authz.py` |
| Worker interruption, provider outage | `tests/test_execution_postgres.py`, `tests/test_arm_c.py` |
| Budget and resource exhaustion | `tests/test_red_team.py`, `tests/test_ai_provider.py` |
| Cross-user stream access | **Not applicable yet:** there's no streaming endpoint |

**Repeating model-based tests to show variability:** needs a live model. NOT RUN until the owner approves it.
