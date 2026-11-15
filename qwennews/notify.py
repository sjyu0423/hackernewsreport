"""Optional macOS notifications (never required for report success)."""

from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


def notify_macos(title: str, body: str, *, enabled: bool = True) -> bool:
    """
    Post a user notification via osascript.

    Returns True on success. Failures are logged and never raised to callers.
    Body must be a short count/summary — never fabricated article claims.
    """
    if not enabled:
        return False
    if shutil.which("osascript") is None:
        logger.info("osascript unavailable; skipping notification")
        return False
    # Escape for AppleScript string literals
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_body = body.replace("\\", "\\\\").replace('"', '\\"')
    script = (
        f'display notification "{safe_body}" with title "{safe_title}" '
        f'sound name "Glass"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Notification failed (report still valid): %s", exc)
        return False
