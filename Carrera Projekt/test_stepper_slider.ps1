$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Port = "COM3"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtuelle Umgebung nicht gefunden: $Python"
}

Set-Location -LiteralPath $ProjectRoot
& $Python pc_send_stepper.py --port $Port --cmd "speed 2000"
& $Python pc_send_stepper.py --port $Port --cmd "cw 64"
Start-Sleep -Milliseconds 300
& $Python pc_send_stepper.py --port $Port --cmd "ccw 64"
& $Python pc_send_stepper.py --port $Port --cmd "release"
