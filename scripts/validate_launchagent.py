#!/usr/bin/env python3
"""Validate an existing LaunchAgent plist for QwenNews safety rules."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qwennews.launchd import validate_plist  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a QwenNews LaunchAgent plist")
    parser.add_argument("plist", type=Path, help="Path to .plist file")
    args = parser.parse_args()
    if not args.plist.is_file():
        print(f"Not found: {args.plist}", file=sys.stderr)
        return 2
    problems = validate_plist(args.plist)
    if problems:
        print("Validation FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
