# Protocol learning labs (PROTO-01)

> Simulated engagement, synthetic data. Status groups from spec G.13.

| Group | Protocols | Milestone | Status |
|---|---|---|---|
| Core integrations | MCP, A2A, AG-UI | 11 | See `docs/protocol-test-results.md` |
| Interface extensions | A2UI, MCP Apps | 16 | Planned |
| Dev-tool exercises | **Agent Client Protocol** (editor ↔ coding agent) | 16 | Planned |
| Historical exercises | **Agent Communication Protocol** (IBM / BeeAI) | 16 | Planned |
| Experimental labs | ANP | 16 | Planned |
| Commerce and payment sandboxes | UCP, **Agentic Commerce Protocol**, AP2, x402, MPP | 16 | Planned |

## Try the core three yourself (after Milestone 11 merges)

Each runs on the mock, with no key and no account. Steps are in `docs/onboarding.md`; the short version:

1. MCP: start the server, point the MCP Inspector at it with a test token, list tools, call `get_member`, then try
   another customer's member and see "not found".
2. A2A: start the specialist and the coordinator, run one case, then stop the specialist and run it again: the
   coordinator reports the peer unavailable and the case is unchanged.
3. AG-UI: open a case's live-run panel, start an investigation, reload the page mid-run, and check the investigation
   ran once (one `ai_runs` row).

`agent-protocols-lab` has one small, standalone demo per protocol; use it to learn a protocol alone, and this repo to
see one connected to a real workflow's permissions and audit.
