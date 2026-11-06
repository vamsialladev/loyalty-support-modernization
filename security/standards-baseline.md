# Standards baseline (SEC-01)

> Simulated engagement, synthetic data. **Technically verified for the tested scope; organizational approvals pending.** No certification or compliance is claimed.

Consulted on 2026-11-06, from each owner's own page. This is the list we chose controls from, not a claim of conformance.

| Source | Version | Where read | How it's used |
|---|---|---|---|
| NIST AI RMF | 1.0, NIST AI 100-1 (2023-01-26). The page says it's being revised | nist.gov/itl/ai-risk-management-framework | Risk language for `risk-register.md` |
| NIST Generative AI Profile | NIST AI 600-1 (2024-07-26) | same page | Risk categories for arm C |
| NIST SSDF | SP 800-218 v1.1; SP 800-218A for generative AI | csrc.nist.gov/projects/ssdf (page updated 2026-10-06) | CI gates, dependency and secret checks |
| OWASP ASVS | 5.0.0 (2025-05-30) | asvs.owasp.org | Sessions, authentication and access-control checks in `control-matrix.md` |
| OWASP Top 10 for LLM and GenAI apps | 2025 list | genai.owasp.org/llm-top-10 | Mapped in `control-matrix.md` |
| OWASP agentic security guidance | Linked from that site; **not read in depth yet** | genai.owasp.org | To read with Milestone 11's protocols |
| Protocol security specifications (MCP, A2A) | **Not read yet:** Milestone 11 | | No protocol is exposed yet |
| Keycloak | 26.4.2, the image used | quay.io | `scripts/oidc_check.ps1` |

**Excluded for now, with reasons:** ASVS levels above what a local demo can show (TLS, HSTS and deployment headers wait for Milestone 12). SOC 2 and ISO controls: organizational, and out of a simulation's reach.
