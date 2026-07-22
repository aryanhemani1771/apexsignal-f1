# Fixtures

Small, **deterministic, synthetic** data used by CI, unit tests, and offline demos. This is
**not** real Formula 1 data — driver/constructor/circuit names here are invented
placeholders so the fixtures carry no third-party data or licensing concerns.

- `demo_race/events.json` — a handful of domain events (a "Demo Grand Prix") that validate
  against `apexsignal.domain.events.DomainEvent`. Phase 1 replaces the real-race replay
  path with normalized FastF1 data; this synthetic bundle keeps the fixture demo running
  with zero credentials in the meantime.

- `real_race/events.jsonl` — a **real** race: the **2023 Bahrain Grand Prix**, normalized from
  FastF1 timing data (factual historical F1 data). Real driver codes (VER, PER, HAM, …) and real
  events (laps, positions, safety car, pit stops). Used by the dashboard so the demo shows real
  drivers and a real race rather than synthetic placeholders. Sourced via FastF1 (MIT); this is
  public factual timing data used for research/education.
