"""Generate and validate macOS LaunchAgent plists for hourly/daily orchestration."""

from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path
from typing import Any

LABEL_HOURLY = "com.qwennews.hourly"
LABEL_DAILY = "com.qwennews.daily"
HOURLY_TEMPLATE = "com.qwennews.hourly.plist.template"
DAILY_TEMPLATE = "com.qwennews.daily.plist.template"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def template_path(kind: str = "hourly") -> Path:
    name = HOURLY_TEMPLATE if kind == "hourly" else DAILY_TEMPLATE
    return project_root() / "packaging" / "launchd" / name


def default_python() -> Path:
    return Path(sys.executable).resolve()


def _base_env(working_directory: Path, env: dict[str, str] | None) -> dict[str, str]:
    environment = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "QWENNEWS_PROJECT_ROOT": str(working_directory),
    }
    if env:
        environment.update(env)
    return environment


def _abs_keep_venv(path: Path) -> Path:
    """Absolute path without resolving venv shims away to the base interpreter."""
    path = Path(path)
    # Prefer the path as given when it already points inside a .venv
    text = str(path)
    if "/.venv/" in text or text.endswith("/.venv/bin/python") or "/.venv/bin/" in text:
        return path.absolute()
    # Otherwise resolve normally
    return path.resolve()


def render_hourly_plist(
    *,
    python_exe: Path,
    working_directory: Path,
    log_dir: Path,
    label: str = LABEL_HOURLY,
    start_interval_seconds: int = 3600,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build an hourly LaunchAgent dictionary with absolute paths only."""
    python_exe = _abs_keep_venv(python_exe)
    working_directory = working_directory.resolve()
    log_dir = log_dir.resolve()
    if start_interval_seconds < 300:
        raise ValueError("start_interval_seconds must be >= 300 to avoid burst scheduling")

    merged = dict(env or {})
    # If using a project venv, export VIRTUAL_ENV for reliable site-packages
    venv_root = python_exe.parent.parent if python_exe.parent.name == "bin" else None
    if venv_root and venv_root.name == ".venv":
        merged.setdefault("VIRTUAL_ENV", str(venv_root.resolve()))
    # Pin production DB explicitly in newly generated plists (does not modify installed agents).
    from qwennews.production import PRODUCTION_DB_RELATIVE

    merged.setdefault(
        "QWENNEWS_DB_PATH",
        str((working_directory / PRODUCTION_DB_RELATIVE).resolve()),
    )

    return {
        "Label": label,
        "ProgramArguments": [
            str(python_exe),
            "-m",
            "qwennews",
            "run-hourly",
        ],
        "WorkingDirectory": str(working_directory),
        "StartInterval": int(start_interval_seconds),
        "ThrottleInterval": 1800,
        "RunAtLoad": False,
        "KeepAlive": False,
        "ProcessType": "Background",
        "Nice": 5,
        "StandardOutPath": str(log_dir / "hourly.stdout.log"),
        "StandardErrorPath": str(log_dir / "hourly.stderr.log"),
        "EnvironmentVariables": _base_env(working_directory, merged),
    }


# Backwards-compatible alias
render_plist = render_hourly_plist
LABEL = LABEL_HOURLY


def render_daily_plist(
    *,
    python_exe: Path,
    working_directory: Path,
    log_dir: Path,
    hour: int,
    minute: int,
    label: str = LABEL_DAILY,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Daily LaunchAgent using StartCalendarInterval (local timezone of the Mac).

    ThrottleInterval discourages sleep/wake catch-up bursts. Shared orchestrate
    lock prevents concurrent Ollama use with the hourly agent.
    """
    python_exe = _abs_keep_venv(python_exe)
    working_directory = working_directory.resolve()
    log_dir = log_dir.resolve()
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("daily hour/minute out of range")

    merged = dict(env or {})
    venv_root = python_exe.parent.parent if python_exe.parent.name == "bin" else None
    if venv_root and venv_root.name == ".venv":
        merged.setdefault("VIRTUAL_ENV", str(venv_root.resolve()))
    from qwennews.production import PRODUCTION_DB_RELATIVE

    merged.setdefault(
        "QWENNEWS_DB_PATH",
        str((working_directory / PRODUCTION_DB_RELATIVE).resolve()),
    )

    return {
        "Label": label,
        "ProgramArguments": [
            str(python_exe),
            "-m",
            "qwennews",
            "run-daily",
        ],
        "WorkingDirectory": str(working_directory),
        "StartCalendarInterval": {
            "Hour": int(hour),
            "Minute": int(minute),
        },
        # After sleep/wake, launchd may fire once when the interval is missed;
        # throttle prevents a burst of catch-up executions.
        "ThrottleInterval": 3600,
        "RunAtLoad": False,
        "KeepAlive": False,
        "ProcessType": "Background",
        "Nice": 5,
        "StandardOutPath": str(log_dir / "daily.stdout.log"),
        "StandardErrorPath": str(log_dir / "daily.stderr.log"),
        "EnvironmentVariables": _base_env(working_directory, merged),
    }


def write_plist(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        plistlib.dump(data, fh, fmt=plistlib.FMT_XML, sort_keys=False)
    return path


def validate_plist(path: Path) -> list[str]:
    """Return a list of validation problems (empty = ok)."""
    problems: list[str] = []
    blob = path.read_bytes()
    for marker in (
        b"__PROJECT_ROOT__",
        b"__PYTHON__",
        b"__LOG_DIR__",
        b"__HOME__",
        b"__HOUR__",
        b"__MINUTE__",
    ):
        if marker in blob:
            problems.append(f"unresolved template placeholder {marker.decode()}")
            return problems
    try:
        with path.open("rb") as fh:
            data = plistlib.load(fh)
    except Exception as exc:  # noqa: BLE001
        return [f"invalid plist: {exc}"]
    for key in (
        "Label",
        "ProgramArguments",
        "WorkingDirectory",
        "StandardOutPath",
        "StandardErrorPath",
    ):
        if key not in data:
            problems.append(f"missing key: {key}")
    args = data.get("ProgramArguments") or []
    if not isinstance(args, list) or len(args) < 3:
        problems.append("ProgramArguments must be a list with python -m qwennews …")
    else:
        py = Path(str(args[0]))
        if not py.is_absolute():
            problems.append("Python executable path must be absolute")
        if str(py).startswith("~") or "$HOME" in str(py) or "${HOME}" in str(py):
            problems.append("Python path must not use ~ or $HOME placeholders")
        cmd = " ".join(str(a) for a in args)
        if "run-hourly" not in cmd and "run-daily" not in cmd:
            problems.append("ProgramArguments must invoke run-hourly or run-daily")
    wd = data.get("WorkingDirectory")
    if wd and not Path(str(wd)).is_absolute():
        problems.append("WorkingDirectory must be absolute")
    if "StartInterval" in data:
        interval = int(data.get("StartInterval") or 0)
        if interval < 300:
            problems.append("StartInterval too aggressive (<300s)")
    if "StartCalendarInterval" in data:
        cal = data["StartCalendarInterval"]
        if not isinstance(cal, dict) or "Hour" not in cal or "Minute" not in cal:
            problems.append("StartCalendarInterval must include Hour and Minute")
        if data.get("StartInterval") is not None:
            problems.append("daily agent should not combine StartInterval with calendar")
    if "StartInterval" not in data and "StartCalendarInterval" not in data:
        problems.append("missing StartInterval or StartCalendarInterval")
    if data.get("KeepAlive") is True:
        problems.append("KeepAlive must be false (no polling loop)")
    return problems


def _default_project_python(root: Path) -> Path:
    """Prefer the project venv interpreter when present."""
    venv_py = root / ".venv" / "bin" / "python"
    if venv_py.exists():
        return venv_py
    return default_python()


def generate_user_plist(
    *,
    output: Path | None = None,
    python_exe: Path | None = None,
    working_directory: Path | None = None,
    log_dir: Path | None = None,
    start_interval_seconds: int = 3600,
) -> tuple[Path, list[str]]:
    """Generate hourly LaunchAgent plist (does not install)."""
    root = (working_directory or project_root()).resolve()
    py = python_exe or _default_project_python(root)
    logs = log_dir or (root / "data" / "logs")
    out = output or (root / "packaging" / "launchd" / "generated" / f"{LABEL_HOURLY}.plist")
    data = render_hourly_plist(
        python_exe=py,
        working_directory=root,
        log_dir=logs,
        start_interval_seconds=start_interval_seconds,
        env={"HOME": os.path.expanduser("~")},
    )
    path = write_plist(out, data)
    return path, validate_plist(path)


def generate_daily_plist(
    *,
    output: Path | None = None,
    python_exe: Path | None = None,
    working_directory: Path | None = None,
    log_dir: Path | None = None,
    hour: int | None = None,
    minute: int | None = None,
    local_time: str | None = None,
) -> tuple[Path, list[str]]:
    """
    Generate daily LaunchAgent plist for a local wall-clock delivery time.

    ``local_time`` is ``HH:MM`` in the Mac's local timezone (launchd calendar).
    Does not install or load the agent.
    """
    if local_time:
        hour_s, minute_s = local_time.split(":", 1)
        hour = int(hour_s)
        minute = int(minute_s)
    if hour is None or minute is None:
        from qwennews.config import load_config

        cfg = load_config()
        hour_s, minute_s = cfg.daily_local_time.split(":", 1)
        hour = int(hour_s)
        minute = int(minute_s)

    root = (working_directory or project_root()).resolve()
    py = python_exe or _default_project_python(root)
    logs = log_dir or (root / "data" / "logs")
    out = output or (root / "packaging" / "launchd" / "generated" / f"{LABEL_DAILY}.plist")
    data = render_daily_plist(
        python_exe=py,
        working_directory=root,
        log_dir=logs,
        hour=hour,
        minute=minute,
        env={"HOME": os.path.expanduser("~")},
    )
    path = write_plist(out, data)
    return path, validate_plist(path)
