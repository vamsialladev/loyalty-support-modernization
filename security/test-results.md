# Security test results (SEC-02, SEC-19)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

**Date:** 2026-11-06. **Environment:** the owned local setup and CI. **Models:** mock and scripted only. **No real model was called.**

Tests check business effects and access boundaries, never refusal wording. A pass means the attack changed nothing the test can see. It doesn't mean the attack can't work some other way.

## Attempted

| Attack | Cases | How | Result |
|---|---|---|---|
| Injection in a message, arm B | 11 | Message attacks run through the conventional path | No business effect |
| Injection in a message, arm C | 11 | The same messages, mock model | No business effect |
| A model that fully obeys the attacker | 6 | Scripted models acting on the attack | Reached nothing |
| Tool misuse | 6 | Scripted models calling tools wrongly | The run stops, and the case keeps arm B's result |
| Tool flood, exhausted budget, provider outage | 3 | Scripted models | Stops at the limits; the case still works |
| Poisoned document | 2 | Instructions inside a document | Evidence only; reaches the model labelled as data |
| Unsafe files | 4 | Files that fail type, size or content checks | Refused |
| Unsafe output | 2 | Script in model text; a `javascript:` link in a message | Escaped; not clickable |
| Secret extraction | 2 | A secret pasted into a message; prompts and settings through tools | Neither got through |
| Approval tampering, posting directly | 2 | A changed amount; an agent posting to approve or execute | Approval void; refused |
| Replay | 2 | Executing twice; an expired session | One credit; refused |
| Shared corpus (`hotel-ai-platform`, `3879d00`) | 30 attacks, 5 controls | Two arms, on business effects | No effect from attacks; controls not held up |
| Authorization, sign-in, limits, accounts, retention, outbound | see `tests/test_security_authz.py` | Includes a test that walks the real routes | Passes after the fix below |
| OIDC: forged tokens, wrong issuer or audience, `alg: none`, rotated keys | see `tests/test_oidc.py` | Plus a real Keycloak in a real browser, 7 of 7 | `evidence/oidc-check-2026-11-06.txt` |

Final counts per run are in `docs/verification-log.md`, Milestone 9.

## What failed along the way

| Finding | Kind | What happened |
|---|---|---|
| **The approvals list showed other customers' pending requests** | **Real bug** | Found by the cross-customer tests on their first run. Fixed in `pending_approvals`, with the test kept |
| Login-limit test failed once in 135 | Test timing | Sign-ins are slow under load, and that test ran close to a 300 s window's edge. It passed alone. The cause is **likely, not proven:** the times in the run's record allow a crossing without showing one. The test now has a fixed clock |
| Rate limits use fixed windows | Real limit, kept | That test exposed the cost, and a new test pins it: at most 10 tries on one account close together, not 5 |

## Not run, or not covered

- **Repeating model-based tests to show variability: NOT RUN.** It needs a live model, which costs money, so it waits for the owner's go-ahead.
- **Cross-user stream access:** there's no streaming endpoint.
- **Malicious callbacks:** there are none until Milestone 11. Only the URL gate exists.
- **MFA:** a guide only. Nothing tests it, because nothing enforces it.
- **No penetration test and no independent review.**

## Residual

**Prompt injection isn't solved.** These tests show what a model obeying an attacker can reach, not how often one would, nor whether a convincing wrong explanation could sway a reviewer. The full list is in `residual-risks.md`.
