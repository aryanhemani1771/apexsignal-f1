"""Source reliability scoring.

Reliability is configurable (from ``configs/news_sources.yaml``), never treated as objective
truth: every score records its source class and the config version. Higher-authority sources
(FIA documents, official statements) outweigh aggregators and anonymous social claims.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from apexsignal.domain.news import SourceClass

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _REPO_ROOT / "configs" / "news_sources.yaml"

# Fallback if the config is unavailable — conservative and monotone by authority.
_FALLBACK = {
    SourceClass.FIA_DOCUMENT: 0.98,
    SourceClass.OFFICIAL_TEAM: 0.95,
    SourceClass.OFFICIAL_CHAMPIONSHIP: 0.93,
    SourceClass.NAMED_JOURNALIST: 0.80,
    SourceClass.SPECIALIST_PUB: 0.70,
    SourceClass.GENERAL_PUB: 0.55,
    SourceClass.AGGREGATOR: 0.35,
    SourceClass.ANONYMOUS_SOCIAL: 0.15,
}


class SourceScorer:
    def __init__(self, config_path: str | Path | None = None) -> None:
        self.version = 0
        self._scores: dict[SourceClass, float] = dict(_FALLBACK)
        path = Path(config_path) if config_path else _DEFAULT_CONFIG
        if path.exists():
            self._load(path)

    def _load(self, path: Path) -> None:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        self.version = int(data.get("version", 0))
        for name, spec in (data.get("source_classes") or {}).items():
            try:
                cls = SourceClass(name)
            except ValueError:
                continue
            if isinstance(spec, dict) and "reliability" in spec:
                self._scores[cls] = float(spec["reliability"])

    def reliability(self, source_class: SourceClass) -> float:
        return self._scores.get(source_class, 0.5)

    def is_confirming_source(self, source_class: SourceClass) -> bool:
        """Official/authoritative sources can confirm (not merely report) an event."""
        return source_class in {
            SourceClass.FIA_DOCUMENT,
            SourceClass.OFFICIAL_TEAM,
            SourceClass.OFFICIAL_CHAMPIONSHIP,
        }
