"""Rule-based event extraction, entity resolution, and source scoring."""

from __future__ import annotations

from datetime import UTC, datetime

from apexsignal.domain.news import NewsDocument, SourceClass
from apexsignal.intelligence.entity_resolution import EntityResolver
from apexsignal.intelligence.event_extractor import RuleBasedExtractor
from apexsignal.intelligence.event_ontology import F1EventType, is_fundamental
from apexsignal.intelligence.source_scoring import SourceScorer

T0 = datetime(2099, 1, 1, 9, 0, tzinfo=UTC)


def _doc(title: str, text: str, source: SourceClass) -> NewsDocument:
    return NewsDocument(
        title=title,
        text=text,
        source_url="https://example.org/x",
        source_class=source,
        published_at=T0,
        first_seen_at=T0,
        meeting_id="demo",
    )


def test_entity_resolution_whole_word() -> None:
    r = EntityResolver()
    assert r.resolve_drivers("Max Verstappen leads") == ["VER"]
    assert r.resolve_constructors("the Ferrari looked quick") == ["ferrari"]
    assert r.resolve_drivers("no driver here") == []


def test_source_scoring_monotone_by_authority() -> None:
    s = SourceScorer()
    assert s.reliability(SourceClass.FIA_DOCUMENT) > s.reliability(SourceClass.GENERAL_PUB)
    assert s.reliability(SourceClass.GENERAL_PUB) > s.reliability(SourceClass.ANONYMOUS_SOCIAL)
    assert s.is_confirming_source(SourceClass.FIA_DOCUMENT)
    assert not s.is_confirming_source(SourceClass.AGGREGATOR)


def test_confirmed_grid_penalty_from_fia() -> None:
    doc = _doc(
        "Verstappen grid penalty",
        "The stewards ruled that Verstappen takes a grid penalty. It is official.",
        SourceClass.FIA_DOCUMENT,
    )
    events = RuleBasedExtractor().extract(doc)
    grid = next(e for e in events if e.event_type is F1EventType.GRID_PENALTY)
    assert grid.is_confirmed is True
    assert grid.drivers == ["VER"]
    assert grid.grid_position_delta == 5.0  # from configs/event_impact_priors.yaml
    assert grid.source_reliability > 0.9
    assert is_fundamental(grid.event_type)


def test_rumour_is_unconfirmed_and_lower_confidence() -> None:
    doc = _doc(
        "Upgrade rumour",
        "Reportedly, Norris may get a new floor upgrade. Nothing is confirmed.",
        SourceClass.AGGREGATOR,
    )
    events = RuleBasedExtractor().extract(doc)
    upgrade = next(e for e in events if e.event_type is F1EventType.AERODYNAMIC_UPGRADE)
    assert upgrade.is_confirmed is False
    assert upgrade.event_confidence < upgrade.source_reliability


def test_requires_entity_except_weather() -> None:
    ext = RuleBasedExtractor()
    # A grid penalty with no resolvable driver yields nothing.
    assert ext.extract(_doc("penalty", "a grid penalty was given", SourceClass.GENERAL_PUB)) == []
    # Rain is race-wide and needs no driver.
    rain = ext.extract(_doc("weather", "rain is expected on Sunday", SourceClass.GENERAL_PUB))
    assert any(e.event_type is F1EventType.RAIN_EXPECTED for e in rain)


def test_unknown_text_extracts_nothing() -> None:
    assert (
        RuleBasedExtractor().extract(_doc("hello", "a quiet news day", SourceClass.GENERAL_PUB))
        == []
    )
