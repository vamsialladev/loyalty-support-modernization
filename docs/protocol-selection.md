# Protocol selection (PROTO-01)

> Simulated engagement, synthetic data. Design in `docs/rfcs/RFC-0004-protocols.md`.

**Start from the problem, not the protocol.** The core workflow needs none of these: staff use the console, the app
calls the loyalty platform and PMS over REST (ADR-0022), and one bounded AI loop does the reading (ADR-0025). A
protocol earns a place only when a caller outside our code needs a standard way in.

| Need | Who has it | Protocol | When plain REST is enough |
|---|---|---|---|
| An AI assistant (Claude Code, an IDE, a customer's own agent) looks up a member, stay, ledger or policy while helping staff | Support leads, developers, the client's AI team | **MCP**, read-only | One known client we control: call the JSON API with a machine token. MCP pays off when several AI clients would each need a custom integration |
| A separate team's agent owns reservation evidence, and our coordinator delegates to it | The PMS / reservations team at a real hotel group | **A2A** | The "specialist" is just a service with one query: a REST call with a timeout does the same job with less code (`docs/a2a-vs-rest.md`) |
| A frontend shows an investigation as it runs (steps, tools, state), not just the result | Agents and supervisors in the console | **AG-UI** | The page only needs the finished result: the console already shows it. AG-UI is for live progress and for frontends we don't write |

**Not chosen for the core, and why:** A2UI and MCP Apps (UI generated or embedded by an agent: Milestone 16, a lab,
because staff screens must stay fixed and reviewable); the three ACPs, ANP, commerce and payment protocols (no loyalty
need; Milestone 16 labs). **A loyalty points adjustment is never a payment**, so no payment protocol touches it.

## Rules we apply (spec G.1, G.2)

- **No universal adapter.** Each protocol keeps its own auth model, errors and lifecycle.
- **Never call a REST endpoint protocol-compliant.** Only code that implements the pinned spec, and is tested against
  a tool we didn't write, is described as speaking that protocol.
- **Don't force protocols into the core.** With every flag off, the app behaves as it did at Milestone 10.
- **Pin released versions, not drafts.** AG-UI 1.1 is a draft: we use 1.0.

## What a new engineer should take from this

The senior question isn't "which protocol is newest?" but "who is the caller, and what breaks if we just give them a
REST endpoint?" Here the honest answer is: for one internal client, nothing breaks. The protocols are built because
the client's roadmap names other AI clients and another team's agent, and because the engagement must show how to do
them safely when that day comes. If that roadmap changed, MCP and A2A would be the first things to switch off.
