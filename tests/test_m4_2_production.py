"""M4.2 production DB config, provenance, scheduler inspection, port diagnostics."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from qwennews.config import load_config
from qwennews.production import (
    PRODUCTION_DB_RELATIVE,
    ProductionConfigError,
    detect_trigger_source,
    diagnose_port,
    inspect_scheduler,
    project_volume_mounted,
    require_existing_db,
    resolve_db_path,
)
from qwennews.storage import ArticleStore


def test_resolve_db_path_defaults_to_live_m0(tmp_path: Path) -> None:
    path = resolve_db_path(None, root=tmp_path, env={})
    assert path == (tmp_path / PRODUCTION_DB_RELATIVE).resolve()


def test_resolve_db_path_respects_env(tmp_path: Path) -> None:
    path = resolve_db_path(
        None,
        root=tmp_path,
        env={"QWENNEWS_DB_PATH": "data/custom.db"},
    )
    assert path == (tmp_path / "data" / "custom.db").resolve()


def test_load_config_uses_production_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QWENNEWS_DB_PATH", raising=False)
    cfg = load_config(env_file=None)
    assert cfg.db_path.name == "live_m0.db"


def test_require_existing_db_fails_visibly(tmp_path: Path) -> None:
    missing = tmp_path / "data" / "live_m0.db"
    with pytest.raises(ProductionConfigError, match="Refusing to create"):
        require_existing_db(missing, purpose="run-hourly")
    assert not missing.exists()


def test_require_existing_db_ok(tmp_path: Path) -> None:
    db = tmp_path / "live_m0.db"
    db.write_bytes(b"sqlite")
    assert require_existing_db(db) == db.resolve()


def test_run_hourly_cli_refuses_missing_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QWENNEWS_DB_PATH", str(tmp_path / "nope.db"))
    from qwennews import cli

    code = cli.main(["run-hourly", "--skip-collect", "--skip-analyze"])
    assert code == 2
    assert not (tmp_path / "nope.db").exists()


def test_detect_trigger_source_launchd_vs_cli() -> None:
    assert (
        detect_trigger_source({"XPC_SERVICE_NAME": "com.qwennews.hourly"}) == "launchd"
    )
    assert detect_trigger_source({"XPC_SERVICE_NAME": "com.qwennews.daily"}) == "launchd"
    assert detect_trigger_source({}) == "cli"
    assert detect_trigger_source({"QWENNEWS_TRIGGER_SOURCE": "kickstart"}) == "kickstart"


def test_orchestration_records_trigger_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QWENNEWS_TRIGGER_SOURCE", "cli")
    db = tmp_path / "t.db"
    store = ArticleStore(db)
    store.init_db()
    from qwennews.config import load_config
    from qwennews.orchestrate import run_orchestration

    cfg = load_config(env_file=None)
    cfg.report_dir = tmp_path / "reports"
    result = run_orchestration(
        "hourly",
        config=cfg,
        store=store,
        skip_collect=True,
        skip_analyze=True,
        acquire_lock=False,
        notify=False,
    )
    assert result.run_id is not None
    rows = store.recent_orchestration_runs(limit=1)
    assert rows
    assert rows[0].get("trigger_source") == "cli"


def test_inspect_scheduler_does_not_claim_success_from_loaded_only() -> None:
    data = inspect_scheduler()
    assert "hourly" in data and "daily" in data
    for mode in ("hourly", "daily"):
        ver = data[mode].get("verification")
        assert ver != "success"
        assert ver in {
            "unverified_not_yet_due",
            "due_but_no_fire",
            "timer_evidence",
            "log_evidence_only",
            "missing_plist",
            "unverified",
        }


def test_diagnose_port_free() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    # socket closed → free
    occ = diagnose_port("127.0.0.1", port)
    assert occ.in_use is False


def test_diagnose_port_occupied() -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = int(srv.getsockname()[1])
    try:
        occ = diagnose_port("127.0.0.1", port)
        assert occ.in_use is True
        assert "will not kill" in occ.detail
    finally:
        srv.close()


def test_project_volume_mounted() -> None:
    info = project_volume_mounted()
    assert info["ok"] is True
    assert info["exists"] is True


def test_dashboard_status_includes_scheduler_and_db_path(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from qwennews.dashboard_api.app import create_app

    db = tmp_path / "live_m0.db"
    store = ArticleStore(db)
    store.init_db()
    app = create_app(db_path=db)
    client = TestClient(app)
    res = client.get("/api/status", params={"live_ollama": "false"})
    assert res.status_code == 200
    body = res.json()
    assert body["db"]["db_path_name"] == "live_m0.db"
    assert "db_path" in body["db"]
    assert "scheduler" in body
    assert "hourly" in body["scheduler"]
    assert "last_successful_hourly_run" in body


def test_launchd_render_includes_db_path(tmp_path: Path) -> None:
    from qwennews.launchd import render_daily_plist, render_hourly_plist

    hourly = render_hourly_plist(
        python_exe=tmp_path / ".venv" / "bin" / "python",
        working_directory=tmp_path,
        log_dir=tmp_path / "logs",
    )
    daily = render_daily_plist(
        python_exe=tmp_path / ".venv" / "bin" / "python",
        working_directory=tmp_path,
        log_dir=tmp_path / "logs",
        hour=7,
        minute=0,
    )
    assert "QWENNEWS_DB_PATH" in hourly["EnvironmentVariables"]
    assert hourly["EnvironmentVariables"]["QWENNEWS_DB_PATH"].endswith("live_m0.db")
    assert daily["EnvironmentVariables"]["QWENNEWS_DB_PATH"].endswith("live_m0.db")
