$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Device = "C5:7D:F4:7A:AC:42"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtuelle Umgebung nicht gefunden: $Python"
}

Set-Location -LiteralPath $ProjectRoot
& $Python train_basic_speed.py $Device --car 0 --min-speed 3 --max-speed 10 --laps 4
