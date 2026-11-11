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
| OWASP Top 10 for Agentic Applications | "for 2026" edition, page dated 2025-12-09 (ASI01–ASI10). Read 2026-11-11 from the published PDF's item list | genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026 | Mapped in `control-matrix.md` (agentic table). "Securing Agentic Applications V2" (2026-11-10) is listed there and **not read yet** |
| MCP specification: authorization, transports, security best practices | 2026-07-28. Read 2026-11-11 | modelcontextprotocol.io/specification/2026-07-28 | Resource-server checks (RFC 9728, RFC 8707, RFC 9207), no token passthrough, Origin validation, SSRF, confused deputy, scope minimisation: `docs/rfcs/RFC-0004-protocols.md`, `docs/protocol-catalog.md` |
| A2A specification: authentication, push-notification security (§7, §13.2) | 1.0 (1.0.1 latest patch). Read 2026-11-11 | a2a-protocol.org/latest/specification | Per-request authentication, webhook URL validation, callback credentials, idempotent handling of duplicates |
| AG-UI specification | 1.0 (1.1 draft not used). Read 2026-11-11 | docs.ag-ui.com/spec/1.0 | Defines no authentication: the app's own session and checks apply. No stream resume, so reconnects can't repeat work |
| Keycloak | 26.4.2, the image used | quay.io | `scripts/oidc_check.ps1` |

**Excluded for now, with reasons:** ASVS levels above what a local demo can show (TLS, HSTS and deployment headers wait for Milestone 12). SOC 2 and ISO controls: organizational, and out of a simulation's reach.
