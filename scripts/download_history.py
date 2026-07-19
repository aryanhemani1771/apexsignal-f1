"""Download & normalize a historical F1 session via FastF1 into an append-only event log.

Requires the ``data`` extra (``uv sync --extra data``) and network access for the first
download of a session (cached thereafter). No credentials are needed.

    uv run python scripts/download_history.py --season 2024 --round 1 --session R
    uv run python scripts/download_history.py --season 2024 --round 1 --out data/raw/2024_01_R.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path

from apexsignal.ingestion.fastf1_adapter import FastF1Adapter, FastF1NotInstalledError
from apexsignal.ingestion.normalization import run_quality_checks
from apexsignal.settings import load_settings
from apexsignal.storage.event_store import AppendOnlyEventStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Download & normalize an F1 session")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--round", required=True, help="round number or GP name")
    parser.add_argument("--session", default="R", help="R, Q, S, FP1, FP2, FP3")
    parser.add_argument("--out", default=None, help="output JSONL path")
    args = parser.parse_args()

    settings = load_settings()
    try:
        adapter = FastF1Adapter(cache_dir=settings.fastf1_cache_dir)
    except FastF1NotInstalledError as exc:
        print(f"[error] {exc}")
        return 1

    round_arg: int | str = int(args.round) if args.round.isdigit() else args.round
    events = adapter.load_session_events(args.season, round_arg, args.session)
    if not events:
        print("No events extracted.")
        return 1

    store = AppendOnlyEventStore.from_events(events)
    out = Path(args.out or f"data/raw/{args.season}_{args.round}_{args.session}.jsonl")
    store.to_jsonl(out)

    quality = run_quality_checks(events)
    print(f"Wrote {len(store)} events -> {out}")
    print(f"Data quality: {quality.summary()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
