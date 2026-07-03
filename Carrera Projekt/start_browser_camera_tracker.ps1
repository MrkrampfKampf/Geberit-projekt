$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Url = "http://127.0.0.1:8766/browser_camera_tracker.html"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtuelle Umgebung nicht gefunden: $Python"
}

Set-Location -LiteralPath $ProjectRoot
Start-Process -FilePath $Python -ArgumentList @("-m", "http.server", "8766", "--bind", "127.0.0.1") -WorkingDirectory $ProjectRoot -WindowStyle Hidden
Start-Sleep -Seconds 1
Start-Process $Url
