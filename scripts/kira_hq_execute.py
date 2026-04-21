#!/usr/bin/env python3
"""Thin runner for kira_hq.execute_wrapper."""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kira_hq.execute_wrapper import main

if __name__ == "__main__":
    raise SystemExit(main())
