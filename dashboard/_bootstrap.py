"""Make `apexsignal` importable without installing the package.

Streamlit Community Cloud does not reliably build this src-layout package from source, so the
dashboard adds the repository's ``src/`` directory to ``sys.path`` directly and depends only on
plain third-party packages (see ``requirements.txt``). Importing this module (first) performs
that path insertion as a side effect.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
