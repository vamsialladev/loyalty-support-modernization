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
| Data generation | $0 | $0 | $0 | Local, deterministic, no external service |

## Sensitivity (to fill)
The inputs most likely to move TCO: request volume, model price per token, supervisor time per approval, and the
number of customers (per-customer deployments add hosting and operations cost).
