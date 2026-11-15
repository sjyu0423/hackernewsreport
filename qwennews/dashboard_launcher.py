"""One-command local dashboard launcher (API + Next.js). Never kills foreign processes."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8765
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 3000


@dataclass
class LauncherError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class ChildProc:
    name: str
    proc: subprocess.Popen[str]
    log_path: Path | None = None
    _log_handles: list[object] = field(default_factory=list)


@dataclass
class LauncherState:
    children: list[ChildProc] = field(default_factory=list)
    stopping: bool = False


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def port_in_use(host: str, port: int) -> bool:
    """Return True if something already owns host:port (bind probe)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            # Do not set SO_REUSEADDR: we want a real conflict if the port is taken.
            sock.bind((host, port))
            return False
        except OSError:
            return True


def require_free_port(host: str, port: int, label: str) -> None:
    if not port_in_use(host, port):
        return
    try:
        from qwennews.production import diagnose_port

        occ = diagnose_port(host, port)
        raise LauncherError(
            f"{label} port conflict: {occ.detail}\n"
            "Examples: Ctrl-C the other QwenNews terminal, or "
            f"`python -m qwennews dashboard --api-port 8766 --web-port 3001`."
        )
    except LauncherError:
        raise
    except Exception:  # noqa: BLE001
        raise LauncherError(
            f"{label} port {host}:{port} is already in use. "
            "Stop the other process yourself, or choose a different --port. "
            "This launcher will not kill unrelated processes."
        ) from None


def _python_exe(root: Path) -> Path:
    venv = root / ".venv" / "bin" / "python"
    if venv.exists():
        return venv
    return Path(sys.executable)


def _npm_cmd() -> str:
    return "npm"


def start_api(
    state: LauncherState,
    *,
    root: Path,
    host: str,
    port: int,
    log_dir: Path,
) -> ChildProc:
    require_free_port(host, port, "Dashboard API")
    log_dir.mkdir(parents=True, exist_ok=True)
    out = log_dir / "dashboard-api.stdout.log"
    err = log_dir / "dashboard-api.stderr.log"
    py = _python_exe(root)
    cmd = [
        str(py),
        "-m",
        "qwennews",
        "dashboard-api",
        "--host",
        host,
        "--port",
        str(port),
    ]
    print(f"[launcher] starting API: {' '.join(cmd)}")
    print(f"[launcher] API logs: {out} / {err}")
    stamp = f"\n--- launch {time.strftime('%Y-%m-%dT%H:%M:%SZ')} ---\n"
    fo = out.open("a", encoding="utf-8")
    fe = err.open("a", encoding="utf-8")
    fo.write(stamp)
    fe.write(stamp)
    fo.flush()
    fe.flush()
    proc = subprocess.Popen(
        cmd,
        cwd=str(root),
        stdout=fo,
        stderr=fe,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    child = ChildProc(name="api", proc=proc, log_path=err, _log_handles=[fo, fe])
    state.children.append(child)
    return child


def start_web(
    state: LauncherState,
    *,
    root: Path,
    host: str,
    port: int,
    mode: str,
    api_base: str,
    log_dir: Path,
) -> ChildProc:
    require_free_port(host, port, "Dashboard UI")
    dash = root / "dashboard"
    if not dash.is_dir():
        raise LauncherError(f"Dashboard directory missing: {dash}")
    if not (dash / "node_modules").is_dir():
        raise LauncherError(
            f"dashboard/node_modules missing. Run: cd {dash} && npm install"
        )
    log_dir.mkdir(parents=True, exist_ok=True)
    out = log_dir / "dashboard-web.stdout.log"
    err = log_dir / "dashboard-web.stderr.log"
    if mode == "prod":
        # Require a real Next production build (BUILD_ID), not just a .next folder.
        build_id = dash / ".next" / "BUILD_ID"
        if not build_id.is_file():
            print("[launcher] no production build found; running npm run build…")
            build = subprocess.run(
                [_npm_cmd(), "run", "build"],
                cwd=str(dash),
                capture_output=True,
                text=True,
            )
            if build.returncode != 0:
                raise LauncherError(
                    "npm run build failed:\n"
                    + (build.stderr or build.stdout or "(no output)")[-4000:]
                )
            if not build_id.is_file():
                raise LauncherError(
                    "npm run build finished but dashboard/.next/BUILD_ID is missing"
                )
        cmd = [
            _npm_cmd(),
            "run",
            "start",
            "--",
            "--hostname",
            host,
            "--port",
            str(port),
        ]
    else:
        cmd = [
            _npm_cmd(),
            "run",
            "dev",
            "--",
            "--hostname",
            host,
            "--port",
            str(port),
        ]

    env = {
        **os.environ,
        "NEXT_PUBLIC_QWENNEWS_API_BASE": api_base,
    }
    print(f"[launcher] starting UI ({mode}): {' '.join(cmd)}")
    print(f"[launcher] UI logs: {out} / {err}")
    stamp = f"\n--- launch {time.strftime('%Y-%m-%dT%H:%M:%SZ')} mode={mode} ---\n"
    fo = out.open("a", encoding="utf-8")
    fe = err.open("a", encoding="utf-8")
    fo.write(stamp)
    fe.write(stamp)
    fo.flush()
    fe.flush()
    proc = subprocess.Popen(
        cmd,
        cwd=str(dash),
        stdout=fo,
        stderr=fe,
        text=True,
        env=env,
    )
    child = ChildProc(name="web", proc=proc, log_path=err, _log_handles=[fo, fe])
    state.children.append(child)
    return child


def stop_all(state: LauncherState, *, grace_seconds: float = 5.0) -> None:
    if state.stopping:
        return
    state.stopping = True
    print("[launcher] shutting down child processes…")
    for child in list(reversed(state.children)):
        proc = child.proc
        if proc.poll() is not None:
            continue
        try:
            proc.send_signal(signal.SIGTERM)
        except ProcessLookupError:
            continue
    deadline = time.time() + grace_seconds
    while time.time() < deadline:
        if all(c.proc.poll() is not None for c in state.children):
            break
        time.sleep(0.1)
    for child in state.children:
        if child.proc.poll() is None:
            print(f"[launcher] force-killing {child.name} pid={child.proc.pid}")
            try:
                child.proc.kill()
            except ProcessLookupError:
                pass
    for child in state.children:
        try:
            child.proc.wait(timeout=2)
        except Exception:  # noqa: BLE001
            pass
        for handle in child._log_handles:
            try:
                handle.close()  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass
        child._log_handles.clear()
    print("[launcher] stopped.")


def wait_healthy(host: str, port: int, *, timeout: float = 30.0, label: str) -> None:
    start = time.time()
    while time.time() - start < timeout:
        if port_in_use(host, port):
            print(f"[launcher] {label} listening on http://{host}:{port}")
            return
        time.sleep(0.25)
    raise LauncherError(f"{label} did not become ready on {host}:{port} within {timeout}s")


def run_launcher(argv: list[str] | None = None) -> int:
    # Keep parent status lines visible when stdout is piped/backgrounded.
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

    parser = argparse.ArgumentParser(
        description="Start QwenNews local dashboard (API + Next.js) on localhost"
    )
    parser.add_argument(
        "--mode",
        choices=["dev", "prod"],
        default="dev",
        help="dev = next dev; prod = next build/start",
    )
    parser.add_argument("--api-host", default=DEFAULT_API_HOST)
    parser.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    parser.add_argument("--web-host", default=DEFAULT_WEB_HOST)
    parser.add_argument("--web-port", type=int, default=DEFAULT_WEB_PORT)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root (default: repo root)",
    )
    args = parser.parse_args(argv)

    for host in (args.api_host, args.web_host):
        if host not in {"127.0.0.1", "localhost", "::1"}:
            print(
                f"Refusing non-loopback host {host!r}. Dashboard is local-only.",
                file=sys.stderr,
            )
            return 2

    root = (args.project_root or project_root()).resolve()
    log_dir = root / "data" / "logs"
    api_base = f"http://{args.api_host}:{args.api_port}"
    state = LauncherState()

    try:
        from qwennews.config import load_config
        from qwennews.production import ProductionConfigError, require_existing_db

        cfg = load_config()
        require_existing_db(cfg.db_path, purpose="dashboard")
        print(f"[launcher] database: {cfg.db_path}")
    except ProductionConfigError as exc:
        print(f"[launcher] ERROR: {exc}", file=sys.stderr)
        return 1

    def _handle_signal(signum: int, _frame: object) -> None:
        print(f"\n[launcher] received signal {signum}")
        stop_all(state)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        start_api(
            state,
            root=root,
            host=args.api_host,
            port=args.api_port,
            log_dir=log_dir,
        )
        wait_healthy(args.api_host, args.api_port, label="API")
        start_web(
            state,
            root=root,
            host=args.web_host,
            port=args.web_port,
            mode=args.mode,
            api_base=api_base,
            log_dir=log_dir,
        )
        wait_healthy(args.web_host, args.web_port, label="UI", timeout=60.0)
    except LauncherError as exc:
        print(f"[launcher] ERROR: {exc}", file=sys.stderr)
        stop_all(state)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[launcher] unexpected error: {exc}", file=sys.stderr)
        stop_all(state)
        return 1

    print()
    print(f"[launcher] Dashboard UI:  http://{args.web_host}:{args.web_port}")
    print(f"[launcher] Dashboard API: {api_base}")
    print("[launcher] Press Ctrl-C to stop both processes.")
    print()

    try:
        while not state.stopping:
            for child in state.children:
                code = child.proc.poll()
                if code is not None:
                    print(
                        f"[launcher] {child.name} exited unexpectedly with code {code}",
                        file=sys.stderr,
                    )
                    if child.log_path and child.log_path.exists():
                        tail = child.log_path.read_text(encoding="utf-8", errors="replace")[
                            -1500:
                        ]
                        if tail.strip():
                            print("[launcher] --- log tail ---", file=sys.stderr)
                            print(tail, file=sys.stderr)
                    stop_all(state)
                    return 1 if code else 0
            time.sleep(0.4)
    finally:
        stop_all(state)
    return 0


def main() -> None:
    raise SystemExit(run_launcher())


if __name__ == "__main__":
    main()
