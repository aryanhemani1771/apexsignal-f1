# data/

- `fixtures/` — **small, deterministic, committed** data bundles used by CI, unit tests,
  offline demos, and the public portfolio demo. Must load without any credentials.
- `sample/` — slightly larger illustrative samples (optional, still committed).
- `raw/` — **git-ignored** working area for downloaded FastF1/OpenF1 data. Never commit raw
  external data.

Provenance rule: every record keeps `event_time` / `first_seen_at` / `ingested_at` (and
`published_at` / `effective_at` where relevant). Backtests use `first_seen_at` for
availability. See `../DATA_DICTIONARY.md`.
