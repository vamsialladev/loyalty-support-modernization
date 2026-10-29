# Scaling and limits

> **Early draft** (PURP-04). All figures are **estimates** until a load test or a run measures them. Sections are
> added as components exist: data volume (M3), queue and database (M6, M12), model cost (M8, M10), team size.

## Assumed baseline
About 320 missing-points requests a month for two properties (assumption A1), 6 agents and 2 supervisors (A5).

| Dimension | 1× (baseline) | 10× | 100× | First thing that breaks (estimate) | Planned response |
|---|---|---|---|---|---|
| Requests | ~320/month | ~3,200/month | ~32,000/month | Supervisor approval capacity, before any software limit | Approval limits by amount and risk; batch review for low-value adjustments (policy decision for the sponsor) |
| Model cost | not measured yet | — | — | — | Measured in M10; routing to a cheaper model only if the benchmark shows no quality loss |
| Queue and database | — | — | — | — | Measured in M12 |
| Team size | 1 engineer | — | — | — | Onboarding doc and starter kit so new engineers can contribute in a day |
