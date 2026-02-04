# Install NSSM service "TraderOutcomeAgent"
# Executer en Administrateur

$ErrorActionPreference = "Stop"
$NSSM = "C:\tools\nssm\nssm.exe"
$REPO = "C:\trader-assistant-core"
$PYTHON = "$REPO\.venv\Scripts\python.exe"
$LOG_DIR = "$REPO\logs"
$LOG_FILE = "$LOG_DIR\outcome_agent.log"

if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}

$exists = $false
try {
    $null = & $NSSM status TraderOutcomeAgent 2>$null
    if ($LASTEXITCODE -eq 0) { $exists = $true }
} catch { }
if ($exists) {
    & $NSSM stop TraderOutcomeAgent
    Start-Sleep -Seconds 2
    & $NSSM remove TraderOutcomeAgent confirm
}

& $NSSM install TraderOutcomeAgent $PYTHON "scripts\run_outcome_agent.py"
& $NSSM set TraderOutcomeAgent AppDirectory $REPO
& $NSSM set TraderOutcomeAgent AppStdout $LOG_FILE
& $NSSM set TraderOutcomeAgent AppStderr $LOG_FILE
& $NSSM set TraderOutcomeAgent AppStdoutCreationDisposition 4
& $NSSM set TraderOutcomeAgent AppStderrCreationDisposition 4
& $NSSM set TraderOutcomeAgent AppEnvironmentExtra "PYTHONPATH=$REPO"
& $NSSM set TraderOutcomeAgent Start SERVICE_AUTO_START
& "C:\Windows\System32\sc.exe" failure TraderOutcomeAgent reset= 86400 actions= restart/60000/restart/60000/restart/60000

& $NSSM start TraderOutcomeAgent
Start-Sleep -Seconds 3
& $NSSM status TraderOutcomeAgent
Get-Content $LOG_FILE -Tail 30
