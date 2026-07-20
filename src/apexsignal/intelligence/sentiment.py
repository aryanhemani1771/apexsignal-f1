"""Public-sentiment scoring (narrative track).

A deliberately simple lexicon scorer for public/market narrative. Sentiment is displayed
**separately** and never feeds the fair-value model — it can help explain market moves or
potential overreaction, not fundamentals.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

_POSITIVE = {
    "strong",
    "fastest",
    "dominant",
    "confident",
    "quick",
    "improved",
    "flying",
    "impressive",
    "optimistic",
    "breakthrough",
    "resurgent",
    "encouraging",
}
_NEGATIVE = {
    "slow",
    "struggling",
    "worried",
    "concern",
    "disappointing",
    "crisis",
    "pessimistic",
    "off",
    "poor",
    "trouble",
    "nightmare",
    "underwhelming",
    "frustrated",
}


class Sentiment(BaseModel):
    score: float  # [-1, 1]
    label: str  # "positive" | "neutral" | "negative"
    positive_hits: int
    negative_hits: int


def score_sentiment(text: str) -> Sentiment:
    tokens = re.findall(r"[a-z']+", text.lower())
    pos = sum(1 for t in tokens if t in _POSITIVE)
    neg = sum(1 for t in tokens if t in _NEGATIVE)
    total = pos + neg
    score = 0.0 if total == 0 else (pos - neg) / total
    label = "neutral"
    if score > 0.15:
        label = "positive"
    elif score < -0.15:
        label = "negative"
    return Sentiment(score=score, label=label, positive_hits=pos, negative_hits=neg)
