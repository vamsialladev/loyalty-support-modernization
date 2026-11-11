# Protocol adoption evidence (PROTO-01)

> Read 2026-11-11. Spec G.1: keep vendor support, announced partnerships and documented production deployments
> apart, and don't claim wide adoption without evidence. **We found no documented production deployment for any of the
> three during this reading, and didn't look for one exhaustively.** That isn't evidence there are none.

| Protocol | Vendor support we saw on primary pages | Announced partnerships | Documented production deployments |
|---|---|---|---|
| MCP | Official SDKs in several languages (Python `mcp` 2.3.0 read today); the MCP Inspector (2.14.0, released 4 Nov) | Not assessed | None read |
| A2A | Official Python SDK `a2a-sdk` 1.3.0; TCK and a2a-inspector repositories under `a2aproject` | Not assessed | None read |
| AG-UI | Python `ag-ui-protocol` 1.0.0, maintained by CopilotKit; JS packages released 2026-11-05 and later; Pydantic AI has an AG-UI integration (its own docs) | Not assessed | None read |

**What this tells a sponsor:** these are real, maintained, released specifications with official SDKs. It doesn't tell
us how many companies run them in production, so the business case never leans on "industry standard".

Within this portfolio: stage 7 (`hotel-tools-mcp`) serves MCP publicly (read-only, on Vercel); `agent-protocols-lab`
demoed ten protocols on 2026-10-27. Those are our own projects, not adoption evidence.
