# Release gate for prompt, model and AI changes

BENCH-13, ENT-15, ENT-21, ENT-22; ADR-0082. Mock provider only in this milestone: no key, no cost. All data is
synthetic.

## What the gate does
A pull request that touches anything that can change arm C's decisions re-runs the frozen mock regression: arm C on
the dev split (100 cases), compared case by case with the committed known-good run
`benchmarks/results/mock/c-mock-dev`. That covers the prompts, the AI config, the AI code, the model adapters,
policies and the eligibility rules. It fails on any difference in a decision field: outcome, points, approval,
execution, eligibility, stays, policies, duplicates, unauthorized actions, AI stop reasons, fallbacks. CI runs it as
the job "Release gate". On other pull requests it reports "not needed" in seconds.

```powershell
uv run python scripts/release_gate.py --base origin/main
uv run python scripts/release_gate.py --force
```

**Shown to catch a change:** with `max_turns` set from 6 to 1 it failed with 240 differences (every case stopped at
`max_steps` and fell back); with the code as committed it passed, 100 of 100 (verification log, Milestone 12, row 24).

## Known-good configuration, for rollback
`benchmarks/results/mock/c-mock-dev/manifest.json` names the commit, prompt version, model and limits of the run the
gate compares with. Rolling back an AI change means returning those files to that commit's version and confirming
the gate passes; the image rollback itself is in `docs/rollback.md`.

## Shadow before promotion (ENT-22)
A candidate prompt or model never reaches a case. It runs into its own results folder, and the gate compares:

```powershell
$env:AI_PROMPT = "arm_c_v2"   # a new file in config/prompts/, with its own version in the front matter
uv run python -m evaluations.run --arm c-mock --split dev --name shadow-arm-c-v2
Remove-Item Env:AI_PROMPT
uv run python scripts/release_gate.py --candidate benchmarks/results/mock/shadow-arm-c-v2
```

**Limit:** the mock provider decides by rules, not by reading the prompt, so a shadow run on the mock checks the
plumbing, not the prompt's quality. A meaningful prompt or model comparison needs live calls, which need the owner's
approval and a budget (none in Milestone 12). Routing a share of real investigations to a candidate is **Roadmap**,
and it needs the same.

## A change that's meant to change decisions
1. Run the gate; read every difference.
2. Run the ablation or live evaluation that justifies the change (with approval if live), and record it in an ADR.
3. Re-baseline with a reviewed commit: a new `benchmarks/results/mock/c-mock-dev` from
   `uv run python -m evaluations.run --arm c-mock --split dev --name c-mock-dev`, reviewed by a second person.

## Model lifecycle (ENT-15)
`uv run python -m app.ai.lifecycle` reviews every allowed model in `config/ai/<customer>.yaml`. It blocks a model
that's deprecated, retired or retiring within 60 days, and warns when the price and status check is more than 90
days old. No retirement date is ever guessed: an empty `retires_on` means none was published as of `checked_on`. The
harness refuses a model past its retirement date, the same as a deprecated or unlisted one (it fails safe to arm
B's result). The upgrade steps are in `docs/ai-system-card.md`.

## Feedback into the dataset (ENT-21)
`uv run python -m evaluations.feedback_candidates --collect` turns QA reviews (`wrong`, `unsure`, `misleading`) and
"not helpful" feedback into a review sheet with codes only. A person fills in the label, their name and
`decision=add`. Only then does `--promote <sheet>` append the row, to the input for the **next** dataset version. It
never edits the frozen v1 dataset or its labels, and never runs on its own.
