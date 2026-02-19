# Installe la tache planifiee Agent Analyste — Lun-Ven a 23h00 Paris
# Executer en Administrateur
# Usage: .\scripts\install_analyst_task.ps1

$CORE_DIR = "C:\trader-assistant-core"
$PYTHON = "$CORE_DIR\.venv\Scripts\python.exe"
$TASK_NAME = "trader-analyst-daily"
$SCHEDULE = "23:00"

if (-not (Test-Path $PYTHON)) {
    Write-Host "Python venv non trouve: $PYTHON"
    exit 1
}

# Supprimer la tache existante si presente
$existing = schtasks /Query /TN $TASK_NAME 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Suppression de la tache existante..."
    schtasks /Delete /TN $TASK_NAME /F 2>$null
}

# Creer la tache : Lun-Ven a 23h00 (pas Samedi/Dimanche)
$tr = "cmd /c cd /d $CORE_DIR && set PYTHONPATH=$CORE_DIR && `"$PYTHON`" -m app.scripts.analyst_daily_run"
schtasks /Create /TN $TASK_NAME /TR $tr /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST $SCHEDULE /RU SYSTEM /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "Tache installee: $TASK_NAME - Lun-Ven a $SCHEDULE"
    Write-Host "Verifier: schtasks /Query /TN $TASK_NAME"
} else {
    Write-Host "Echec creation tache."
    exit 1
}
