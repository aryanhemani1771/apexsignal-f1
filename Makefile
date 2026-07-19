.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help setup lock sync fmt lint type test test-fast cov security audit check ci fixtures replay dashboard api clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Create the venv and install core + dev deps (Phase 0 baseline)
	uv sync --dev

lock: ## Refresh uv.lock
	uv lock

sync: ## Install locked deps
	uv sync --dev

fmt: ## Auto-format
	uv run ruff format .
	uv run ruff check --fix .

lint: ## Lint (no changes)
	uv run ruff check .
	uv run ruff format --check .

type: ## Type-check src
	uv run mypy src

test: ## Run the full test suite
	uv run pytest

test-fast: ## Run tests, skipping slow/integration
	uv run pytest -m "not slow and not integration"

cov: ## Run tests with coverage
	uv run pytest --cov --cov-report=term-missing

security: ## Static security scan
	uv run bandit -q -r src

audit: ## Dependency vulnerability audit
	uv run pip-audit || true

check: lint type test ## Full local gate (lint + type + test)

ci: lint type test security ## What CI runs (minus docker build)

fixtures: ## (Phase 1) regenerate deterministic fixture bundle
	uv run python scripts/generate_demo_assets.py

replay: ## (Phase 1) replay a bundled historical race in the terminal
	uv run python scripts/replay_race.py

dashboard: ## (Phase 1+) launch the Streamlit dashboard
	uv run streamlit run dashboard/app.py

api: ## (Phase 5+) launch the FastAPI service
	uv run uvicorn apexsignal.api.main:app --reload

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage dist build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
