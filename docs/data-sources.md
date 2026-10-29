# Data sources

> PURP-08. Synthetic data is the default for every demo and evaluation. Any other source must pass the checklist
> below **before** it is used, and is always labelled as an optional, separate source.

## Sources in use

| Source | Kind | Licence | Personal data | Used for | Status |
|---|---|---|---|---|---|
| This repository's generator (`seed_data/generator/`, from M3) | Synthetic, deterministic | MIT (this repo) | None: names, emails and phones are invented (`example.com`, `.test`, 555 numbers) | Everything | Default |
| Guest Rewards program text from stages 1–2 | Fictional policy text, same author | MIT | None | Policy documents | In use |

No public dataset is used.

## Checklist before adding a public dataset
1. Official source and version recorded, with a link.
2. Licence and terms read and recorded: commercial use allowed? redistribution allowed? attribution required?
3. Confirmed to contain **no personal data** (and no data that could re-identify people).
4. Credit added here and wherever results using it are shown.
5. Added as a separate, clearly labelled source (its own directory and manifest), never mixed into the synthetic
   default; demos and evaluations keep using synthetic data unless a report says otherwise.
6. Recorded as an ADR (why it adds value over synthetic data).
