#!/usr/bin/env python3
"""Generate and validate user-specific LaunchAgent plists (does not install)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qwennews.launchd import generate_daily_plist, generate_user_plist  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate macOS LaunchAgent plists for QwenNews (hourly and/or daily)"
    )
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Generate the daily calendar LaunchAgent instead of hourly",
    )
    parser.add_argument(
        "--both",
        action="store_true",
        help="Generate both hourly and daily plists",
    )
    parser.add_argument(
        "--time",
        default=None,
        help="Daily local delivery time HH:MM (default: QWENNEWS_DAILY_LOCAL_TIME)",
    )
    parser.add_argument("--python", type=Path, default=None)
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--log-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--interval", type=int, default=3600, help="Hourly StartInterval")
    args = parser.parse_args()

    targets: list[tuple[str, tuple[Path, list[str]]]] = []
    if args.both or not args.daily:
        targets.append(
            (
                "hourly",
                generate_user_plist(
                    output=None if args.both or args.daily else args.output,
                    python_exe=args.python,
                    working_directory=args.project_root,
                    log_dir=args.log_dir,
                    start_interval_seconds=args.interval,
                ),
            )
        )
    if args.daily or args.both:
        targets.append(
            (
                "daily",
                generate_daily_plist(
                    output=args.output if args.daily and not args.both else None,
                    python_exe=args.python,
                    working_directory=args.project_root,
                    log_dir=args.log_dir,
                    local_time=args.time,
                ),
            )
        )

    failed = False
    for kind, (path, problems) in targets:
        print(f"[{kind}] Wrote: {path}")
        if problems:
            failed = True
            print(f"[{kind}] Validation FAILED:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
        else:
            print(f"[{kind}] Validation: OK")

    print()
    print("This script does NOT install or load LaunchAgents.")
    print("See docs/milestones/m3.md for install / status / disable / uninstall steps.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
