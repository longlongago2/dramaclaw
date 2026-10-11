from __future__ import annotations

import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("local_gateway", ROOT / "scripts/local_gateway.py")
gateway_helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway_helper)


@pytest.fixture
def configured_root(tmp_path, monkeypatch):
    root = tmp_path / "dramaclaw"
    root.mkdir()
    for name in ("PORT", "NOVELVIDEO_DATA_ROOT", "NOVELVIDEO_STATE_DIR", "NEWAPI_ADMIN_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(gateway_helper, "gateway_healthy", lambda url: False)
    return root


def save_settings(root, **settings):
    import sqlite3

    database = root / "state/local/settings.db"
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE runtime_settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.executemany("INSERT INTO runtime_settings VALUES (?, ?)", settings.items())


def make_sibling(root, port=3210):
    directory = root.parent / "dramaclaw-gateway/common"
    directory.mkdir(parents=True)
    (directory / "init.go").write_text(f'Port = flag.Int("port", {port}, "the listening port")')


def plan(root: Path):
    env = os.environ.copy()
    env.pop("PORT", None)
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/local_gateway.py"), "plan", "--root", str(root)],
        env=env, capture_output=True, text=True, encoding="utf-8", timeout=10,
    )


def test_missing_gateway_reports_sibling_lookup_without_an_address(tmp_path):
    result = plan(tmp_path / "dramaclaw")
    assert result.returncode == 0, result.stderr
    gateway = json.loads(result.stdout)
    assert gateway["found"] is False
    assert gateway["directory"] == str(tmp_path / "dramaclaw-gateway")
    assert "Default lookup" in gateway["message"] and "sibling directory" in gateway["message"]
    assert "url" not in gateway and "port" not in gateway


@pytest.mark.parametrize("configured_port,expected", [("", 3210), ("PORT=4321\n", 4321)])
def test_gateway_address_comes_from_sibling_configuration_or_source(tmp_path, configured_port, expected):
    gateway = tmp_path / "dramaclaw-gateway"
    (gateway / "common").mkdir(parents=True)
    (gateway / "common/init.go").write_text('Port = flag.Int("port", 3210, "the listening port")')
    (gateway / ".env").write_text(configured_port)
    result = plan(tmp_path / "dramaclaw")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["found"] is True
    assert data["url"] == f"http://127.0.0.1:{expected}"
    assert data["port"] == expected


def test_unknown_gateway_port_fails_instead_of_guessing(tmp_path):
    gateway = tmp_path / "dramaclaw-gateway/common"
    gateway.mkdir(parents=True)
    (gateway / "init.go").write_text("// unsupported gateway configuration")
    result = plan(tmp_path / "dramaclaw")
    assert result.returncode != 0
    assert "Cannot determine gateway port" in result.stderr
    assert not result.stdout.strip()


def test_auto_official_skips_even_a_broken_checkout_without_creating_settings(configured_root):
    (configured_root.parent / "dramaclaw-gateway").mkdir()
    result = gateway_helper.select_gateway(configured_root, "auto")
    assert result["action"] == "skip"
    assert "official" in result["message"]
    assert not (configured_root / "state").exists()


def test_off_does_not_read_settings_or_inspect_checkout(configured_root):
    database = configured_root / "state/local/settings.db"
    database.parent.mkdir(parents=True)
    database.write_text("broken database")
    result = gateway_helper.select_gateway(configured_root, "off")
    assert result["action"] == "skip"


@pytest.mark.parametrize("model_mode", ["custom", "hybrid"])
def test_auto_starts_required_matching_local_gateway(configured_root, model_mode):
    save_settings(configured_root, model_gateway_mode=model_mode, custom_newapi_admin_base_url="http://localhost:3210")
    make_sibling(configured_root)
    result = gateway_helper.select_gateway(configured_root, "auto")
    assert result["action"] == "start"
    assert result["url"] == "http://127.0.0.1:3210"


@pytest.mark.parametrize("url", ["http://127.0.0.1:3000", "https://gateway.example.com"])
def test_auto_reuses_configured_instance_without_requiring_checkout(configured_root, monkeypatch, url):
    save_settings(configured_root, model_gateway_mode="custom", custom_newapi_admin_base_url=url)
    monkeypatch.setenv("NEWAPI_ADMIN_BASE_URL", "http://127.0.0.1:9999")
    monkeypatch.setattr(gateway_helper, "gateway_healthy", lambda candidate: candidate == url)
    result = gateway_helper.select_gateway(configured_root, "auto")
    assert result["action"] == "reuse"
    assert result["url"] == url
    assert "not managed" in result["message"]


def test_auto_remote_failure_does_not_start_sibling(configured_root):
    save_settings(configured_root, model_gateway_mode="custom", custom_newapi_base_url="https://gateway.example.com/v1")
    make_sibling(configured_root)
    result = gateway_helper.select_gateway(configured_root, "auto")
    assert result["action"] == "error"
    assert "remote gateway" in result["message"]


def test_auto_rejects_local_port_mismatch(configured_root):
    save_settings(configured_root, model_gateway_mode="hybrid", custom_newapi_admin_base_url="http://localhost:9999")
    make_sibling(configured_root)
    result = gateway_helper.select_gateway(configured_root, "auto")
    assert result["action"] == "error"
    assert "does not match" in result["message"]


def test_on_starts_sibling_even_in_official_mode(configured_root):
    make_sibling(configured_root)
    assert gateway_helper.select_gateway(configured_root, "on")["action"] == "start"


@pytest.mark.parametrize("mode", ["on", "auto"])
def test_required_missing_project_reports_lookup_and_ui_only_option(configured_root, mode):
    save_settings(configured_root, model_gateway_mode="hybrid")
    result = gateway_helper.select_gateway(configured_root, mode)
    assert result["action"] == "error"
    assert "Default lookup" in result["message"]
    assert "--gateway-mode off" in result["message"]
    assert "url" not in result


@pytest.mark.parametrize("url", ["http://localhost:invalid", "http://[invalid", "http://user:password@localhost:3210"])
def test_invalid_configured_url_is_an_actionable_error(configured_root, url):
    save_settings(configured_root, model_gateway_mode="custom", custom_newapi_admin_base_url=url)
    result = gateway_helper.select_gateway(configured_root, "auto")
    assert result["action"] == "error"
    assert "Invalid configured gateway URL" in result["message"]
    assert url not in result["message"]


def test_run_preserves_explicit_gateway_database_and_cache_config(configured_root, monkeypatch):
    from types import SimpleNamespace

    make_sibling(configured_root)
    directory = configured_root.parent / "dramaclaw-gateway"
    (directory / ".env").write_text("SQL_DSN=postgres://127.0.0.1/gateway\nSQLITE_PATH=existing.db\nREDIS_CONN_STRING=redis://127.0.0.1:6379\n")
    for name in ("SQL_DSN", "SQLITE_PATH", "REDIS_CONN_STRING"):
        monkeypatch.delenv(name, raising=False)
    binary = Path(gateway_helper.gateway_plan(configured_root)["binary"])
    binary.parent.mkdir(parents=True)
    binary.touch()
    captured = {}

    def run(command, *, env):
        captured.update(env)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(gateway_helper.subprocess, "run", run)
    monkeypatch.setattr(gateway_helper.os, "execve", lambda path, command, env: captured.update(env))
    monkeypatch.setattr(sys, "argv", ["local_gateway.py", "run", "--root", str(configured_root)])
    # main changes cwd to the gateway, so restore it with pytest's monkeypatch.
    monkeypatch.chdir(configured_root)
    if os.name == "nt":
        with pytest.raises(SystemExit) as exited:
            gateway_helper.main()
        assert exited.value.code == 0
    else:
        gateway_helper.main()
    assert captured["SQL_DSN"] == "postgres://127.0.0.1/gateway"
    assert captured["SQLITE_PATH"] == "existing.db"
    assert captured["REDIS_CONN_STRING"] == "redis://127.0.0.1:6379"
    assert not (configured_root / "state/newapi").exists()


@pytest.mark.parametrize("body,healthy", [
    ('{"success": true, "data": {"version": "test"}}', True),
    ('{"success": false, "data": {}}', False),
    ('<html>another service</html>', False),
])
def test_health_probe_validates_status_and_bypasses_local_proxy(monkeypatch, body, healthy):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *args):
            pass

    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("no_proxy", "")
    monkeypatch.setenv("NO_PROXY", "")
    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
        thread.start()
        try:
            assert gateway_helper.gateway_healthy(f"http://127.0.0.1:{server.server_port}") is healthy
        finally:
            server.shutdown()
            thread.join(timeout=5)
