"""Refresh Kalshi/Polymarket public market data (read-only).

Planned for Phase 5 — see ROADMAP.md. Not yet implemented; this stub exists so the
entry point and its wiring are discoverable, and it fails loudly rather than pretending.
"""

from __future__ import annotations

import sys

_PHASE = "5"
_DESC = "Refresh Kalshi/Polymarket public market data (read-only)."


def main() -> int:
    sys.stderr.write(
        f"[not implemented] {_DESC}\n"
        f"This is a Phase {_PHASE} deliverable. See ROADMAP.md for status and the next task.\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
