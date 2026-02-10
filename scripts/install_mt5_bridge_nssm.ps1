# Installe le service NSSM mt5-bridge (données réelles MT5 sur port 8080)
# Prerequis: MetaTrader 5 installe et terminal lance (pour donnees live)
# Executer en Administrateur
# Usage: .\scripts\install_mt5_bridge_nssm.ps1

$CORE_DIR = "C:\trader-assistant-core"
$NSSM = "C:\tools\nssm\nssm.exe"
$PYTHON = "$CORE_DIR\.venv\Scripts\python.exe"

if (-not (Test-Path $NSSM)) {
    Write-Host "NSSM non trouve. Installez-le dans C:\tools\nssm"
    exit 1
}

if (-not (Test-Path $PYTHON)) {
    Write-Host "Python venv non trouve: $PYTHON"
    exit 1
}

& $NSSM install mt5-bridge $PYTHON "-m" "uvicorn" "services.mt5_bridge.main:app" "--host" "127.0.0.1" "--port" "8080"
& $NSSM set mt5-bridge AppDirectory $CORE_DIR
& $NSSM set mt5-bridge AppEnvironmentExtra "PYTHONPATH=$CORE_DIR"
& $NSSM start mt5-bridge
Write-Host "Service mt5-bridge installe et demarre (port 8080)"
