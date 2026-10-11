"""Discover and run the sibling gateway for both native CE launchers."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

from dotenv import dotenv_values


def gateway_plan(root: Path) -> dict:
    root = root.resolve()
    directory = root.parent / "dramaclaw-gateway"
    rule = "Default lookup: <dramaclaw parent>/dramaclaw-gateway (sibling directory)."
    if not directory.is_dir():
        return {"found": False, "directory": str(directory), "message": f"Gateway project not found: {directory}. {rule}"}
    config = dotenv_values(directory / ".env")
    source = directory / "common/init.go"
    default = re.search(r'Port\s*=\s*flag.Int\("port",\s*(\d+)', source.read_text(encoding="utf-8"))
    port_value = os.environ.get("PORT") or config.get("PORT")
    if not port_value and default is None:
        raise ValueError(f"Cannot determine gateway port from {source}; configure PORT in {directory / '.env'}.")
    port = int(port_value or default.group(1))
    if not 1 <= port <= 65535:
        raise ValueError("Gateway PORT must be between 1 and 65535.")
    binary = root / ".cache/local-gateway" / ("dramaclaw-gateway.exe" if os.name == "nt" else "dramaclaw-gateway")
    return {"found": True, "directory": str(directory), "port": port, "url": f"http://127.0.0.1:{port}", "binary": str(binary)}


def gateway_healthy(url: str) -> bool:
    try:
        # Local discovery must not go through a system HTTP proxy.
        local = urlsplit(url).hostname in {"localhost", "127.0.0.1", "::1"}
        opener = build_opener(ProxyHandler({})) if local else build_opener()
        with opener.open(url.rstrip("/") + "/api/status", timeout=2) as response:
            status = json.load(response)
        return isinstance(status, dict) and status.get("success") is True and isinstance(status.get("data"), dict)
    except (OSError, ValueError):
        return False


def select_gateway(root: Path, mode: str) -> dict:
    root = root.resolve()
    directory = root.parent / "dramaclaw-gateway"
    result = {"action": "skip", "directory": str(directory), "required": False}
    if mode == "off":
        return dict(result, message="Gateway disabled by --gateway-mode off.")
    target = ""
    if mode == "auto":
        data_root = Path(os.environ.get("NOVELVIDEO_DATA_ROOT") or root)
        state = Path(os.environ.get("NOVELVIDEO_STATE_DIR") or data_root / "state")
        database = state / "local/settings.db"
        if not database.is_absolute():
            database = root / database
        settings = {}
        if database.is_file():
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name='runtime_settings'").fetchone():
                    settings = dict(conn.execute("SELECT key, value FROM runtime_settings"))
        gateway_mode = settings.get("model_gateway_mode", "official").strip().lower()
        if gateway_mode not in {"custom", "hybrid"}:
            return dict(result, message="Gateway skipped: official mode uses RelayClaw directly.")
        target = (settings.get("custom_newapi_admin_base_url") or settings.get("custom_newapi_base_url") or os.environ.get("NEWAPI_ADMIN_BASE_URL") or "").strip().rstrip("/")
        if target.endswith("/v1"):
            target = target[:-3]
        if target:
            try:
                parsed = urlsplit(target)
                port = parsed.port
                valid = parsed.scheme in {"http", "https"} and parsed.hostname and not (parsed.username or parsed.password or parsed.query or parsed.fragment) and port != 0
            except ValueError:
                valid = False
            if not valid:
                return dict(result, action="error", required=True, message="Invalid configured gateway URL; fix model gateway settings or use --gateway-mode off to start the UI only.")
            if gateway_healthy(target):
                return dict(result, action="reuse", required=True, url=target, message=f"Gateway ready: {target} (existing instance; not managed by this launcher).")
            if parsed.hostname.lower() not in {"localhost", "127.0.0.1", "::1"}:
                return dict(result, action="error", required=True, message=f"Configured remote gateway is unavailable: {target}. A sibling checkout cannot replace it; use --gateway-mode off to start the UI only.")
    plan = gateway_plan(root)
    if not plan["found"]:
        return dict(result, action="error", required=True, message=plan["message"] + " Use --gateway-mode off to start the UI only.")
    if target:
        parsed = urlsplit(target)
        if parsed.scheme != "http" or (parsed.port or 80) != plan["port"] or parsed.path:
            return dict(result, action="error", required=True, message=f"Configured local gateway {target} does not match the sibling project's port {plan['port']}. Fix its PORT/configuration or use --gateway-mode off.")
    if gateway_healthy(plan["url"]):
        return dict(plan, action="reuse", required=True, message=f"Gateway ready: {plan['url']} (existing instance; not managed by this launcher).")
    return dict(plan, action="start", required=True, message=f"Starting gateway from sibling project: {directory}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "select", "prepare", "run"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--gateway-mode", choices=("auto", "on", "off"), default="auto")
    args = parser.parse_args()
    if args.action == "select":
        print(json.dumps(select_gateway(args.root, args.gateway_mode)))
        return
    plan = gateway_plan(args.root)
    if args.action == "plan" or not plan["found"]:
        print(json.dumps(plan))
        return
    directory = Path(plan["directory"])
    binary = Path(plan["binary"])
    if args.action == "prepare":
        go = shutil.which("go")
        if not go and os.name == "nt":
            installed = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Go/bin/go.exe"
            if installed.is_file():
                go = str(installed)
        if not go:
            raise RuntimeError(f"Gateway project found at {directory}, but Go is missing. Install the version required by its go.mod.")
        if not (directory / "web/dist/index.html").is_file():
            bun = shutil.which("bun")
            if not bun:
                raise RuntimeError(f"Gateway web/dist is missing at {directory}; install Bun to build the management UI.")
            subprocess.run([bun, "install", "--frozen-lockfile"], cwd=directory / "web", check=True, stdout=sys.stderr)
            subprocess.run([bun, "run", "build"], cwd=directory / "web", check=True, stdout=sys.stderr)
        binary.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([go, "build", "-o", str(binary), "."], cwd=directory, check=True, stdout=sys.stderr)
        print(json.dumps(plan))
        return
    if not binary.is_file():
        raise RuntimeError("Gateway binary is missing; run local_gateway.py prepare first.")
    env = os.environ.copy()
    for name, value in dotenv_values(directory / ".env").items():
        if value is not None:
            env.setdefault(name, value)
    # Use CE SQLite by default while respecting explicit gateway DB/cache config.
    state = Path(env.get("NOVELVIDEO_STATE_DIR") or args.root.resolve() / "state")
    if not env.get("SQL_DSN") and not env.get("SQLITE_PATH"):
        database = Path(env.get("NEWAPI_SQLITE_PATH") or state / "newapi/one-api.db")
        database.parent.mkdir(parents=True, exist_ok=True)
        env["SQLITE_PATH"] = str(database.resolve())
    env["PORT"] = str(plan["port"])
    logs = Path(env.get("NOVELVIDEO_RUNTIME_DIR") or args.root.resolve() / "runtime") / "gateway-logs"
    logs.mkdir(parents=True, exist_ok=True)
    os.chdir(directory)
    command = [str(binary), "--port", str(plan["port"]), "--log-dir", str(logs)]
    if os.name == "nt":
        # Windows execve spawns a detached replacement and exits Python. Keep
        # the launcher alive so PowerShell can monitor and kill its full tree.
        sys.exit(subprocess.run(command, env=env).returncode)
    os.execve(str(binary), command, env)


if __name__ == "__main__":
    main()
