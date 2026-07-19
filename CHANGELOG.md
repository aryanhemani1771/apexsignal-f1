# Changelog

All notable changes to ApexSignal F1. Format loosely follows Keep a Changelog.
Also serves as the agent development log (one entry per phase / work session).

## [Unreleased]

### Phase 1 — Historical F1 data & replay — 2026-07-19
**Objective:** a complete race can be replayed locally without external credentials.

Added:
- `domain/race_state.py` — `RaceState`/`DriverState` + deterministic reducer
  (`apply_event`) and `replay`/`replay_states`; replay is order-independent and produces a
  stable snapshot id.
- `storage/event_store.py` — append-only event store with JSONL load/save, deterministic
  iteration order.
- `ingestion/fixtures_adapter.py` — load bundled fixture bundles offline.
- `ingestion/fastf1_adapter.py` — real FastF1 → domain events (laps, positions, tyres, pit
  stops, weather, track status, race control); t0-anchored absolute timestamps; lazy import
  so the module stays importable without the `data` extra.
- `ingestion/normalization.py` — `run_quality_checks` with 8 integrity checks + report.
- `services/race_service.py` — replay/standings/timing-tower helpers shared by CLI + dashboard.
- `dashboard/app.py` + `dashboard/theme.py` — interactive replay page (fixture mode).
- Real `scripts/download_history.py` and `scripts/replay_race.py`.
- Tests: reducer determinism, event-store round-trip, 8 quality checks, race-service views,
  and a network-gated FastF1 integration test (skipped unless `RUN_FASTF1_TESTS=1`).

Verified:
- `make ci` green — 42 tests pass + 1 gated skip; ruff/mypy(strict)/bandit clean.
- **Real end-to-end on the 2023 Bahrain GP**: 1347 events, 0 data-quality errors, replayed
  podium **VER / PER / ALO** — matches the actual race result.

### Phase 0 — Repository & research — 2026-07-19
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
