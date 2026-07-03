$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Device = "C5:7D:F4:7A:AC:42"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtuelle Umgebung nicht gefunden: $Python"
}

Set-Location -LiteralPath $ProjectRoot
& $Python -c "from carreralib import ControlUnit; addr='$Device'; cu=ControlUnit(addr, timeout=3); print('Control Unit verbunden'); print('Firmware:', cu.version()); print('Naechste Meldung:', cu.poll()); cu.close()"
