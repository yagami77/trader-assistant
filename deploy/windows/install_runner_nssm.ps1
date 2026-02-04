# Install NSSM service "trader-runner"
# Executer en Administrateur
# Usage: .\install_runner_nssm.ps1

$ErrorActionPreference = "Stop"
$NSSM = "C:\tools\nssm\nssm.exe"
$REPO = "C:\trader-assistant-core"
$PYTHON = "$REPO\.venv\Scripts\python.exe"
$LOG_DIR = "$REPO\logs"
$LOG_FILE = "$LOG_DIR\runner.log"

# 1) Creer logs si manquant
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
    Write-Host "Created $LOG_DIR"
}

# 2) Supprimer service existant si present
$exists = $false
try {
    $null = & $NSSM status trader-runner 2>$null
    if ($LASTEXITCODE -eq 0) { $exists = $true }
} catch {
    # Service n'existe pas
}
if ($exists) {
    Write-Host "Stopping and removing existing trader-runner..."
    & $NSSM stop trader-runner
    Start-Sleep -Seconds 2
    & $NSSM remove trader-runner confirm
}

# 3) Installer le service
& $NSSM install trader-runner $PYTHON "-m" "app.scripts.runner_loop" "--interval" "300" "--symbol" "XAUUSD" "--timeframe" "M15"
if ($LASTEXITCODE -ne 0) { throw "NSSM install failed" }

# 4) Config
& $NSSM set trader-runner AppDirectory $REPO
& $NSSM set trader-runner AppStdout $LOG_FILE
& $NSSM set trader-runner AppStderr $LOG_FILE
& $NSSM set trader-runner AppStdoutCreationDisposition 4
& $NSSM set trader-runner AppStderrCreationDisposition 4
& $NSSM set trader-runner AppEnvironmentExtra "PYTHONPATH=$REPO"
& $NSSM set trader-runner Start SERVICE_AUTO_START

# Restart on failure
& "C:\Windows\System32\sc.exe" failure trader-runner reset= 86400 actions= restart/60000/restart/60000/restart/60000

# 5) Demarrer
& $NSSM start trader-runner
if ($LASTEXITCODE -ne 0) { Write-Warning "Start may have failed - check logs" }

Start-Sleep -Seconds 3

# 6) Afficher statut et log
Write-Host "`n=== NSSM status trader-runner ==="
& $NSSM status trader-runner

Write-Host "`n=== Last 30 lines of runner.log ==="
if (Test-Path $LOG_FILE) {
    Get-Content $LOG_FILE -Tail 30
} else {
    Write-Host "(log file not yet created)"
}
