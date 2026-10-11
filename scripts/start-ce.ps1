# Start the CE API and frontend locally; no Docker or Bash required.
[CmdletBinding()]
param(
    [switch]$SkipHermes,
    [switch]$SkipInstall,
    [ValidateSet('auto', 'on', 'off')][string]$GatewayMode = 'auto'
)
$ErrorActionPreference = 'Stop'
$rootDir = Split-Path -Parent $PSScriptRoot
$processes = @()
function Get-Setting([string]$Name, [string]$Default) {
    $value = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value
}
function Invoke-Checked([string]$Command, [string[]]$Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command failed (exit $LASTEXITCODE)." }
}
function Start-DevProcess([string]$Name, [string]$Directory, [string]$Command, [string[]]$Arguments) {
    # Encode PowerShell source to pass paths and arguments without cmd.exe quoting.
    $quoted = @($Command) + $Arguments | ForEach-Object { "'" + $_.Replace("'", "''") + "'" }
    $jobCode = Join-Path $rootDir 'scripts/DevProcessJob.cs'
    $quotedJobCode = "'" + $jobCode.Replace("'", "''") + "'"
    # The hidden shell joins its own Windows job before any uv/pnpm children
    # can spawn. Even if a wrapper exits first, the OS kills its descendants.
    $source = '$ErrorActionPreference = ''Stop''; Add-Type -LiteralPath ' + $quotedJobCode +
        '; [CEDevProcessJob]::AttachCurrentProcess(); & ' + ($quoted -join ' ') + '; exit $LASTEXITCODE'
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($source))
    $shell = (Get-Process -Id $PID).Path
    $stdout = Join-Path $logDir "$Name.log"
    $stderr = Join-Path $logDir "$Name.error.log"
    Write-Host ''
    Write-Host "$Name logs:"
    Write-Host "  Output: $stdout"
    Write-Host "  Errors: $stderr"
    return Start-Process -FilePath $shell -ArgumentList @('-NoProfile', '-EncodedCommand', $encoded) -WorkingDirectory $Directory -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
}
Push-Location $rootDir
try {
    foreach ($command in @('uv', 'pnpm.cmd')) {
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "$command is required on PATH." }
    }
    $env:PYTHONUTF8 = '1'
    if (-not (Test-Path -LiteralPath '.env') -and (Test-Path -LiteralPath '.env.example')) {
        Copy-Item -LiteralPath '.env.example' -Destination '.env'
        Write-Host 'Created .env; configure model gateway access there.'
    }
    if (-not $SkipInstall) { Invoke-Checked 'uv' @('sync', '--group', 'dev') }
    # Parse dotenv as data rather than execute shell commands from configuration.
    $python = Join-Path $rootDir '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Application venv is missing. Run uv sync --group dev.' }
    $configJson = & $python -c "import json; from dotenv import dotenv_values; print(json.dumps(dotenv_values('.env'), ensure_ascii=True))"
    if ($LASTEXITCODE -ne 0) { throw 'Could not parse .env.' }
    $config = $configJson | ConvertFrom-Json
    foreach ($property in $config.PSObject.Properties) {
        if ($null -ne $property.Value) { [Environment]::SetEnvironmentVariable($property.Name, [string]$property.Value, 'Process') }
    }
    $apiPort = [int](Get-Setting 'NOVELVIDEO_API_PORT' '8780')
    $apiHost = Get-Setting 'NOVELVIDEO_API_HOST' '0.0.0.0'
    $frontendPort = [int](Get-Setting 'SUPERTALE_FE_PORT' '5173')
    $frontendHost = Get-Setting 'SUPERTALE_FE_HOST' '0.0.0.0'
    $readyTimeout = [int](Get-Setting 'NOVELVIDEO_API_READY_TIMEOUT' '90')
    $gatewayHelper = Join-Path $PSScriptRoot 'local_gateway.py'
    $gateway = (& $python $gatewayHelper select --root $rootDir --gateway-mode $GatewayMode.ToLowerInvariant()) | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Could not discover the sibling gateway project.' }
    if ($gateway.action -eq 'error') { throw $gateway.message }
    Write-Host $gateway.message
    if ($apiPort -lt 1 -or $apiPort -gt 65535 -or $frontendPort -lt 1 -or $frontendPort -gt 65535 -or $apiPort -eq $frontendPort -or $readyTimeout -lt 1) { throw 'Invalid ports or API readiness timeout.' }
    # Refuse occupied ports so readiness cannot accidentally probe another API.
    $ports = @($apiPort, $frontendPort)
    if ($gateway.action -eq 'start') {
        if ($gateway.port -in $ports) { throw 'Gateway PORT conflicts with the API or frontend port.' }
        $ports += [int]$gateway.port
    }
    foreach ($port in $ports) {
        $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Any, $port)
        try {
            # Windows dual-stack listeners can block Node's IPv4 bind even
            # when a default .NET socket with address reuse accepts the port.
            $existingListeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
            if ($existingListeners.Count) { throw 'An IPv4 or IPv6 listener already owns this port.' }
            $listener.ExclusiveAddressUse = $true
            $listener.Start()
        } catch {
            $bindError = $_.Exception.GetBaseException().Message
            $service = if ($port -eq $apiPort) { 'API' } elseif ($port -eq $frontendPort) { 'Frontend' } else { 'Gateway' }
            $owners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty OwningProcess -Unique |
                ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue } |
                ForEach-Object { "$($_.ProcessName) (PID $($_.Id))" })
            $ownerIds = @($existingListeners | Select-Object -ExpandProperty OwningProcess -Unique)
            $detail = if ($owners.Count) { ' Occupied by: ' + ($owners -join ', ') + '.' }
                elseif ($ownerIds.Count) { ' Listener owner PID(s): ' + ($ownerIds -join ', ') + ' (process may have exited while descendants retain the socket).' }
                else { " Bind error: $bindError" }
            $setting = if ($port -eq $apiPort) { 'NOVELVIDEO_API_PORT' } elseif ($port -eq $frontendPort) { 'SUPERTALE_FE_PORT' } else { 'PORT in the gateway project .env' }
            throw "$service port $port is unavailable.$detail Stop the existing dev service with Ctrl+C, or change $setting in .env and retry."
        } finally {
            $listener.Stop()
        }
    }
    $env:ST_EDITION = 'ce'
    foreach ($name in @('ST_CONTROL_PLANE_DSN', 'ST_REDIS_URL', 'ST_CELERY_BROKER_URL', 'ST_CELERY_RESULT_BACKEND')) {
        [Environment]::SetEnvironmentVariable($name, '', 'Process')
    }
    $env:NOVELVIDEO_API_URL = "http://127.0.0.1:$apiPort"
    $env:DRAMACLAW_API_URL = $env:NOVELVIDEO_API_URL
    $env:SUPERTALE_API_URL = $env:NOVELVIDEO_API_URL
    $env:NOVELVIDEO_DATA_ROOT = Get-Setting 'NOVELVIDEO_DATA_ROOT' $rootDir
    foreach ($pair in @(@('NOVELVIDEO_STATE_DIR', 'state'), @('NOVELVIDEO_OUTPUT_DIR', 'output'), @('NOVELVIDEO_RUNTIME_DIR', 'runtime'))) {
        [Environment]::SetEnvironmentVariable($pair[0], (Get-Setting $pair[0] (Join-Path $env:NOVELVIDEO_DATA_ROOT $pair[1])), 'Process')
    }
    if (-not $env:DRAMACLAW_CHAT_BACKEND -and -not $env:SUPERTALE_CHAT_BACKEND) { $env:DRAMACLAW_CHAT_BACKEND = 'hermes' }
    if (-not $SkipHermes) { & (Join-Path $PSScriptRoot 'setup-hermes.ps1') }
    Write-Host ''
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Write-Warning 'ffmpeg is missing; media processing may fail.' }
    if (-not $env:NEWAPI_API_KEY -or $env:NEWAPI_API_KEY -eq 'your_newapi_token') { Write-Warning 'Configure model access before running AI generation.' }
    $frontendDir = Join-Path $rootDir 'frontend'
    if (-not $SkipInstall -and -not (Test-Path -LiteralPath (Join-Path $frontendDir 'node_modules'))) {
        Push-Location $frontendDir
        try { Invoke-Checked 'pnpm.cmd' @('install') } finally { Pop-Location }
    }
    $logDir = Join-Path $env:NOVELVIDEO_RUNTIME_DIR ('dev-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    if ($gateway.action -in @('start', 'reuse')) { $env:NEWAPI_ADMIN_BASE_URL = $gateway.url }
    if ($gateway.action -eq 'start') {
        Write-Host "Preparing gateway from $($gateway.directory)"
        & $python $gatewayHelper prepare --root $rootDir | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Gateway preparation failed; see the error above.' }
        $env:NEWAPI_ADMIN_BASE_URL = $gateway.url
        $gatewayProcess = Start-DevProcess 'gateway' $rootDir $python @($gatewayHelper, 'run', '--root', $rootDir)
        $processes += $gatewayProcess
        $deadline = [DateTime]::UtcNow.AddSeconds($readyTimeout)
        while ($true) {
            if ($gatewayProcess.HasExited) { throw "Gateway exited; see $logDir." }
            try {
                $status = Invoke-RestMethod -Uri "$($gateway.url)/api/status" -TimeoutSec 2
                if ($status.success -eq $true) { break }
            } catch { }
            if ([DateTime]::UtcNow -ge $deadline) { throw "Gateway readiness timed out; see $logDir." }
            Start-Sleep -Milliseconds 250
        }
    }
    $apiProcess = Start-DevProcess 'api' $rootDir (Get-Command uv).Source @('run', '--no-sync', 'novelvideo', 'api', '--host', $apiHost, '--port', "$apiPort", '--reload')
    $processes += $apiProcess
    $deadline = [DateTime]::UtcNow.AddSeconds($readyTimeout)
    while ($true) {
        if ($apiProcess.HasExited) { throw "API exited; see $logDir." }
        try {
            $response = Invoke-WebRequest -Uri "$($env:NOVELVIDEO_API_URL)/api/v1/config" -TimeoutSec 2 -UseBasicParsing
            if ($response.StatusCode -eq 200) { break }
        } catch { }
        if ([DateTime]::UtcNow -ge $deadline) { throw "API readiness timed out; see $logDir." }
        Start-Sleep -Milliseconds 250
    }
    # Keep browser requests relative; Vite proxies them to this local API port.
    $env:VITE_API_URL = $env:NOVELVIDEO_API_URL
    $frontendProcess = Start-DevProcess 'frontend' $frontendDir (Get-Command pnpm.cmd).Source @('dev', '--host', $frontendHost, '--port', "$frontendPort", '--strictPort')
    $processes += $frontendProcess
    $deadline = [DateTime]::UtcNow.AddSeconds($readyTimeout)
    while ($true) {
        if ($frontendProcess.HasExited) {
            Get-Content -LiteralPath (Join-Path $logDir 'frontend.error.log') -Tail 15 | ForEach-Object { Write-Host $_ }
            throw "Frontend exited (code $($frontendProcess.ExitCode)); see $logDir."
        }
        if ($apiProcess.HasExited) { throw "API exited while starting frontend; see $logDir." }
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$frontendPort" -TimeoutSec 2 -UseBasicParsing
            if ($response.StatusCode -eq 200) { break }
        } catch { }
        if ([DateTime]::UtcNow -ge $deadline) { throw "Frontend readiness timed out; see $logDir." }
        Start-Sleep -Milliseconds 250
    }
    Write-Host ''
    Write-Host 'Local development services:'
    Write-Host "  API ready: $($env:NOVELVIDEO_API_URL)"
    Write-Host "  Frontend ready: http://127.0.0.1:$frontendPort"
    if ($gateway.action -eq 'start') { Write-Host "  Gateway ready: $($gateway.url) (project: $($gateway.directory))" }
    else { Write-Host "  $($gateway.message)" }
    Write-Host ''
    Write-Host 'Press Ctrl+C to stop all services started by this launcher.'
    $services = @(@('API', $apiProcess), @('Frontend', $frontendProcess))
    if ($gateway.action -eq 'start') { $services += ,@('Gateway', $gatewayProcess) }
    while ($true) {
        foreach ($entry in $services) {
            if ($entry[1].HasExited) {
                $errorLog = Join-Path $logDir ($entry[0].ToLower() + '.error.log')
                Get-Content -LiteralPath $errorLog -Tail 15 | ForEach-Object { Write-Host $_ }
                throw "$($entry[0]) exited (code $($entry[1].ExitCode)); see $logDir."
            }
        }
        Start-Sleep -Milliseconds 500
    }
} finally {
    foreach ($process in $processes) {
        try {
            if (-not $process.HasExited) {
                # Ctrl+C stops the PowerShell pipeline: invoking a native command
                # with & ... | Out-Null here can be cancelled before it runs.
                # Use .NET directly so cleanup also runs in a stopped pipeline.
                $stopInfo = [Diagnostics.ProcessStartInfo]::new()
                $stopInfo.FileName = Join-Path $env:SystemRoot 'System32/taskkill.exe'
                $stopInfo.Arguments = "/PID $($process.Id) /T /F"
                $stopInfo.UseShellExecute = $false
                $stopInfo.CreateNoWindow = $true
                $stopInfo.RedirectStandardOutput = $true
                $stopInfo.RedirectStandardError = $true
                $stopProcess = [Diagnostics.Process]::Start($stopInfo)
                try {
                    $stopOutput = $stopProcess.StandardOutput.ReadToEnd()
                    $stopError = $stopProcess.StandardError.ReadToEnd()
                    $stopProcess.WaitForExit()
                    if ($stopProcess.ExitCode -ne 0 -and -not $process.HasExited) {
                        [Console]::Error.WriteLine("Could not stop service PID $($process.Id): $stopOutput $stopError")
                    }
                } finally {
                    $stopProcess.Dispose()
                }
            }
        } catch {
            # A failure for one service must not skip cleanup of the other.
            [Console]::Error.WriteLine("Service cleanup failed for PID $($process.Id): $_")
        } finally {
            $process.Dispose()
        }
    }
    Pop-Location
}
