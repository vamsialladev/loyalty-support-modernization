# AI engineering matrix (spec B.9; AI-01)

**SYNTHETIC.** These labels are a learning structure, not a standard taxonomy. **No result in this table comes from a real model:** the tests use a mock or a scripted model, so they
show what the harness does, not how good a model is. Measured results arrive with the owner-approved live run and Milestone 10.

| Discipline | Problem it solves | Where | Try this | Tests | Trade-offs and limits |
|---|---|---|---|---|---|
| Prompt | The model must know its job, and that a member's text isn't an instruction | `config/prompts/arm_c_v1.md` | Change one rule and watch `tests/test_ai_tools.py` hold the version: a change needs a new version | `test_ai_tools.py` prompt tests, `test_prompt_versioning.py` | A regression suite on held-out cases needs a live model: Milestone 10. Never chosen from a few demos |
| Context | The model should see only what this task needs, with its source and age | `app/ai/context.py` | Paste an email address into a request and read the context the model gets | `test_ai_tools.py` context tests | No compaction: runs are short. Dropped history is stated, not hidden |
| Tool | A model with broad tools is a security hole | `app/ai/tools.py` | Ask `get_stay` for another member's stay in a test | `test_ai_tools.py`, `test_arm_c.py::test_a_model_cant_reach_another_members_stay` | Five narrow tools mean more turns than one broad one |
| Agent | Reading a vague message needs judgment that rules can't give | `app/services/assisted.py` | Run D16 on arm B, then arm C | `test_arm_c.py` | One loop, no sub-agents. It's only used where rules can't work |
| Loop | An unbounded loop spends money and can't be reasoned about | `app/ai/loop.py` | Lower `max_turns` in `config/ai/hg-demo.yaml` and rerun | `test_ai_loop.py`: each stop condition | Limits are starting points until Milestone 12 |
| Workflow / graph | Decisions must happen in a fixed order, whatever a model does | Arm B's investigation, then the loop, then the engine again; the write path after approval | Follow one case's `case_events` | `test_arm_c.py`, `test_execution_postgres.py` | No graph library: a state machine and a job are enough |
| Retrieval | The model needs the right policy words, from the right version | `conventional.search_policy` | Search "retro credit" on a stay from before and after 2026-07-01 | `test_arm_b_console.py`, `test_ai_tools.py` citation tests | Full-text plus synonyms. Embeddings aren't justified by any measurement so far |
| Memory / state | A model's memory can't be proof of anything | The database; `ai_runs`, `ai_steps`; nothing carried between runs | Run a case twice and compare `ai_runs` | `test_arm_c.py` state tests | No vector memory, because no evaluated need exists |
| Harness | Budgets, records and caps can't live in a prompt | `app/ai/harness.py` | Set a tiny cap, and watch a run stop before calling | `test_ai_provider.py` | A checkpoint can't give exactly-once effects. The loop has none, and credits use the write path |
| Evaluation | "It looks good" isn't evidence | `benchmarks/`, Milestone 10; `evaluations/routing_baseline.py` | Read `config/routing/thresholds.yaml`, then the Git log for when it was committed | `test_routing_baseline.py` | Not measured on a real model yet |
| Reliability / platform | Providers fail, and the case must not | The fallback in `assisted.py`; retries in `loop.py`, spend in `harness.py` | Make the scripted model raise `ProviderUnavailable` | `test_ai_loop.py`, `test_arm_c.py` fallback tests | No circuit breaker yet: a failed run ends quickly and the next one tries again. Milestone 12 decides |
| Human oversight and feedback | Reviewers rubber-stamp what looks finished | `templates/case_b.html`: evidence and the engine first, AI text labelled, overrides need reasons | Read a case page top to bottom | `test_arm_c.py::test_the_page_shows_evidence_and_the_engine_before_any_ai_text` | Automation bias is measured at Milestone 10, not assumed away |

## What's enforced by code, not by asking the model nicely

| Rule | Where |
|---|---|
| Action equals the engine's | `app/ai/validation.py` |
| No amount field; stated numbers must be the engine's | `Proposal` in `app/ai/tools.py`, `validation.py` |
| Citations must have been retrieved in this run | `validation.py` |
| Stays must have come from `get_stay` | `validation.py` |
| No percentages or confidence wording | `validation.py` |
| No tool outside the allowlist; the run stops at once | `loop.py` |
| No hidden reasoning requested or stored | `config/prompts/arm_c_v1.md`, `harness.py`, `ai_steps` |
| Spending caps survive a restart | `harness.py`, `ai_spend` |
