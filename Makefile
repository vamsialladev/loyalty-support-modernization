# Each target has a PowerShell equivalent in scripts\ (make is often missing on Windows).
# Targets added as milestones reach them: up, migrate, seed, reset-demo, eval, benchmark, down, clean (Appendix B).

PROFILE ?= portfolio

.PHONY: install test lint typecheck preflight leaks scores

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
