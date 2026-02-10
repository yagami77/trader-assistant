# Installe le service NSSM trader-runner
# Executer en Administrateur
# Usage: .\scripts\install_runner_nssm.ps1

$CORE_DIR = "C:\trader-assistant-core"
$NSSM = "C:\tools\nssm\nssm.exe"
$PYTHON = "$CORE_DIR\.venv\Scripts\python.exe"
$RUNNER_SCRIPT = "$CORE_DIR\app\scripts\runner_loop.py"

if (-not (Test-Path $NSSM)) {
    Write-Host "NSSM non trouve. Installez-le dans C:\tools\nssm"
    exit 1
}

if (-not (Test-Path $PYTHON)) {
    Write-Host "Python venv non trouve: $PYTHON"
    exit 1
}

& $NSSM install trader-runner $PYTHON "-m" "app.scripts.runner_loop" "--interval" "60" "--symbol" "XAUUSD"
& $NSSM set trader-runner AppDirectory $CORE_DIR
& $NSSM set trader-runner AppEnvironmentExtra "PYTHONPATH=$CORE_DIR"
& $NSSM start trader-runner
Write-Host "Service trader-runner installe et demarre"
