# Each target has a PowerShell equivalent in scripts\ (make is often missing on Windows).
# Targets added as milestones reach them: up, migrate, seed, reset-demo, eval, benchmark, down, clean (Appendix B).

PROFILE ?= portfolio
SEED ?= 20261102
SCALE ?= 1.0

.PHONY: install test lint typecheck preflight leaks scores data data-reset data-clean data-verify discovery dictionary

install:
	uv sync

test: lint typecheck
	uv run pytest --cov --cov-report=term-missing

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

preflight:
	uv run python -m app.preflight --profile $(PROFILE)

leaks:
	uv run python -m app.env_leaks

scores:
	uv run python scripts/matrix_scores.py

# Synthetic data (spec B.5): generate, reset (clean + generate), clean (seed_data/v1 only), verify against the manifest.
data:
	uv run python -m seed_data.generator generate --seed $(SEED) --scale $(SCALE)

data-reset: data-clean data

data-clean:
	uv run python -m seed_data.generator clean

data-verify:
	uv run python -m seed_data.generator verify --seed $(SEED) --scale $(SCALE)

discovery:
	uv run python -m evaluations.discovery_analysis

dictionary:
	uv run python -m seed_data.generator dictionary
