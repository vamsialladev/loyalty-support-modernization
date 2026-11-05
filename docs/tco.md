# Total cost of ownership (1–3 years)

> **Early draft, estimates under stated assumptions; nothing here is measured** (PURP-04). Filled in as costs are
> measured: model cost per case in M10, hosting in M12, support effort in M18. Shown as pessimistic / base /
> optimistic once there are inputs to vary.

## Cost components

| Component | Year 1 | Year 2 | Year 3 | Source of the number |
|---|---|---|---|---|
| Model / API usage | not measured yet | — | — | M10 live runs × assumed volume (A1) |
| Hosting (app, worker, mock API, Postgres) | not measured yet | — | — | M12 hosting options (official pricing) |
| Engineering build | assumption, set in M10 | — | — | Hours × rate, both assumptions |
| Support and maintenance | assumption, set in M18 | — | — | Runbooks and maintenance schedule |
| Evaluation re-runs (regression before releases) | not measured yet | — | — | M10 cost per run |
| Worker process (added in Milestone 6) | not measured yet | — | — | One more container beside the app; no new paid service. Priced with hosting in M12 |
| Upstream calls for re-checks (added in Milestone 6) | not measured yet | — | — | About 4 more reads at approve and at execute. Free on the mock; a real vendor's API terms may charge or limit them |
| Data generation | $0 | $0 | $0 | Local, deterministic, no external service |

## Sensitivity (to fill)
The inputs most likely to move TCO: request volume, model price per token, supervisor time per approval, and the
number of customers (per-customer deployments add hosting and operations cost). From Milestone 6: the cost of a real
platform's API calls for re-checks, and the people cost of a re-approval each time evidence changes or 24 hours pass.
