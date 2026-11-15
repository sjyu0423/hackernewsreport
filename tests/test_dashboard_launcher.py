"""M4.1 dashboard launcher lifecycle and port-safety tests."""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qwennews.dashboard_launcher import (
    LauncherError,
    LauncherState,
    port_in_use,
    require_free_port,
    run_launcher,
    start_api,
    stop_all,
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_port_in_use_detects_listener() -> None:
    port = _free_port()
    assert port_in_use("127.0.0.1", port) is False
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(1)
    try:
        assert port_in_use("127.0.0.1", port) is True
        with pytest.raises(LauncherError, match="in use|port conflict"):
            require_free_port("127.0.0.1", port, "API")
    finally:
        srv.close()


def test_require_free_port_ok() -> None:
    port = _free_port()
    require_free_port("127.0.0.1", port, "API")


def test_stop_all_terminates_children() -> None:
    state = LauncherState()
    proc = subprocess.Popen(
        ["python3", "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    from qwennews.dashboard_launcher import ChildProc

    state.children.append(ChildProc(name="sleep", proc=proc))
    assert proc.poll() is None
    stop_all(state, grace_seconds=2.0)
    assert proc.poll() is not None
    assert state.stopping is True


def test_run_launcher_refuses_non_loopback() -> None:
    code = run_launcher(["--api-host", "0.0.0.0", "--web-host", "127.0.0.1"])
    assert code == 2


def test_start_api_refuses_occupied_port(tmp_path: Path) -> None:
    port = _free_port()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(1)
    state = LauncherState()
    try:
        with pytest.raises(LauncherError, match="in use|port conflict"):
            start_api(
                state,
                root=tmp_path,
                host="127.0.0.1",
                port=port,
                log_dir=tmp_path / "logs",
            )
        assert state.children == []
    finally:
        srv.close()


def test_run_launcher_stops_when_api_fails_health(tmp_path: Path) -> None:
    """If API never binds, launcher errors and cleans up without hanging."""
    api_port = _free_port()
    web_port = _free_port()

    fake_proc = MagicMock()
    fake_proc.poll.return_value = None  # still running → stop_all signals it
    fake_proc.pid = 99999

    with (
        patch("qwennews.dashboard_launcher.subprocess.Popen", return_value=fake_proc),
        patch(
            "qwennews.dashboard_launcher.wait_healthy",
            side_effect=LauncherError("API down"),
        ),
        patch("qwennews.dashboard_launcher.require_free_port"),
    ):
        code = run_launcher(
            [
                "--mode",
                "dev",
                "--api-port",
                str(api_port),
                "--web-port",
                str(web_port),
                "--project-root",
                str(tmp_path),
            ]
        )
    assert code == 1
    fake_proc.send_signal.assert_called()
    # After signal, pretend process exited so stop_all can finish.
    fake_proc.poll.return_value = 0


def test_stop_all_is_idempotent() -> None:
    state = LauncherState()
    stop_all(state)
    stop_all(state)
    assert state.stopping is True
