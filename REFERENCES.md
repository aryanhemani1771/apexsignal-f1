# REFERENCES

External projects and APIs used or inspected. Inspect each project's license **before**
borrowing any code; record anything actually reused in `THIRD_PARTY_NOTICES.md`.
Our original contribution is the pricing, structured-news, calibration, and
risk-allocation system — we do not fork-and-rename any project.

## Data dependency (used directly)
- **theOehrly/Fast-F1** (MIT) — authoritative historical F1 adapter: schedules, results,
  lap/sector timing, telemetry, tyres, weather, session data. Used as a dependency; we do
  not copy its internals.
- **OpenF1** (openf1.org) — historical REST from 2023+ needs no auth; real-time requires a
  subscription. Never made mandatory.

## Inspected for architecture / patterns only
- **f1stuff/f1-live-data** — FastF1 live-timing ingestion, recorded-session replay,
  race-control messages, Docker/streaming patterns. We use DuckDB/Parquet + Streamlit
  instead of its InfluxDB/Grafana stack.
- **Nicxe/f1_sensor** (MIT) — race-control messages, flags, incident/session-state
  handling. Concepts re-expressed as original domain models.
- **harningle/fia-doc** — FIA PDF → structured data (classifications, penalties, pit/tyre).
  **License not clearly stated on the repo — treat as reference only until verified.**
- **flairNLP/fundus** (MIT) — permitted news article extraction/metadata. Only for
  publishers whose terms allow crawling; prefer FIA/team RSS + document endpoints.
- **mehmetkahya0/f1-race-prediction** — simulator *organization* only. Do **not** reuse its
  synthetic ratings, manually assigned parameters, or performance claims.

## Market APIs
- **Kalshi** — official starter (`Kalshi/kalshi-starter-code-python`) for auth patterns;
  treat the REST OpenAPI + WebSocket AsyncAPI specs as source of truth (SDKs may lag).
  Public market data + **demo** execution only; no real-money execution.
- **Polymarket/py-sdk** (MIT, beta) — public/read-only market info only. Docs list the US
  as blocked → keep read-only, support an optional geo-availability check, never bypass.

## Verification notes
- Timestamps/licenses above reflect the build spec's research summary; re-verify current
  license text and API docs when first integrating each (record in `THIRD_PARTY_NOTICES.md`).
