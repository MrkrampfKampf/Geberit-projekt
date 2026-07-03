$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Device = if ($args.Count -gt 0) { $args[0] } else { "C5:7D:F4:7A:AC:42" }

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtuelle Umgebung nicht gefunden: $Python"
}

Set-Location -LiteralPath $ProjectRoot
& $Python lap_time_ui.py $Device
