# Changelog

All notable changes to ApexSignal F1. Format loosely follows Keep a Changelog.
Also serves as the agent development log (one entry per phase / work session).

## [Unreleased]

### Phase 0 — Repository & research (in progress) — 2026-07-19
**Objective:** repository boots and tests pass; documentation and tooling scaffold
that lets any agent (incl. Codex) resume the build phase-by-phase.

Added:
- Standalone `apexsignal-f1` repo, package structure under `src/apexsignal/`.
- `pyproject.toml` with `uv`, ruff, mypy (strict), pytest, coverage, bandit; phased
  optional-dependency groups (`data`/`models`/`api`/`dashboard`/`sim`).
- Tooling: `Makefile`, `.pre-commit-config.yaml`, `.gitignore`, `.env.example`.
- Containers: `Dockerfile`, `docker-compose.yml` (build not verified locally — no Docker on authoring machine).
- CI: `ci.yml`, `security.yml`, `refresh_demo_data.yml`, `deploy.yml`.
- Docs: README, AGENTS, CLAUDE, ROADMAP, DECISIONS, MODEL_CARD, RISK_DISCLOSURE,
  DATA_DICTIONARY, THIRD_PARTY_NOTICES, REFERENCES, `docs/BUILD_SPEC.md`.
- Configs: `base`, `development`, `portfolio_demo`, `risk_limits`, `news_sources`, `event_impact_priors`.
- Core code: `settings.py` (env validation + safety guards), `logging.py` (structlog + secret redaction),
  domain models `provenance.py` and `events.py`.
- Tests: settings validation, domain-event invariants, and a point-in-time leakage guard.
- Deterministic fixture bundle under `data/fixtures/`.

Notes:
- No fabricated metrics anywhere. No model results claimed yet.
