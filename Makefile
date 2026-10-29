# Each target has a PowerShell equivalent in scripts\ (make is often missing on Windows).
# Targets still to come: eval, benchmark (Appendix B).

PROFILE ?= portfolio
SEED ?= 20261102
SCALE ?= 1.0

.PHONY: install test lint typecheck preflight leaks scores data data-reset data-clean data-verify discovery dictionary up down migrate seed reset-demo clean logs test-integration compose-check contract

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

# Local stack (Milestone 4). Uses .env; `make preflight` checks it first. Equivalent: scripts\stack.ps1 -Action <x>.
up:
	@test -f seed_data/v1/members.jsonl || uv run python -m seed_data.generator generate
	docker compose up --build -d --wait

down:
	docker compose down

migrate:
	docker compose exec -T app alembic upgrade head

seed:
	docker compose exec -T app python -m app.seed --dataset demo

reset-demo:
	docker compose exec -T app python -m app.seed --dataset demo --reset

clean:
	docker compose down -v --remove-orphans

logs:
	docker compose logs --tail 100

# Real-Postgres tests need TEST_MOCK_API_DATABASE_URL (the compose check sets it on a throwaway stack).
test-integration:
	uv run pytest -m postgres -q

compose-check:
	powershell -ExecutionPolicy Bypass -File scripts/compose_check.ps1

contract:
	uv run python -m mock_customer_api.contract --check
