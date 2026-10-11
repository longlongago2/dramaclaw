"""Exercise the actual Bash launcher with process trees and real signals."""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "POSIX Bash launcher")
class BashLauncherCleanupTests(unittest.TestCase):
    def exercise(self, *, stop_signal=None, starting=False, leader_exits=False, with_gateway=False, reuse_gateway=False, gateway_mode=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            launcher = scripts / "start-ce.sh"
            launcher.write_text((ROOT / "scripts/start-ce.sh").read_text())
            (root / ".env").write_text("")
            (root / "frontend/node_modules").mkdir(parents=True)
            (root / ".venv/bin").mkdir(parents=True)
            (root / ".venv/bin/python").symlink_to(sys.executable)
            setup = scripts / "setup-hermes.sh"
            setup.write_text("#!/bin/sh\nexit 0\n")
            setup.chmod(0o755)
            binaries = root / "bin"
            binaries.mkdir()
            ports = []
            for _ in range(3 if with_gateway or reuse_gateway else 2):
                with socket.socket() as available:
                    available.bind(("127.0.0.1", 0))
                    ports.append(available.getsockname()[1])
            worker = root / "worker.py"
            worker.write_text('''import os, signal, subprocess, sys, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
role = sys.argv[1]
port = os.environ[{"api": "NOVELVIDEO_API_PORT", "frontend": "SUPERTALE_FE_PORT", "gateway": "FIXTURE_GATEWAY_PORT"}[role]]
root = Path(os.environ["FIXTURE_ROOT"])
if len(sys.argv) > 2:
    # Require the launcher's bounded SIGKILL fallback for descendants.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
        def log_message(self, *args):
            pass
    HTTPServer(("127.0.0.1", int(port)), Handler).serve_forever()
else:
    child = subprocess.Popen([sys.executable, __file__, role, "child"])
    (root / (role + ".pids")).write_text(f"{os.getpid()} {child.pid}")
    while not (root / "exit-api").exists() or role != "api":
        time.sleep(0.05)
''')
            # Isolate lifecycle tests from Go/Bun builds; test real discovery separately.
            (scripts / "local_gateway.py").write_text('''import json, os, sys
mode = sys.argv[sys.argv.index("--gateway-mode") + 1] if "--gateway-mode" in sys.argv else "auto"
if sys.argv[1] == "run":
    os.execv(sys.executable, [sys.executable, os.environ["FIXTURE_WORKER"], "gateway"])
elif mode == "off":
    print(json.dumps({"action": "skip", "message": "Gateway disabled"}))
elif os.environ["FIXTURE_GATEWAY"] == "reuse":
    print(json.dumps({"action": "reuse", "message": "Existing gateway; not managed", "url": "http://127.0.0.1:" + os.environ["FIXTURE_GATEWAY_PORT"]}))
elif os.environ["FIXTURE_GATEWAY"] == "1":
    print(json.dumps({"action": "start", "message": "Starting fixture gateway", "port": int(os.environ["FIXTURE_GATEWAY_PORT"]), "url": "http://127.0.0.1:" + os.environ["FIXTURE_GATEWAY_PORT"]}))
else:
    print(json.dumps({"action": "skip", "message": "Gateway skipped: official mode"}))
''')
            for name, body in {
                "uv": 'if [ "$1" = sync ]; then exit 0; fi\nexec "$FIXTURE_PYTHON" "$FIXTURE_WORKER" api',
                "pnpm": 'exec "$FIXTURE_PYTHON" "$FIXTURE_WORKER" frontend',
                "curl": 'case "$*" in *api/status*) echo \'{"success":true}\'; exit 0;; esac\nif [ "$FIXTURE_STARTING" = 1 ]; then exit 1; fi\n[ -f "$FIXTURE_ROOT/api.pids" ]',
                "ffmpeg": "exit 0",
            }.items():
                executable = binaries / name
                executable.write_text(f"#!/bin/sh\n{body}\n")
                executable.chmod(0o755)
            env = dict(
                os.environ, PATH=f"{binaries}:/usr/bin:/bin",
                NOVELVIDEO_API_PORT=str(ports[0]), SUPERTALE_FE_PORT=str(ports[1]),
                NOVELVIDEO_API_READY_TIMEOUT="30", DRAMACLAW_CHAT_BACKEND="codex",
                FIXTURE_PYTHON=sys.executable, FIXTURE_WORKER=str(worker),
                FIXTURE_ROOT=str(root), FIXTURE_STARTING="1" if starting else "0",
                FIXTURE_GATEWAY="reuse" if reuse_gateway else "1" if with_gateway else "0", FIXTURE_GATEWAY_PORT=str(ports[-1]),
            )
            output = root / "launcher.log"
            with output.open("w") as log:
                existing = None
                if reuse_gateway:
                    existing = subprocess.Popen([sys.executable, str(worker), "gateway"], env=env, stdout=log, stderr=log, start_new_session=True)
                command = ["bash", str(launcher)]
                if gateway_mode is not None:
                    command.extend(["--gateway-mode", gateway_mode])
                process = subprocess.Popen(
                    command, env=env, stdout=log, stderr=log,
                    start_new_session=True,
                )

            def listening(port):
                with socket.socket() as probe:
                    probe.settimeout(0.1)
                    return probe.connect_ex(("127.0.0.1", port)) == 0

            active_ports = ports[:1] if starting else ports[:2] if reuse_gateway else ports
            try:
                deadline = time.monotonic() + 10
                while not all(listening(port) for port in (ports if reuse_gateway else active_ports)):
                    self.assertIsNone(process.poll(), output.read_text())
                    self.assertLess(time.monotonic(), deadline, output.read_text())
                    time.sleep(0.05)
                # The terminal's foreground group receives Ctrl+C. The service
                # groups must be separate, so the launcher owns their cleanup.
                for pid_file in root.glob("*.pids"):
                    parent_pid = int(pid_file.read_text().split()[0])
                    self.assertEqual(os.getpgid(parent_pid), parent_pid)
                    self.assertNotEqual(os.getpgid(parent_pid), os.getpgid(process.pid))
                if leader_exits:
                    (root / "exit-api").touch()
                    expected = 1
                else:
                    os.killpg(process.pid, stop_signal)
                    expected = 128 + stop_signal
                self.assertEqual(process.wait(timeout=10), expected, output.read_text())
                # SIGKILL of grandchildren is asynchronous: the launcher can
                # exit before the kernel schedules a descendant's final exit.
                deadline = time.monotonic() + 2
                while any(listening(port) for port in active_ports) and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertFalse(any(listening(port) for port in active_ports), output.read_text())
                if reuse_gateway:
                    self.assertIsNone(existing.poll(), 'Launcher stopped an existing gateway')
                    self.assertTrue(listening(ports[-1]), 'Existing gateway lost its listener')
                if starting:
                    self.assertFalse((root / "frontend.pids").exists(), "Startup continued after cancellation")
            finally:
                # Limit failure cleanup to this fixture's session/groups.
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                for pid_file in root.glob("*.pids"):
                    parent_pid, child_pid = map(int, pid_file.read_text().split())
                    for pid in (parent_pid, child_pid):
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                if existing is not None:
                    existing.wait(timeout=5)

    def test_ctrl_c_during_startup(self):
        self.exercise(stop_signal=signal.SIGINT, starting=True)

    def test_ctrl_c_stops_both_service_groups(self):
        self.exercise(stop_signal=signal.SIGINT)

    def test_sigterm_during_startup(self):
        self.exercise(stop_signal=signal.SIGTERM, starting=True)

    def test_sigterm_stops_both_service_groups(self):
        self.exercise(stop_signal=signal.SIGTERM)

    def test_cleanup_after_group_leader_exits(self):
        self.exercise(leader_exits=True)

    def test_ctrl_c_stops_gateway_and_both_services(self):
        self.exercise(stop_signal=signal.SIGINT, with_gateway=True)

    def test_ctrl_c_preserves_reused_gateway(self):
        self.exercise(stop_signal=signal.SIGINT, reuse_gateway=True)

    def test_off_starts_app_and_preserves_existing_gateway(self):
        self.exercise(stop_signal=signal.SIGINT, reuse_gateway=True, gateway_mode="off")

    def test_invalid_gateway_mode_fails_before_starting_services(self):
        result = subprocess.run(["bash", str(ROOT / "scripts/start-ce.sh"), "--gateway-mode", "invalid"], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn('must be auto, on, or off', result.stderr)


if __name__ == "__main__":
    unittest.main()
