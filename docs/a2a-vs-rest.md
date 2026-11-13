# A2A or a plain REST call? (PROTO-04, spec G.4)

> Simulated engagement, synthetic data. Code: `protocols/a2a/`. Design: RFC-0004, ADR-0025, ADR-0071.

The same evidence (one member's stays and queued postings) can reach the loyalty side two ways in this repo:

| | REST adapter (`app/adapters/mock_customer_api.py`) | A2A (`protocols/a2a/`) |
|---|---|---|
| Who owns the other side | The PMS's API, called directly by our code | Another team's agent, which decides how to read its own system |
| How we find it | A configured base URL and an OpenAPI contract (`openapi-v1.json`) | A configured URL, then its Agent Card (capabilities, auth scheme). The card is checked, not trusted |
| Auth | Our service token for the mock API | An OAuth token whose audience is the specialist; per-task check of the customer on its side |
| Shape of the answer | Typed records, mapped by `customer_shapes/` | One data artifact with provenance and a content hash, checked by schema |
| Long work | Not needed: reads take milliseconds | Task states, `GetTask`, `CancelTask`, push notifications |
| Failure handling | Typed errors (`RecordNotFound`, `UpstreamTimeout`), retries in the worker | Task states: `failed`, `rejected`, `canceled`; our side adds `timed_out`, `peer_unavailable`, `invalid_card`, `invalid_artifact` |
| Code on our side | ~1 adapter method per read | Coordinator, specialist, a table, a migration, callbacks |
| Tests here | `tests/test_mock_api.py` and the arm tests | `tests/test_a2a.py`, `tests/test_a2a_postgres.py` |

## When REST is enough (this case, today)

The specialist does one read with no judgment in it. The reservations data has an API. So a REST call with a timeout
gives the same evidence with a fraction of the moving parts, and that's what arms B and C use. **A2A here is a lab:
built to show how it's done safely, not because this workflow needs it.**

## When A2A would earn its place

- The other side is an **agent another team runs and changes on its own schedule**, and you want to talk to what it
  can do (its card), not to its internals.
- The work is **long or needs judgment** (finding a stay across several systems, asking a property for a folio), so
  task states, cancellation and notifications matter.
- **Several teams' agents** would otherwise each need a custom integration.

## What stays the same either way

Evidence from anywhere is data for a person to review. The rules engine decides eligibility and points, a supervisor
approves, and the write path executes. A2A never reaches any of those.

## What a new engineer should take from this

Ask "what does the protocol buy us that a timeout and a typed error don't?" before building it. Here, the honest
answer is "nothing yet", and the doc says so. The lab exists so that when the answer changes (another team's agent,
long-running work), the safe version is already designed, tested and reviewed.
