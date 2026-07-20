"""Event extraction: news text → structured :class:`ExtractedF1Event` objects.

The default extractor is deterministic and rule-based (keyword → event type + entity
resolution + configured priors). An optional hosted-LLM extractor can be slotted in behind the
same ``EventExtractor`` protocol, but is never required — CI and the demo run on the rule-based
one. Extraction only assigns quantitative effect sizes when a configured prior exists, and
returns an empty list when nothing is clearly supported (strict "unknown" handling).
"""

from __future__ import annotations

from typing import Protocol

from apexsignal.domain.news import ExtractedF1Event, NewsDocument
from apexsignal.intelligence.entity_resolution import EntityResolver
from apexsignal.intelligence.event_ontology import F1EventType
from apexsignal.intelligence.impact_priors import ImpactPriors, load_impact_priors
from apexsignal.intelligence.source_scoring import SourceScorer

# (event type, trigger phrases, extraction confidence). Multiword phrases are more specific.
_RULES: list[tuple[F1EventType, tuple[str, ...], float]] = [
    (
        F1EventType.GRID_PENALTY,
        ("grid penalty", "grid place penalty", "places on the grid", "grid drop"),
        0.9,
    ),
    (
        F1EventType.POWER_UNIT_CHANGE,
        ("power unit change", "new power unit", "engine change", "new engine", "ice change"),
        0.85,
    ),
    (F1EventType.GEARBOX_CHANGE, ("gearbox change", "new gearbox"), 0.85),
    (
        F1EventType.RELIABILITY_WARNING,
        ("reliability concern", "reliability issue", "reliability worry", "reliability warning"),
        0.8,
    ),
    (
        F1EventType.HYDRAULIC_ISSUE,
        ("hydraulic issue", "hydraulic problem", "hydraulic failure"),
        0.85,
    ),
    (F1EventType.BRAKE_ISSUE, ("brake issue", "brake problem", "brake failure"), 0.85),
    (
        F1EventType.PRACTICE_CRASH,
        ("crashed in practice", "practice crash", "hit the wall in practice", "shunt in fp"),
        0.9,
    ),
    (F1EventType.QUALIFYING_CRASH, ("crashed in qualifying", "qualifying crash"), 0.9),
    (F1EventType.DRIVER_ILLNESS, ("illness", "unwell", "feeling ill", "food poisoning"), 0.75),
    (F1EventType.DRIVER_INJURY, ("injury", "injured"), 0.75),
    (
        F1EventType.AERODYNAMIC_UPGRADE,
        ("aero upgrade", "aerodynamic upgrade", "new floor", "floor upgrade", "upgrade package"),
        0.8,
    ),
    (
        F1EventType.RAIN_EXPECTED,
        (
            "rain expected",
            "rain is expected",
            "rain forecast",
            "rain is forecast",
            "wet race",
            "showers expected",
        ),
        0.8,
    ),
    (
        F1EventType.STEWARD_INVESTIGATION,
        ("under investigation", "investigated by the stewards", "noted by the stewards"),
        0.85,
    ),
    (
        F1EventType.TIME_PENALTY,
        ("time penalty", "5-second penalty", "10-second penalty", "five-second penalty"),
        0.85,
    ),
]

# Weather-type events may be race-wide (no specific driver required).
_ENTITYLESS_OK = {F1EventType.RAIN_EXPECTED}

_CONFIRM_WORDS = ("confirmed", "official", "has been", "will start", "stewards ruled", "ruled that")
_RUMOUR_WORDS = (
    "rumour",
    "rumor",
    "reportedly",
    "expected to",
    "could ",
    "may ",
    "understood to",
    "speculation",
)


class EventExtractor(Protocol):
    def extract(self, document: NewsDocument) -> list[ExtractedF1Event]: ...


class RuleBasedExtractor:
    """Deterministic keyword + entity + prior extractor."""

    def __init__(
        self,
        *,
        resolver: EntityResolver | None = None,
        scorer: SourceScorer | None = None,
        priors: ImpactPriors | None = None,
    ) -> None:
        self.resolver = resolver or EntityResolver()
        self.scorer = scorer or SourceScorer()
        self.priors = priors or load_impact_priors()

    def extract(self, document: NewsDocument) -> list[ExtractedF1Event]:
        text = f"{document.title}. {document.text}"
        low = text.lower()
        drivers = self.resolver.resolve_drivers(text)
        constructors = self.resolver.resolve_constructors(text)
        reliability = self.scorer.reliability(document.source_class)
        confirmed = self._is_confirmed(low, document)

        events: list[ExtractedF1Event] = []
        for event_type, phrases, extraction_conf in _RULES:
            if not any(p in low for p in phrases):
                continue
            if not drivers and not constructors and event_type not in _ENTITYLESS_OK:
                continue

            deltas = self._deltas(event_type)
            events.append(
                ExtractedF1Event(
                    event_type=event_type,
                    drivers=drivers,
                    constructors=constructors,
                    meeting_id=document.meeting_id,
                    source_type=document.source_class,
                    source_reliability=reliability,
                    extraction_confidence=extraction_conf,
                    event_confidence=reliability * (1.0 if confirmed else 0.6),
                    is_confirmed=confirmed,
                    factual_summary=self._summary(event_type, drivers, constructors),
                    supporting_excerpt=document.text[:180],
                    source_url=document.source_url,
                    published_at=document.published_at,
                    first_seen_at=document.first_seen_at,
                    **deltas,
                )
            )
        return events

    def _deltas(self, event_type: F1EventType) -> dict[str, float]:
        # Only populate effect sizes backed by a configured prior.
        out: dict[str, float] = {}
        for field, prior in self.priors.for_event(event_type.value).items():
            out[field] = prior.mean
        return out

    @staticmethod
    def _is_confirmed(low: str, document: NewsDocument) -> bool:
        if any(w in low for w in _RUMOUR_WORDS):
            return False
        if any(w in low for w in _CONFIRM_WORDS):
            return True
        # Official / FIA sources confirm by default.
        return SourceScorer().is_confirming_source(document.source_class)

    @staticmethod
    def _summary(event_type: F1EventType, drivers: list[str], constructors: list[str]) -> str:
        who = ", ".join(drivers or constructors) or "field"
        return f"{event_type.value.replace('_', ' ').title()} — {who}"
