# AGENTS.md — Operating manual for coding agents

This is the canonical operating manual for **any** agent working on ApexSignal F1
(Codex reads `AGENTS.md`; Claude Code / Fable read `CLAUDE.md`, which points here).
The full build specification the project is derived from is preserved in
`docs/BUILD_SPEC.md`. Progress lives in `ROADMAP.md`; rationale in `DECISIONS.md`.

## What this project is
A news-aware, event-driven Formula 1 prediction-market **pricing and paper-trading
research platform**. It reconstructs point-in-time race state, produces calibrated
probabilities for F1 contracts, compares them to public market prices, and generates
correlation-aware **simulated** allocations. It is a research/paper-trading system —
**not** a live-money trading bot and **not** a toy winner-predictor.

## Start-of-session checklist
1. Read `ROADMAP.md` → `DECISIONS.md` → this file.
2. Find the first unchecked box in the lowest incomplete phase.
3. State the phase objective in `CHANGELOG.md` (dev log).
4. Implement the **smallest end-to-end vertical slice**, with its acceptance test.
5. `make check` (lint + type + test). Fix failures.
6. Update `ROADMAP.md` checkboxes + "Current status", `DECISIONS.md` if you made a call, `CHANGELOG.md`.
7. Commit logically grouped changes with a clear message.

## Non-negotiable rules (safety & integrity)
- **No live money.** `ENABLE_LIVE_TRADING=false` and `EXECUTION_MODE=paper` are the
  defaults and are enforced in `settings.py`. Real-money execution is never
  implemented on the default branch; the guarded path raises `LiveTradingDisabledError`.
- **No evasion.** No geo-restriction bypass, VPN/proxy handling, account automation,
  or CAPTCHA solving. **Polymarket is read-only.**
- **No fabricated results.** Never invent backtest numbers, Brier scores, P&L,
  latency, race counts, calibration, or market availability. Until something is
  actually measured, display/write `Not yet evaluated` (or `NOT verified`). The README
  and `ROADMAP.md` must separate implemented / experimental / planned / validated.
- **No data leakage.** Every observation carries `event_time`, `first_seen_at`,
  `ingested_at` (and `published_at`/`effective_at` where relevant). Backtests use
  `first_seen_at` for availability. Leakage tests must stay green.
- **No unlicensed assets.** Original branding only; no F1/FIA/team/exchange logos
  unless licensing permits. Inspect the license of any repo before borrowing code and
  record it in `THIRD_PARTY_NOTICES.md`.
- **Never label allocations** "guaranteed / safe / locks / risk-free". Use
  **"Model-ranked simulated allocation"**. The engine may return **"No qualifying
  opportunity."**

## Engineering conventions
- Python 3.12, `uv` for env/deps. Core deps minimal; heavy stacks are optional-dep
  extras (`data`, `models`, `api`, `dashboard`, `sim`) added in the phase that needs them.
- Pydantic v2 for domain models & settings. Polars for dataframes (Pandas only where
  FastF1 forces it). DuckDB/Parquet for storage. `structlog` for logging (never log secrets).
- Production logic lives in `src/apexsignal/`, never in notebooks.
- No placeholder logic on the principal execution path. A stub is allowed only when it
  (a) is blocked on a missing credential, (b) has a working fixture fallback, (c) has a
  complete interface + tests, and (d) is documented as a stub. Mark such items `[~]`.
- Determinism: seeded RNG in tests; replay must be reproducible.

## Escalate to the user ONLY for
1. Credentials that cannot be mocked. 2. Accepting third-party terms.
3. Deployment authorization. 4. A genuinely irreversible operation.
Missing credentials must never block the local fixture demo.

## Commands
`make setup` · `make check` · `make ci` · `make test` · `make fmt` · `make replay` (Phase 1+) · `make dashboard` (Phase 1+).
