$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtuelle Umgebung nicht gefunden: $Python"
}

Set-Location -LiteralPath $ProjectRoot
& $Python autonomous_stepper_driver.py --camera 1 --port COM3 --seconds 30 --car cyan --range-steps 290 --stepper-speed-us 1200 --max-gas 35 --dry-run
