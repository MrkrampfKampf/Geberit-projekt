$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$AppConnectDevice = "C5:7D:F4:7A:AC:42"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtuelle Umgebung nicht gefunden: $Python"
}

Set-Location -LiteralPath $ProjectRoot
& $Python learning_stepper_driver.py --camera 1 --port COM3 --car cyan --laps 3 --seconds 30 --range-steps 290 --stepper-speed-us 1200 --max-gas 38 --appconnect-device $AppConnectDevice --appconnect-car 6 --dry-run
