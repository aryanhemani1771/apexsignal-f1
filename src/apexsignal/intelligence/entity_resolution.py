"""Entity resolution: map driver/constructor mentions in text to stable ids.

A roster maps names, surnames, and three-letter abbreviations to canonical driver ids
(the abbreviation) and constructor ids (a slug). The resolver is case-insensitive and matches
on whole words so "ALO" doesn't match inside another token.
"""

from __future__ import annotations

import re

from pydantic import BaseModel


class Roster(BaseModel):
    # alias (lowercased) -> driver_id
    driver_aliases: dict[str, str]
    # alias (lowercased) -> constructor_id
    constructor_aliases: dict[str, str]


# A small default roster; callers can supply their own for other seasons.
DEFAULT_ROSTER = Roster(
    driver_aliases={
        "verstappen": "VER",
        "max verstappen": "VER",
        "ver": "VER",
        "perez": "PER",
        "sergio perez": "PER",
        "per": "PER",
        "hamilton": "HAM",
        "lewis hamilton": "HAM",
        "ham": "HAM",
        "russell": "RUS",
        "george russell": "RUS",
        "rus": "RUS",
        "leclerc": "LEC",
        "charles leclerc": "LEC",
        "lec": "LEC",
        "sainz": "SAI",
        "carlos sainz": "SAI",
        "sai": "SAI",
        "norris": "NOR",
        "lando norris": "NOR",
        "nor": "NOR",
        "piastri": "PIA",
        "oscar piastri": "PIA",
        "pia": "PIA",
        "alonso": "ALO",
        "fernando alonso": "ALO",
        "alo": "ALO",
        "stroll": "STR",
        "lance stroll": "STR",
        "str": "STR",
    },
    constructor_aliases={
        "red bull": "red_bull",
        "redbull": "red_bull",
        "mercedes": "mercedes",
        "ferrari": "ferrari",
        "mclaren": "mclaren",
        "aston martin": "aston_martin",
    },
)


class EntityResolver:
    def __init__(self, roster: Roster | None = None) -> None:
        self.roster = roster or DEFAULT_ROSTER

    def _find(self, text: str, aliases: dict[str, str]) -> list[str]:
        low = text.lower()
        found: list[str] = []
        # Longer aliases first so "max verstappen" wins over "verstappen".
        for alias in sorted(aliases, key=len, reverse=True):
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, low):
                ident = aliases[alias]
                if ident not in found:
                    found.append(ident)
        return found

    def resolve_drivers(self, text: str) -> list[str]:
        return self._find(text, self.roster.driver_aliases)

    def resolve_constructors(self, text: str) -> list[str]:
        return self._find(text, self.roster.constructor_aliases)
