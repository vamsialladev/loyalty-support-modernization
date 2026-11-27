# Public datasets

> Only public data the owner approved, used for measurement. No dataset text is committed, cached, logged or shown in
> the demo: only counts and field names. Stage 9's own cases stay SYNTHETIC (`benchmarks/datasets/v1`).

## MultiWOZ 2.2, test split (approved by the owner, 2026-11-26, Milestone 13)

| Field | Value |
|---|---|
| What it is | Multi-domain hotel, restaurant, train and other dialogues. "Human-human written conversations": crowd workers played a visitor and a clerk (Wizard-of-Oz). Version 2.2 adds corrected annotations in the schema-guided format |
| Source | https://github.com/budzianowski/multiwoz, `data/MultiWOZ_2.2/test/` |
| Version pinned | commit `fe0c8e65cfcd8462bd33c86e35f21addc84ca82b` (2025-01-14, the default branch `master` when read on 2026-11-26) |
| Files used | `dialogues_001.json` (11,781,808 bytes) and `dialogues_002.json` (10,771,758 bytes), 1,000 dialogues. Train and dev splits not downloaded |
| SHA-256 | `dialogues_001.json`: `d6f43876cf130fdb2dfa8f96bc056b0995354137f02122e004925d01264ed386`; `dialogues_002.json`: `89af95d8f596a448e733d59b31be78f1dd1632eddd99d5cb298a3fcb1ac9d185` (checked by the script) |
| Licence | **The sources disagree.** The repository's `LICENSE` is MIT ("Copyright (c) 2019 Paweł Budzianowski"), and its README says the toolkit is released under it. The Hugging Face mirror card (`pfb30/multi_woz_v22`) says "The dataset is released under the Apache License 2.0". The 2.2 data folder's README names none. Both are permissive and allow use, analysis and redistribution with attribution, so measuring with it is allowed either way. We keep both notices here, cite the papers, and redistribute nothing |
| Terms we follow | Attribution (below); no data in the repository; no utterances in reports; not used to train anything |
| Personal data | None real: the people are role-playing, and booking references are invented. We still store no utterance |
| Citation | Budzianowski et al., "MultiWOZ: A Large-Scale Multi-Domain Wizard-of-Oz Dataset for Task-Oriented Dialogue Modelling", EMNLP 2018. Zang et al., "MultiWOZ 2.2: A Dialogue Dataset with Additional Annotation Corrections and State Tracking Baselines", NLP4ConvAI workshop at ACL 2020, pp. 109–117 |
| Read on | 2026-11-26: the GitHub README, `LICENSE`, the 2.2 README, the GitHub API (licence field, commit, file sizes), the Hugging Face card and API, the two ACL Anthology pages (their CC BY 4.0 footer covers the papers, not the data) |

### Download and run (Windows)
Into an empty folder outside the repository (the data stays out of git):

```powershell
New-Item -ItemType Directory -Force $env:TEMP\multiwoz22-test
```

```powershell
foreach ($f in "dialogues_001.json","dialogues_002.json") { Invoke-WebRequest -Uri "https://raw.githubusercontent.com/budzianowski/multiwoz/fe0c8e65cfcd8462bd33c86e35f21addc84ca82b/data/MultiWOZ_2.2/test/$f" -OutFile "$env:TEMP\multiwoz22-test\$f" }
```

```powershell
uv run python -I evaluations/m13_multiwoz.py --data $env:TEMP\multiwoz22-test
```

The script refuses files whose SHA-256 differs from the pinned ones, and writes
`benchmarks/reports/m13/multiwoz-questions.json`.

### What it was used for
Milestone 13: how often real hotel messages ask a general question an answer cache could serve
(`docs/m13-baseline.md` §2b). Label on every result: **"Real public conversation data (MultiWOZ 2.2; licence MIT
per the repository, Apache-2.0 per the Hugging Face card). No model used."**
