"""Dashboard theme — dark trading-terminal look, original branding only.

No third-party (F1/FIA/team/exchange) logos or colors are used.
"""

from __future__ import annotations

BRAND = "ApexSignal F1"
TAGLINE = "Event-driven F1 prediction-market research — paper trading only"

# Original palette (no team/championship branding).
BG = "#0b0f14"
PANEL = "#131a22"
ACCENT = "#3dd6c4"
TEXT = "#e6edf3"
MUTED = "#8b98a5"

CSS = f"""
<style>
  .stApp {{ background: {BG}; color: {TEXT}; }}
  .as-panel {{ background: {PANEL}; border-radius: 12px; padding: 14px 18px; }}
  .as-accent {{ color: {ACCENT}; }}
  .as-muted {{ color: {MUTED}; font-size: 0.85rem; }}
  h1, h2, h3 {{ color: {TEXT}; }}
</style>
"""

DISCLAIMER = (
    "ApexSignal F1 is an independent research project and is not affiliated with Formula 1, "
    "the FIA, any constructor, Kalshi, Polymarket, or Akuna Capital. Research/paper-trading "
    "only — not financial advice."
)
