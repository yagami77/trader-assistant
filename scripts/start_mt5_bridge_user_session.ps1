# Lance le bridge MT5 dans la session utilisateur (même session que MT5).
# Attend que MT5 (terminal64/terminal32) soit dans NOTRE session avant de lancer le bridge.
# Usage: tache Planificateur "Au demarrage" ou .\scripts\start_mt5_bridge_user_session.ps1

$CORE_DIR = "C:\trader-assistant-core"
$PYTHON = "$CORE_DIR\.venv\Scripts\python.exe"
$MT5_PROCESS_NAMES = @("terminal64", "terminal32")   # MetaTrader 5
$POLL_INTERVAL_SEC = 5
$TIMEOUT_SEC = 120

Set-Location $CORE_DIR
$env:PYTHONPATH = $CORE_DIR

# Eviter doublon : si le bridge repond 200 (connecte a MT5), ne pas relancer
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    if ($r.StatusCode -eq 200) {
        Write-Host "Bridge deja actif et connecte a MT5, sortie."
        exit 0
    }
} catch { }

$ourSessionId = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
Write-Host "Session actuelle: $ourSessionId. Attente de MT5 dans la meme session (max ${TIMEOUT_SEC}s)..."

$elapsed = 0
while ($elapsed -lt $TIMEOUT_SEC) {
    foreach ($name in $MT5_PROCESS_NAMES) {
        $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
        foreach ($p in $procs) {
            if ($p.SessionId -eq $ourSessionId) {
                Write-Host "MT5 trouve dans cette session (PID $($p.Id)), lancement du bridge..."
                & $PYTHON -m uvicorn services.mt5_bridge.main:app --host 127.0.0.1 --port 8080
                exit $LASTEXITCODE
            }
        }
    }
    Start-Sleep -Seconds $POLL_INTERVAL_SEC
    $elapsed += $POLL_INTERVAL_SEC
    Write-Host "  ... attente MT5 (${elapsed}s)"
}

Write-Host "Timeout: MT5 non trouve dans la session $ourSessionId apres ${TIMEOUT_SEC}s. Lancement du bridge quand meme (peut etre DATA_OFF)."
& $PYTHON -m uvicorn services.mt5_bridge.main:app --host 127.0.0.1 --port 8080
