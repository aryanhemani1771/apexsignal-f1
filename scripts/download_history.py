"""Download & normalize historical F1 data via FastF1/OpenF1.

Planned for Phase 1 — see ROADMAP.md. Not yet implemented; this stub exists so the
entry point and its wiring are discoverable, and it fails loudly rather than pretending.
"""

from __future__ import annotations

import sys

_PHASE = "1"
_DESC = "Download & normalize historical F1 data via FastF1/OpenF1."


def main() -> int:
    sys.stderr.write(
        f"[not implemented] {_DESC}\n"
        f"This is a Phase {_PHASE} deliverable. See ROADMAP.md for status and the next task.\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
