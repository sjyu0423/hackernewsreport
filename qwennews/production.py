"""Production path, scheduler verification, and operator diagnostics (M4.2)."""

from __future__ import annotations

import os
import re
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Canonical production SQLite file for this checkout. Do not silently create
# alternate empty DBs when this path is missing.
PRODUCTION_DB_RELATIVE = Path("data/live_m0.db")
LEGACY_DEFAULT_DB_RELATIVE = Path("data/qwennews.db")

LABEL_HOURLY = "com.qwennews.hourly"
LABEL_DAILY = "com.qwennews.daily"


class ProductionConfigError(RuntimeError):
    """Visible failure for misconfigured / missing production database."""


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_production_db_path(*, root: Path | None = None) -> Path:
    base = root or project_root()
    return (base / PRODUCTION_DB_RELATIVE).resolve()


def resolve_db_path(
    raw: str | Path | None = None,
    *,
    root: Path | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    """
    Resolve the effective database path.

    Precedence:
    1. Explicit `raw` argument
    2. QWENNEWS_DB_PATH from env
    3. Documented production default: data/live_m0.db
    """
    environ = env if env is not None else os.environ
    base = root or project_root()
    if raw is not None and str(raw).strip():
        path = Path(str(raw).strip())
    else:
        from_env = (environ.get("QWENNEWS_DB_PATH") or "").strip()
        path = Path(from_env) if from_env else PRODUCTION_DB_RELATIVE
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def require_existing_db(path: Path | str, *, purpose: str = "operation") -> Path:
    """Fail visibly if the expected production database file is missing."""
    db = Path(path)
    if not db.is_file():
        raise ProductionConfigError(
            f"Database not found for {purpose}: {db}\n"
            f"Expected an existing production SQLite file "
            f"(canonical path: {PRODUCTION_DB_RELATIVE}).\n"
            "Refusing to create an empty alternate database. "
            "Set QWENNEWS_DB_PATH to an existing file, or run "
            "`python -m qwennews init-db` only when you intentionally want a new DB."
        )
    return db.resolve()


def detect_trigger_source(env: dict[str, str] | None = None) -> str:
    """
    Best-effort provenance for orchestration runs.

    launchd sets XPC_SERVICE_NAME to the job label for LaunchAgents.
    Manual CLI runs typically have no such value.
    """
    environ = env if env is not None else os.environ
    # Explicit override for tests / wrappers (checked before ambient XPC noise)
    forced = (environ.get("QWENNEWS_TRIGGER_SOURCE") or "").strip().lower()
    if forced in {"launchd", "cli", "manual", "kickstart", "test"}:
        return forced

    xpc = (environ.get("XPC_SERVICE_NAME") or "").strip()
    if xpc in {LABEL_HOURLY, LABEL_DAILY}:
        return "launchd"
    if xpc.startswith("com.qwennews."):
        return "launchd"
    # Some sandboxes/export environments set a numeric placeholder — treat as CLI.
    if not xpc or xpc.isdigit():
        return "cli"
    return f"xpc:{xpc}"


def _uid() -> int:
    return os.getuid()


def _plist_path(label: str) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"


def _safe_run(cmd: list[str], *, timeout: float = 5.0) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)


def _parse_launchctl_print(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "runs": None,
        "state": None,
        "last_exit_code": None,
        "raw_excerpt": text[:2000] if text else "",
    }
    m = re.search(r"runs\s*=\s*(\d+)", text)
    if m:
        out["runs"] = int(m.group(1))
    m = re.search(r"state\s*=\s*([^\n]+)", text)
    if m:
        out["state"] = m.group(1).strip()
    m = re.search(r"last exit code\s*=\s*([^\n]+)", text)
    if m:
        out["last_exit_code"] = m.group(1).strip()
    return out


def _log_sizes(project: Path, mode: str) -> dict[str, int]:
    log_dir = project / "data" / "logs"
    return {
        "stdout_bytes": _file_size(log_dir / f"{mode}.stdout.log"),
        "stderr_bytes": _file_size(log_dir / f"{mode}.stderr.log"),
    }


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:
        return 0


def inspect_scheduler(*, project: Path | None = None) -> dict[str, Any]:
    """
    Read-only verification of installed LaunchAgents.

    Never claims timer success from loaded state alone. Distinguishes
    insufficient elapsed time from missing fires after the due window.
    """
    root = (project or project_root()).resolve()
    now = datetime.now().astimezone()
    hourly = _inspect_one(
        label=LABEL_HOURLY,
        mode="hourly",
        root=root,
        now=now,
        kind="interval",
    )
    daily = _inspect_one(
        label=LABEL_DAILY,
        mode="daily",
        root=root,
        now=now,
        kind="calendar",
    )
    return {
        "checked_at": now.isoformat(),
        "project_root": str(root),
        "hourly": hourly,
        "daily": daily,
        "note": (
            "Timer verification requires launchctl runs > 0 and/or non-empty "
            "agent logs after a due window. Loaded state alone is not success. "
            "DB orchestration rows without launchd provenance are treated as CLI/manual."
        ),
    }


def _inspect_one(
    *,
    label: str,
    mode: str,
    root: Path,
    now: datetime,
    kind: str,
) -> dict[str, Any]:
    plist = _plist_path(label)
    info: dict[str, Any] = {
        "label": label,
        "plist_path": str(plist),
        "plist_present": plist.is_file(),
        "kind": kind,
        "verification": "unverified",
        "verification_reason": "",
        "launchctl": {},
        "logs": _log_sizes(root, mode),
        "schedule": {},
        "due": False,
        "elapsed_since_plist_mtime_seconds": None,
    }
    if not plist.is_file():
        info["verification"] = "missing_plist"
        info["verification_reason"] = f"Installed plist not found at {plist}"
        return info

    try:
        import plistlib

        with plist.open("rb") as fh:
            data = plistlib.load(fh)
        info["schedule"] = {
            "StartInterval": data.get("StartInterval"),
            "StartCalendarInterval": data.get("StartCalendarInterval"),
            "RunAtLoad": data.get("RunAtLoad"),
            "WorkingDirectory": data.get("WorkingDirectory"),
            "has_QWENNEWS_DB_PATH": "QWENNEWS_DB_PATH"
            in (data.get("EnvironmentVariables") or {}),
            "ProgramArguments": data.get("ProgramArguments"),
        }
        mtime = datetime.fromtimestamp(plist.stat().st_mtime).astimezone()
        info["plist_mtime"] = mtime.isoformat()
        elapsed = (now - mtime).total_seconds()
        info["elapsed_since_plist_mtime_seconds"] = round(elapsed, 1)
        interval = data.get("StartInterval")
        cal = data.get("StartCalendarInterval")
        if kind == "interval" and isinstance(interval, int):
            info["due"] = elapsed >= float(interval)
            info["schedule"]["next_due_estimate"] = (
                mtime.timestamp() + float(interval)
            )
            info["schedule"]["seconds_until_first_due"] = max(0.0, float(interval) - elapsed)
        elif kind == "calendar" and isinstance(cal, dict):
            hour = int(cal.get("Hour", 0))
            minute = int(cal.get("Minute", 0))
            info["schedule"]["local_time"] = f"{hour:02d}:{minute:02d}"
            # Due today only if wall clock is past today's scheduled time AND
            # plist existed before that time; otherwise next is tomorrow.
            today_fire = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if mtime <= today_fire <= now:
                info["due"] = True
                info["schedule"]["todays_slot_passed"] = True
            else:
                info["due"] = False
                info["schedule"]["todays_slot_passed"] = now >= today_fire
                info["verification_reason"] = (
                    "Daily calendar slot for today has not been observed as a "
                    "timer fire; next genuine fire is the next local "
                    f"{hour:02d}:{minute:02d} after install."
                )
    except Exception as exc:  # noqa: BLE001
        info["schedule_error"] = str(exc)

    code, out, err = _safe_run(["launchctl", "print", f"gui/{_uid()}/{label}"])
    parsed = _parse_launchctl_print(out or err)
    info["launchctl"] = {
        "ok": code == 0,
        **parsed,
    }
    runs = parsed.get("runs")
    log_bytes = info["logs"]["stdout_bytes"] + info["logs"]["stderr_bytes"]

    if isinstance(runs, int) and runs > 0:
        info["verification"] = "timer_evidence"
        info["verification_reason"] = (
            f"launchctl reports runs={runs}. Correlate with agent logs and "
            "orchestration trigger_source=launchd rows before treating as healthy."
        )
    elif log_bytes > 0:
        info["verification"] = "log_evidence_only"
        info["verification_reason"] = (
            "Agent log files are non-empty but launchctl runs is still 0 or unknown. "
            "Manual kickstart can also write logs — do not treat as timer proof alone."
        )
    elif info.get("due"):
        info["verification"] = "due_but_no_fire"
        info["verification_reason"] = (
            "A schedule window appears due based on plist mtime / calendar, but "
            f"launchctl runs={runs!r} and agent logs are empty. Diagnose launchd "
            "delivery (volume mount, gui domain, throttle) — do not claim success."
        )
    else:
        info["verification"] = "unverified_not_yet_due"
        if kind == "interval":
            remaining = (info.get("schedule") or {}).get("seconds_until_first_due")
            info["verification_reason"] = (
                "Hourly StartInterval has not elapsed since plist mtime; "
                f"first timer fire not yet expected ({remaining}s remaining estimate). "
                "Loaded state alone is not verification."
            )
        else:
            info["verification_reason"] = info.get("verification_reason") or (
                "No daily timer fire observed yet; waiting for next calendar slot."
            )
    return info


@dataclass
class PortOccupant:
    host: str
    port: int
    in_use: bool
    pid: int | None = None
    command: str | None = None
    looks_like_qwennews: bool | None = None
    detail: str = ""


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return False
        except OSError:
            return True


def diagnose_port(host: str, port: int) -> PortOccupant:
    """Identify who holds a port without killing anything."""
    if not port_in_use(host, port):
        return PortOccupant(host=host, port=port, in_use=False, detail="port is free")

    code, out, err = _safe_run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"])
    text = out or err
    pid: int | None = None
    command: str | None = None
    looks: bool | None = None
    for line in text.splitlines():
        if line.startswith("COMMAND") or not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            pid = int(parts[1])
            break
    if pid is not None:
        _c, ps_out, _ = _safe_run(["ps", "-p", str(pid), "-o", "command="])
        command = (ps_out or "").strip() or None
        if command:
            lowered = command.lower()
            looks = any(
                token in lowered
                for token in (
                    "qwennews",
                    "dashboard-api",
                    "run_dashboard",
                    "next",
                    "dashboard",
                )
            )
    detail = (
        f"{host}:{port} is in use"
        + (f" by pid={pid}" if pid else "")
        + (f" ({command})" if command else "")
        + ". This launcher will not kill it."
    )
    if looks:
        detail += (
            " Command line looks like a QwenNews/Next process — stop that stack "
            "yourself (Ctrl-C in its terminal) before retrying, or pass a free --port."
        )
    elif looks is False:
        detail += " Occupant does not look like QwenNews; leave it alone and choose another port."
    return PortOccupant(
        host=host,
        port=port,
        in_use=True,
        pid=pid,
        command=command,
        looks_like_qwennews=looks,
        detail=detail,
    )


def project_volume_mounted(root: Path | None = None) -> dict[str, Any]:
    path = (root or project_root()).resolve()
    ok = path.exists() and os.path.isdir(path)
    # External volume heuristic for this checkout
    on_volumes = str(path).startswith("/Volumes/")
    return {
        "path": str(path),
        "exists": ok,
        "on_volumes_prefix": on_volumes,
        "ok": ok,
    }


def db_identity(path: Path) -> dict[str, Any]:
    resolved = Path(path).resolve()
    exists = resolved.is_file()
    size = resolved.stat().st_size if exists else 0
    return {
        "path": str(resolved),
        "name": resolved.name,
        "exists": exists,
        "size_bytes": size,
        "is_canonical_production_name": resolved.name == PRODUCTION_DB_RELATIVE.name,
        "legacy_default_name": LEGACY_DEFAULT_DB_RELATIVE.name,
    }
