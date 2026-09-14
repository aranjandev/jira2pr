"""Shared pytest fixtures/sys.path setup for the compiler + runtime test suite.

Works both with an editable install (`pip install -e .`) and a bare checkout,
so CI doesn't silently skip tests if the install step is ever missed.
"""

from __future__ import annotations

import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
COMPILER_DIR = ENGINE_DIR / "compiler"

for p in (str(ENGINE_DIR), str(COMPILER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)
