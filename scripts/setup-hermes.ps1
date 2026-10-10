# Install or verify the credential-safe Hermes fork in an isolated Windows venv.
[CmdletBinding()]
param([switch]$Check)
$ErrorActionPreference = 'Stop'
$rootDir = Split-Path -Parent $PSScriptRoot
function Get-Setting([string]$Name, [string]$Default) {
    $value = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value
}
function Invoke-Checked([string]$Command, [string[]]$Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command failed (exit $LASTEXITCODE)." }
}
# Public HTTPS works without configuring GitHub SSH keys or opening port 22.
$env:HERMES_REPO = Get-Setting 'HERMES_REPO' 'https://github.com/dramaclaw/hermes-agent.git'
$env:HERMES_REF = Get-Setting 'HERMES_REF' 'brainclaw/evidence-plane'
$env:HERMES_SOURCE_DIR = Get-Setting 'HERMES_SOURCE_DIR' (Join-Path $rootDir '.cache/hermes-agent')
$env:HERMES_ENV_DIR = Get-Setting 'HERMES_ENV_DIR' (Join-Path $rootDir '.cache/hermes-venv')
$env:HERMES_PYTHON = Get-Setting 'HERMES_PYTHON' (Join-Path $env:HERMES_ENV_DIR 'Scripts/python.exe')
$env:HERMES_BASE_PYTHON = Get-Setting 'HERMES_BASE_PYTHON' (Join-Path $rootDir '.venv/Scripts/python.exe')
$env:HERMES_CLI_PATH = Get-Setting 'HERMES_CLI_PATH' (Join-Path $env:HERMES_ENV_DIR 'Scripts/hermes.exe')
$env:PYTHONUTF8 = '1'
$probe = @"
import sys
try:
    from acp_adapter.server import _recover_turn_meta
    assert _recover_turn_meta({'session_id': 's', 'dramaclaw.probe': 'v'}).get('dramaclaw.probe') == 'v'
    from agent.gateway_credential import apply_to_headers, refuse_foreign_endpoint
except Exception:
    sys.exit(1)
"@
if (-not (Test-Path -LiteralPath $env:HERMES_PYTHON)) {
    if ($Check) { throw "Hermes isolated environment is missing: $env:HERMES_ENV_DIR" }
    if (-not (Test-Path -LiteralPath $env:HERMES_BASE_PYTHON)) { throw 'Run uv sync --group dev first, or set HERMES_BASE_PYTHON.' }
    Invoke-Checked 'uv' @('venv', '--python', $env:HERMES_BASE_PYTHON, $env:HERMES_ENV_DIR)
}
& $env:HERMES_PYTHON -c $probe
if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $env:HERMES_CLI_PATH)) {
    Invoke-Checked $env:HERMES_CLI_PATH @('--version')
    return
}
if ($Check) { throw 'Hermes is missing or is not the required fork. Run scripts/setup-hermes.ps1.' }
if (Test-Path -LiteralPath (Join-Path $env:HERMES_SOURCE_DIR '.git')) {
    # A failed first fetch leaves an initialized repository with the old URL.
    # Honor the configured source on retries as well as first installation.
    $remotes = @(& git -C $env:HERMES_SOURCE_DIR remote)
    if ($LASTEXITCODE -ne 0) { throw 'Could not read Hermes repository remotes.' }
    if ($remotes -contains 'origin') {
        Invoke-Checked 'git' @('-C', $env:HERMES_SOURCE_DIR, 'remote', 'set-url', 'origin', $env:HERMES_REPO)
    } else {
        Invoke-Checked 'git' @('-C', $env:HERMES_SOURCE_DIR, 'remote', 'add', 'origin', $env:HERMES_REPO)
    }
    Invoke-Checked 'git' @('-C', $env:HERMES_SOURCE_DIR, 'fetch', '--quiet', 'origin', $env:HERMES_REF)
    Invoke-Checked 'git' @('-C', $env:HERMES_SOURCE_DIR, 'checkout', '--quiet', 'FETCH_HEAD')
} else {
    # Fetching a ref supports branch names, tags and pinned commit hashes alike.
    if (Test-Path -LiteralPath $env:HERMES_SOURCE_DIR) { throw "Source exists without .git: $env:HERMES_SOURCE_DIR" }
    Invoke-Checked 'git' @('init', $env:HERMES_SOURCE_DIR)
    Invoke-Checked 'git' @('-C', $env:HERMES_SOURCE_DIR, 'remote', 'add', 'origin', $env:HERMES_REPO)
    Invoke-Checked 'git' @('-C', $env:HERMES_SOURCE_DIR, 'fetch', '--depth', '1', 'origin', $env:HERMES_REF)
    Invoke-Checked 'git' @('-C', $env:HERMES_SOURCE_DIR, 'checkout', '--quiet', 'FETCH_HEAD')
}
Invoke-Checked 'uv' @('pip', 'install', '--python', $env:HERMES_PYTHON, '-e', "$($env:HERMES_SOURCE_DIR)[acp]")
Invoke-Checked $env:HERMES_PYTHON @((Join-Path $rootDir 'deploy/patch_hermes_acp_toolsets.py'))
Invoke-Checked $env:HERMES_PYTHON @('-c', $probe)
Invoke-Checked $env:HERMES_CLI_PATH @('--version')
Write-Host 'Hermes fork ready.'
