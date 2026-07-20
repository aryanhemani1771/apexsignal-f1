"""Run the news-intelligence pipeline on the bundled synthetic documents.

Demonstrates the Phase 4 deliverable end-to-end offline: extract structured events, resolve
supersession/contradictions, map impacts, then show a structured event moving a model prior and
telemetry confirming or rejecting it. No credentials required.

    uv run python scripts/refresh_news.py
"""

from __future__ import annotations

from datetime import timedelta

from apexsignal.ingestion.fixtures_adapter import demo_news_documents, demo_news_roster
from apexsignal.intelligence.entity_resolution import EntityResolver
from apexsignal.intelligence.event_extractor import RuleBasedExtractor
from apexsignal.intelligence.telemetry_confirmation import confirm_with_telemetry
from apexsignal.services.news_service import apply_impacts_to_sim_input, run_pipeline
from apexsignal.simulation.engine import RaceSimulator, SimConfig, SimInput
from apexsignal.simulation.payoff_matrix import price_contracts


def _demo_sim(drivers: list[str]) -> SimInput:
    return SimInput(
        driver_ids=drivers,
        total_laps=40,
        current_lap=15,
        clean_air_pace=[90.0 + i * 0.1 for i in range(len(drivers))],
        tyre_compound=["medium"] * len(drivers),
        tyre_age=[10] * len(drivers),
        pit_count=[0] * len(drivers),
        gap_to_leader=[i * 1.5 for i in range(len(drivers))],
        retired=[False] * len(drivers),
        race_dnf_prob=[0.10] * len(drivers),
    )


def main() -> int:
    docs = demo_news_documents()
    extractor = RuleBasedExtractor(resolver=EntityResolver(demo_news_roster()))
    # Price "as of" just after the last document so every event is available (fixtures are
    # dated in a clearly-synthetic future to signal they are not real news).
    as_of = max(d.first_seen_at for d in docs) + timedelta(hours=1)
    result = run_pipeline(docs, extractor=extractor, as_of=as_of)

    print("=== News timeline (fundamental vs. sentiment separated) ===")
    for item in result.timeline:
        tag = "FUNDAMENTAL" if item.fundamental else "context"
        conf = "confirmed" if item.is_confirmed else "unconfirmed"
        print(f"  [{tag:<11} {conf:<11}] {item.summary}  (x{item.evidence_count})")

    print("\n=== Public sentiment (separate track — never feeds fair value) ===")
    for title, s in result.sentiment.items():
        if s.label != "neutral":
            print(f"  {s.label:<8} ({s.score:+.2f})  {title}")

    if result.contradictions:
        print("\n=== Contradictions ===")
        for c in result.contradictions:
            print(f"  {c.reason}")

    print("\n=== Per-driver impact (parameter deltas) ===")
    for did, impact in result.impacts.items():
        print(
            f"  {did}: pace {impact.pace_delta_seconds_per_lap:+.3f}s  "
            f"grid {impact.grid_position_delta:+.2f}  dnf_logodds {impact.dnf_log_odds_delta:+.2f}"
        )

    drivers = ["AX7", "BO4", "CX3", "DX1", "EX2", "FX8"]
    base = _demo_sim(drivers)
    adjusted = apply_impacts_to_sim_input(base, result.impacts)
    sim = RaceSimulator(SimConfig(n_paths=4000, seed=42))
    base_p = price_contracts(sim.simulate(base))
    adj_p = price_contracts(sim.simulate(adjusted))

    print("\n=== A structured event visibly moves a model prior ===")
    for did in ("BO4", "CX3"):
        print(
            f"  {did} win: {base_p.drivers[did].win:.3f} -> {adj_p.drivers[did].win:.3f}   "
            f"dnf: {base_p.drivers[did].dnf:.3f} -> {adj_p.drivers[did].dnf:.3f}"
        )

    print("\n=== News proposes, telemetry confirms ===")
    bo4 = result.impacts.get("BO4")
    if bo4 and bo4.pace_delta_seconds_per_lap:
        prior, unc = bo4.pace_delta_seconds_per_lap, max(0.05, bo4.pace_uncertainty_delta)
        for label, observed in (("practice confirms", prior * 1.2), ("practice rejects", -prior)):
            tc = confirm_with_telemetry(prior, unc, observed)
            print(
                f"  {label}: prior {prior:+.3f} + obs {observed:+.3f} "
                f"-> posterior {tc.posterior_pace_delta:+.3f} [{tc.verdict}]"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
