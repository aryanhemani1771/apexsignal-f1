"""Synthetic execution — paper accounting against synthetic replay order books.

Identical accounting to :class:`PaperExecutor`; the distinction is that the books it fills
against come from the synthetic market adapter, so a full research loop runs offline.
"""

from __future__ import annotations

from apexsignal.execution.paper import PaperExecutor


class SyntheticExecutor(PaperExecutor):
    """Paper executor intended for use with the synthetic market adapter's books."""
