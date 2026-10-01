# PowerShell 7. Launch a dedicated desktop runtime; never stop another process.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$AppRoot,
    [Parameter(Mandatory)][string]$RuntimeExe,
    [Parameter(Mandatory)][string]$Profile,
    [int]$DebugPort = 0,
    [switch]$Monitor
)
$ErrorActionPreference = 'Stop'
$AppRoot = (Resolve-Path -LiteralPath $AppRoot).Path
$RuntimeExe = (Resolve-Path -LiteralPath $RuntimeExe).Path
$Profile = [IO.Path]::GetFullPath($Profile)
if (-not (Test-Path -LiteralPath (Join-Path $AppRoot 'out/main/index.js'))) { throw 'Build the desktop before launching.' }
if ($DebugPort -lt 0 -or $DebugPort -gt 65535) { throw 'Invalid debug port.' }
# Start-Process joins ArgumentList on Windows. Quote validated filesystem paths explicitly.
foreach ($value in @($AppRoot, $RuntimeExe, $Profile, $PSCommandPath)) {
    if ($value.Contains('"')) { throw 'Double quotes are not supported in launch paths.' }
}
if (-not $Monitor) {
    $launchArgs = @('-NoProfile', '-File', ('"{0}"' -f $PSCommandPath),
        '-AppRoot', ('"{0}"' -f $AppRoot), '-RuntimeExe', ('"{0}"' -f $RuntimeExe),
        '-Profile', ('"{0}"' -f $Profile), '-DebugPort', $DebugPort, '-Monitor')
    Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList $launchArgs -WindowStyle Hidden | Out-Null
    return
}
# Reuse PiDeck's existing profile/version lock and focus IPC. It also restores tray windows.
# Never implement a second PID lock or stop another desktop instance here.
$settings = Get-Content -LiteralPath (Join-Path $Profile 'settings.json') -Raw | ConvertFrom-Json
if ($settings.singleInstance -ne $true) { throw 'Enable singleInstance in this CST profile before launching.' }
try {
    $logDir = Join-Path $Profile 'logs/launches'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $runId = '{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'), $PID
    $receiptPath = Join-Path $logDir "$runId.json"
    $receipt = [ordered]@{ startedAt = [DateTimeOffset]::Now.ToString('o'); app = $AppRoot; runtime = $RuntimeExe; profile = $Profile; status = 'starting' }
    $receipt | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding utf8
    $electronArgs = @(('"{0}"' -f $AppRoot), ('"--user-data-dir={0}"' -f $Profile))
    if ($DebugPort -ne 0) { $electronArgs += @("--remote-debugging-port=$DebugPort", '--remote-debugging-address=127.0.0.1') }
    # Visible window is the requested product; only this supervisor stays hidden.
    $child = Start-Process -FilePath $RuntimeExe -ArgumentList $electronArgs -WorkingDirectory $AppRoot -WindowStyle Normal -PassThru -RedirectStandardOutput (Join-Path $logDir "$runId.stdout.log") -RedirectStandardError (Join-Path $logDir "$runId.stderr.log")
    $receipt.pid = $child.Id
    $receipt.status = 'running'
    $receipt | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding utf8
    $child.WaitForExit()
    $receipt.status = 'exited'
    $receipt.endedAt = [DateTimeOffset]::Now.ToString('o')
    $receipt.exitCode = $child.ExitCode
    $receipt | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding utf8
} catch {
    if ($receiptPath) {
        $receipt.status = 'launcher-error'
        $receipt.error = $_.Exception.Message
        $receipt | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding utf8
    }
    throw
}
