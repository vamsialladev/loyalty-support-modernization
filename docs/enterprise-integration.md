# Enterprise integration

Spec E4, E7; ENT-13, ENT-14, ENT-16, ENT-28, ENT-29, ENT-30; ADR-0086. **Documentation only.** No integration with
any named product has been built or tested, and no vendor sandbox was used. Product names are examples of the
kinds of systems a customer has, not systems this project connects to. All data is synthetic.

## Systems of record (ENT-28)
The app reads and writes through ports (`app/ports/customer_systems.py`), and the customer's systems sit behind
adapters. Today one adapter serves the mock customer API (`app/adapters/mock_customer_api.py`). A real customer's
systems would map like this:

| Port operation | Typical system of record | Examples | Notes for the adapter |
|---|---|---|---|
| Find and read a member, read the points ledger, post an adjustment | Loyalty platform | the program's own platform, or a vendor loyalty suite | Adjustments need an idempotency key the platform honours, or a status lookup by key (`docs/real-system-swap-guide.md`) |
| Read stay records and booking channel | Property management or reservation system | a PMS or central reservation system | Often batch exports; the evidence age check (`max_evidence_age_minutes`) decides how fresh is fresh enough |
| Intake of the member's request, notes back to the member | CRM or case management | Salesforce Service Cloud, ServiceNow, Zendesk | The case reference and status map to the CRM's ticket; the member's message stays in the CRM |
| Reporting | Data warehouse | the customer's warehouse | Fed by the analytics export (`python -m app.services.analytics_export`), counts only |

The field mapping per customer lives in `config/customers/<id>.yaml` (`field_mapping`, `value_maps`).

## Embedding in the agent's existing tool (ENT-29)
| Option | How | Gains | Costs |
|---|---|---|---|
| The console as it is | Agents open this console beside the CRM | Built and tested; full control of the approval UI | Two screens; agents copy references between them |
| A side panel in the CRM | The CRM shows the recommendation, evidence and approval status through the JSON API (`/api/v1`, published contract) | Agents stay in their tool; the API already enforces the same permissions | Each CRM's panel framework; sign-in through the CRM's identity provider (OIDC is already supported) |
| Notes written back | The app posts its result as a note on the CRM ticket | The smallest change for agents | Approvals still need the console: a note can't carry the binding of an approval (ADR-0059) |

**Recommended first:** the side panel, read-only at first, with approvals staying in the console until the CRM can
show the approval binding.

## Event-driven triggers (ENT-30)
| Option | How | Gains | Costs |
|---|---|---|---|
| Polling (today's pattern for intake from files and the API) | A job asks the CRM for new tickets every few minutes | Simple; no inbound network path | Delay up to the interval; load on the CRM |
| A signed webhook | The CRM calls an intake endpoint when a ticket is created; the app checks an HMAC signature and a timestamp, then queues the case | Seconds, not minutes; no polling load | A public endpoint to protect; replay protection; the CRM must support it |
| Change data capture | The CRM's change feed or event bus delivers ticket events | Ordered, durable | Platform-specific; more infrastructure |

**Not built:** the signed webhook on the mock API was optional ("if time allows") and wasn't done in Milestone 12.
**A webhook would also need intake idempotency, which doesn't exist yet:** `case_requests.request_ref` isn't unique,
so a repeated event would create a second case. A unique index on the CRM's event or ticket ID, with "already
received" as the answer, comes first.

## AI gateway pattern (ENT-16)
A customer with several AI applications often routes model calls through one internal gateway that holds the keys,
enforces spend limits, logs usage and applies content policies. This system fits behind one without changes to the
loop: the model port (`app/ports/model_provider.py`) takes one adapter per provider, so a gateway is one more
adapter. This system already does, inside itself, what a gateway centralizes: the allowed-model list, retirement
tracking, per-run, daily and monthly caps, redaction before the call, GenAI telemetry without content, and a circuit
breaker. With a gateway, the caps here stay as a second line, and the gateway's limit is the first.

## Provider contract checklist (ENT-14)
Before real data reaches any model provider, a customer's review answers each of these from the provider's current
terms. **None has been answered for a real customer here.**

- [ ] Data processing agreement signed; the sub-processor list read
- [ ] Retention of inputs and outputs: how long, and whether "zero retention" is available for this use
- [ ] Whether inputs are used for training (and how that's turned off, in writing)
- [ ] Processing regions, and whether a region can be required (Bedrock in a chosen region is the path here)
- [ ] Security certifications the customer requires (for example SOC 2 Type II, ISO 27001), with report dates
- [ ] Incident notification time and contact
- [ ] Model deprecation notice period (this system tracks `retires_on`, `app/ai/lifecycle.py`)
- [ ] Rate limits and the support tier for production
- [ ] Price list and how changes are announced (prices in `config/ai/` carry a `checked_on` date)
- [ ] Acceptable-use terms that touch this use (decisions about members' points, with a person approving)

## Claude via Amazon Bedrock (ENT-13): configured only, blocked
`AI_PROVIDER=bedrock` is a recognized setting, and preflight checks `AWS_PROFILE`, `AWS_REGION` and
`BEDROCK_MODEL_ID` (profile "Claude via Amazon Bedrock (configure only)"). The app reports it as configured only, and
investigations fall back to arm B's result. No Bedrock adapter is built or tested, because this project has no AWS
access. That access is the unblocking step, with the owner's approval and a budget.
