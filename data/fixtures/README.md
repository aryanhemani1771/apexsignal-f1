# Fixtures

Small, **deterministic, synthetic** data used by CI, unit tests, and offline demos. This is
**not** real Formula 1 data — driver/constructor/circuit names here are invented
placeholders so the fixtures carry no third-party data or licensing concerns.

- `demo_race/events.json` — a handful of domain events (a "Demo Grand Prix") that validate
  against `apexsignal.domain.events.DomainEvent`. Phase 1 replaces the real-race replay
  path with normalized FastF1 data; this synthetic bundle keeps the fixture demo running
  with zero credentials in the meantime.

Real historical race bundles land in Phase 1 (see `ROADMAP.md`) and will be sourced via
FastF1 with full provenance timestamps.
