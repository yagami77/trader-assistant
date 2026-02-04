# Installe/recree les 3 services NSSM avec noms standardises
# mt5-bridge, trader-core, trader-runner
# Executer en Administrateur

$ErrorActionPreference = "Stop"
$NSSM = "C:\tools\nssm\nssm.exe"
$BRIDGE_DIR = "C:\trader-assistant"
$CORE_DIR = "C:\trader-assistant-core"

# Supprimer anciens services (noms legacy)
foreach ($name in @("MT5Bridge", "TraderCore", "mt5-bridge", "trader-core", "trader-runner", "TraderOutcomeAgent")) {
    $st = & $NSSM status $name 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Removing $name..."
        & $NSSM stop $name 2>$null
        Start-Sleep -Seconds 2
        & $NSSM remove $name confirm 2>$null
    }
}

# Creer dossiers logs
@("$BRIDGE_DIR\logs", "$CORE_DIR\logs") | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

# --- mt5-bridge ---
& $NSSM install mt5-bridge "C:\Windows\System32\cmd.exe" "/c" "$BRIDGE_DIR\run_bridge.bat"
& $NSSM set mt5-bridge AppDirectory $BRIDGE_DIR
& $NSSM set mt5-bridge AppStdout "$BRIDGE_DIR\logs\bridge.log"
& $NSSM set mt5-bridge AppStderr "$BRIDGE_DIR\logs\bridge_err.log"
& $NSSM set mt5-bridge AppStdoutCreationDisposition 4
& $NSSM set mt5-bridge AppStderrCreationDisposition 4
& $NSSM set mt5-bridge Start SERVICE_AUTO_START
sc.exe failure mt5-bridge reset= 86400 actions= restart/60000/restart/60000/restart/60000
Write-Host "mt5-bridge installed"

# --- trader-core ---
& $NSSM install trader-core "C:\Windows\System32\cmd.exe" "/c" "$CORE_DIR\run_core.bat"
& $NSSM set trader-core AppDirectory $CORE_DIR
& $NSSM set trader-core AppStdout "$CORE_DIR\logs\core.log"
& $NSSM set trader-core AppStderr "$CORE_DIR\logs\core_err.log"
& $NSSM set trader-core AppStdoutCreationDisposition 4
& $NSSM set trader-core AppStderrCreationDisposition 4
& $NSSM set trader-core AppEnvironmentExtra "PYTHONPATH=$CORE_DIR"
& $NSSM set trader-core Start SERVICE_AUTO_START
sc.exe failure trader-core reset= 86400 actions= restart/60000/restart/60000/restart/60000
Write-Host "trader-core installed"

# --- trader-runner ---
& $NSSM install trader-runner "$CORE_DIR\.venv\Scripts\python.exe" "-m" "app.scripts.runner_loop" "--interval" "300" "--symbol" "XAUUSD" "--timeframe" "M15"
& $NSSM set trader-runner AppDirectory $CORE_DIR
& $NSSM set trader-runner AppStdout "$CORE_DIR\logs\runner.log"
& $NSSM set trader-runner AppStderr "$CORE_DIR\logs\runner.log"
& $NSSM set trader-runner AppStdoutCreationDisposition 4
& $NSSM set trader-runner AppStderrCreationDisposition 4
& $NSSM set trader-runner AppEnvironmentExtra "PYTHONPATH=$CORE_DIR"
& $NSSM set trader-runner Start SERVICE_AUTO_START
sc.exe failure trader-runner reset= 86400 actions= restart/60000/restart/60000/restart/60000
Write-Host "trader-runner installed"

# Demarrer
& $NSSM start mt5-bridge
& $NSSM start trader-core
Start-Sleep -Seconds 5
& $NSSM start trader-runner

# --- TraderOutcomeAgent ---
& $NSSM install TraderOutcomeAgent "$CORE_DIR\.venv\Scripts\python.exe" "scripts\run_outcome_agent.py"
& $NSSM set TraderOutcomeAgent AppDirectory $CORE_DIR
& $NSSM set TraderOutcomeAgent AppStdout "$CORE_DIR\logs\outcome_agent.log"
& $NSSM set TraderOutcomeAgent AppStderr "$CORE_DIR\logs\outcome_agent.log"
& $NSSM set TraderOutcomeAgent AppStdoutCreationDisposition 4
& $NSSM set TraderOutcomeAgent AppStderrCreationDisposition 4
& $NSSM set TraderOutcomeAgent AppEnvironmentExtra "PYTHONPATH=$CORE_DIR"
& $NSSM set TraderOutcomeAgent Start SERVICE_AUTO_START
sc.exe failure TraderOutcomeAgent reset= 86400 actions= restart/60000/restart/60000/restart/60000
& $NSSM start TraderOutcomeAgent

Write-Host "`n=== Status ==="
& $NSSM status mt5-bridge
& $NSSM status trader-core
& $NSSM status trader-runner
& $NSSM status TraderOutcomeAgent
