# Residual risks (SEC-02)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

What the controls don't cover. Each needs an accountable decision before any real use.

1. **Prompt injection isn't solved.** The tests show what a model obeying an attacker can reach. A convincing wrong explanation could still sway a reviewer.
2. **The live security evidence is thin.** The stress set ran live 3 times, with no false approval and no duplicate or unauthorized action. The red-team suite and the shared corpus still run on mock and scripted models. Nothing has tested a real person reading a convincing wrong explanation.
3. **The audit log isn't tamper-proof.** The app role can't change it. A database owner can.
4. **Redaction is pattern matching.** Names stay on purpose.
5. **Provider data terms are unverified.** "Not used for training" wouldn't mean no retention or company approval.
6. **MFA is only a guide here.** Nothing enforces it (`docs/identity.md`).
7. **Rate limits trust the socket address.** Behind a proxy that's the proxy, until a trusted header is set up.
8. **Backups keep erased data until they expire.** None exist in this local setup; a real deployment would have them.
9. **No malware scanning on uploads.**
10. **Local demo auth isn't for production.** There's no MFA, and recovery depends on an administrator.
11. **Free text in some audit events** (a reopen reason, for example) isn't removed by erasure.
12. **Not reviewed by anyone independent.** No penetration test, and no external review.
