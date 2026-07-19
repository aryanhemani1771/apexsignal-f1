# CLAUDE.md

The canonical operating manual for agents on this project is **[AGENTS.md](AGENTS.md)** —
read it in full. It applies identically to Claude Code, Codex, and Fable.

Then, every session, read in order:
1. [ROADMAP.md](ROADMAP.md) — build progress & the next unchecked task (source of truth).
2. [DECISIONS.md](DECISIONS.md) — why the architecture is the way it is.
3. [AGENTS.md](AGENTS.md) — rules, conventions, and the start-of-session checklist.

The full original build specification is preserved verbatim in
[docs/BUILD_SPEC.md](docs/BUILD_SPEC.md).

## The five rules you must never break
1. No live-money trading; paper/demo only. Polymarket read-only. No evasion of platform/geo controls.
2. No fabricated metrics — write `Not yet evaluated` until something is truly measured.
3. No data leakage — respect `first_seen_at`; keep leakage tests green.
4. No unlicensed logos/assets/code; record borrowings in `THIRD_PARTY_NOTICES.md`.
5. Allocations are labeled **"Model-ranked simulated allocation"**, never "safe/guaranteed".

Begin from the first unchecked box in the lowest incomplete phase of `ROADMAP.md`.
