$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtuelle Umgebung nicht gefunden: $Python"
}

Set-Location -LiteralPath $ProjectRoot
& $Python track_dual_cars_live.py --camera 1 --width 1280 --height 720 --hide-masks --colors cyan
