#!/usr/bin/env python3
"""Convenience entry: python scripts/run_dashboard.py [--mode dev|prod]"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qwennews.dashboard_launcher import main  # noqa: E402

if __name__ == "__main__":
    main()
