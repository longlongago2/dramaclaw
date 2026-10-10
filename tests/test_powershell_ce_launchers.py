from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHELL = shutil.which('pwsh') or shutil.which('powershell')
pytestmark = pytest.mark.skipif(os.name != 'nt' or not SHELL, reason='Windows PowerShell launcher')


def test_powershell_launchers_parse_on_windows():
    code = """
$errors = $null
foreach ($file in @('scripts/start-ce.ps1', 'scripts/setup-hermes.ps1')) {
    [System.Management.Automation.Language.Parser]::ParseFile((Join-Path (Get-Location) $file), [ref]$null, [ref]$errors) | Out-Null
    if ($errors.Count) { throw ($errors | Out-String) }
}
"""
    result = subprocess.run([SHELL, '-NoProfile', '-Command', code], cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('fork', [False, True])
def test_powershell_hermes_check_uses_isolated_interpreter(tmp_path, fork):
    site = tmp_path / 'site'
    adapter = site / 'acp_adapter'
    adapter.mkdir(parents=True)
    (adapter / '__init__.py').write_text('', encoding='utf-8')
    recovery = 'return meta' if fork else 'return {}'
    (adapter / 'server.py').write_text(f'def _recover_turn_meta(meta):\n    {recovery}\n', encoding='utf-8')
    agent = site / 'agent'
    agent.mkdir()
    (agent / '__init__.py').write_text('', encoding='utf-8')
    (agent / 'gateway_credential.py').write_text('def apply_to_headers(): pass\ndef refuse_foreign_endpoint(): pass\n', encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=str(site), HERMES_PYTHON=sys.executable, HERMES_CLI_PATH=sys.executable)
    result = subprocess.run([SHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'scripts/setup-hermes.ps1'), '-Check'], env=env, capture_output=True, text=True, timeout=30)
    assert (result.returncode == 0) == fork, result.stdout + result.stderr
    if not fork:
        assert 'required fork' in result.stderr


def test_hermes_setup_recovers_interrupted_fetch_with_configured_remote(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', *map(str, args)], text=True).strip()

    upstream = tmp_path / 'upstream'
    git('init', '-b', 'main', upstream)
    (upstream / 'fork.txt').write_text('project fork', encoding='utf-8')
    git('-C', upstream, 'add', '.')
    git('-C', upstream, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')
    empty_remote = tmp_path / 'old-remote'
    git('init', '--bare', empty_remote)
    source = tmp_path / 'interrupted-clone'
    git('init', source)
    git('-C', source, 'remote', 'add', 'origin', empty_remote)
    env = dict(os.environ, HERMES_REPO=str(upstream), HERMES_REF='main', HERMES_SOURCE_DIR=str(source), HERMES_PYTHON=sys.executable, HERMES_CLI_PATH=sys.executable, PYTHONPATH='')
    script = str(ROOT / 'scripts/setup-hermes.ps1').replace("'", "''")
    # Stop at dependency installation: this test uses only local Git fixtures.
    code = f"function uv {{ throw 'INSTALL_REACHED' }}; & '{script}'"
    result = subprocess.run([SHELL, '-NoProfile', '-Command', code], env=env, capture_output=True, text=True, timeout=30)
    assert 'INSTALL_REACHED' in result.stderr, result.stdout + result.stderr
    assert git('-C', source, 'remote', 'get-url', 'origin') == str(upstream)
    assert git('-C', source, 'rev-parse', 'HEAD') == git('-C', upstream, 'rev-parse', 'HEAD')


def test_launcher_rejects_ipv6_port_owner_before_starting_services(tmp_path):
    import socket

    if not shutil.which('pnpm.cmd') or not shutil.which('uv'):
        pytest.skip('Launcher dependencies are unavailable')
    (tmp_path / 'scripts').mkdir()
    shutil.copy2(ROOT / 'scripts/start-ce.ps1', tmp_path / 'scripts/start-ce.ps1')
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as occupied:
        occupied.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        occupied.bind(('::', 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        with socket.socket() as available:
            available.bind(('127.0.0.1', 0))
            api_port = available.getsockname()[1]
        (tmp_path / '.env').write_text(f'NOVELVIDEO_API_PORT={api_port}\nSUPERTALE_FE_PORT={port}\n', encoding='utf-8')
        def quoted(path):
            return "'" + str(path).replace("'", "''") + "'"
        code = (
            f"New-Item -ItemType Junction -Path {quoted(tmp_path / '.venv')} "
            f"-Target {quoted(ROOT / '.venv')} | Out-Null; "
            f"& {quoted(tmp_path / 'scripts/start-ce.ps1')} -SkipInstall -SkipHermes"
        )
        result = subprocess.run([SHELL, '-NoProfile', '-Command', code], capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert f'Frontend port {port} is unavailable' in result.stderr, result.stdout + result.stderr
    assert f'PID {os.getpid()}' in result.stderr
    assert not (tmp_path / 'runtime').exists(), 'No services should be launched on an occupied port'
