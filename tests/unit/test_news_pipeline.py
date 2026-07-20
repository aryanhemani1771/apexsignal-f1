"""News pipeline: dedup, supersession, contradictions, sentiment, and moving a model prior."""

from __future__ import annotations

from datetime import UTC, datetime

from apexsignal.ingestion.fixtures_adapter import demo_news_documents, demo_news_roster
from apexsignal.intelligence.entity_resolution import EntityResolver
from apexsignal.intelligence.event_extractor import RuleBasedExtractor
from apexsignal.intelligence.event_ontology import F1EventType
from apexsignal.intelligence.sentiment import score_sentiment
from apexsignal.services.news_service import apply_impacts_to_sim_input, run_pipeline
from apexsignal.simulation.engine import RaceSimulator, SimConfig, SimInput
from apexsignal.simulation.payoff_matrix import price_contracts

AFTER_ALL = datetime(2099, 1, 2, tzinfo=UTC)
BEFORE_CONFIRM = datetime(2099, 1, 1, 11, 0, tzinfo=UTC)  # after rumour, before confirmation


def _extractor() -> RuleBasedExtractor:
    return RuleBasedExtractor(resolver=EntityResolver(demo_news_roster()))


def test_sentiment_polarity() -> None:
    assert score_sentiment("strong, confident, impressive pace").label == "positive"
    assert score_sentiment("slow, struggling, disappointing, poor").label == "negative"
    assert score_sentiment("the car is red").label == "neutral"


def test_confirmed_upgrade_supersedes_rumour() -> None:
    result = run_pipeline(demo_news_documents(), extractor=_extractor(), as_of=AFTER_ALL)
    upgrades = [e for e in result.active_events if e.event_type is F1EventType.AERODYNAMIC_UPGRADE]
    assert upgrades, "expected a surviving upgrade event"
    # The surviving upgrade for BO4 is the confirmed one; the rumour was superseded.
    assert all(e.is_confirmed for e in upgrades if "BO4" in e.drivers)
    assert any(e.supersedes_event_ids for e in upgrades)


def test_timeline_separates_fundamental_from_sentiment() -> None:
    result = run_pipeline(demo_news_documents(), extractor=_extractor(), as_of=AFTER_ALL)
    assert any(item.fundamental for item in result.timeline)
    # Sentiment is scored separately per document and never appears as a fundamental event.
    assert result.sentiment  # populated
    assert any(s.label == "positive" for s in result.sentiment.values())


def test_point_in_time_hides_future_confirmation() -> None:
    early = run_pipeline(demo_news_documents(), extractor=_extractor(), as_of=BEFORE_CONFIRM)
    upgrades = [e for e in early.active_events if e.event_type is F1EventType.AERODYNAMIC_UPGRADE]
    # Only the (unconfirmed) rumour is visible yet; the confirmation hasn't been seen.
    assert all(not e.is_confirmed for e in upgrades)


def test_news_moves_the_model_prior() -> None:
    result = run_pipeline(demo_news_documents(), extractor=_extractor(), as_of=AFTER_ALL)
    drivers = ["AX7", "BO4", "CX3", "DX1", "EX2", "FX8"]
    base = SimInput(
        driver_ids=drivers,
        total_laps=40,
        current_lap=15,
        clean_air_pace=[90.0 + i * 0.1 for i in range(len(drivers))],
        tyre_compound=["medium"] * len(drivers),
        tyre_age=[10] * len(drivers),
        pit_count=[0] * len(drivers),
        gap_to_leader=[i * 1.5 for i in range(len(drivers))],
        retired=[False] * len(drivers),
        race_dnf_prob=[0.1] * len(drivers),
    )
    adjusted = apply_impacts_to_sim_input(base, result.impacts)

    # The confirmed aero upgrade makes BO4 faster than in the base case.
    bo4 = drivers.index("BO4")
    assert adjusted.clean_air_pace[bo4] < base.clean_air_pace[bo4]
    # The reliability concern raises CX3's retirement probability.
    cx3 = drivers.index("CX3")
    assert adjusted.race_dnf_prob[cx3] > base.race_dnf_prob[cx3]

    sim = RaceSimulator(SimConfig(n_paths=1500, seed=4))
    base_win = price_contracts(sim.simulate(base)).drivers["BO4"].win
    adj_win = price_contracts(sim.simulate(adjusted)).drivers["BO4"].win
    assert adj_win > base_win  # the upgrade visibly moved BO4's win probability
