$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python ai_race_trainer.py --camera 1 --port COM3 --car cyan --range-steps 435 --stepper-speed-us 1200 --start-gas 20 --gas-step 2 --laps-per-boost 2 --max-gas 60 --min-drive-gas 20 --launch-max-gas 35 --launch-step 5 --launch-timeout 1.4 --launch-moved-distance-px 35 --level-survival-s 0 --crash-memory-s 2.2 --crash-drop 5 --curve-crash-extra-drop 0 --pre-curve-drop 5 --root-cause-loss-threshold 2 --root-cause-memory-s 6.0 --upstream-fast-drop 5 --upstream-max-cells 9 --explore-random-cells 3 --explore-random-drop 5 --failure-limit-threshold 20 --failure-limit-margin 5 --failure-limit-step 3 --loss-tail-cells 24 --loss-tail-drop 5 --min-cell-track-ratio 0.08
