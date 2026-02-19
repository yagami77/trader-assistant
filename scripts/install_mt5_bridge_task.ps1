# Installe la tache Planificateur pour lancer le bridge MT5 a l'ouverture de session.
# Le bridge tourne dans la meme session que MT5 (obligatoire pour que la lib MT5 le voie).
# Prerequis: MT5 dans le Dossier de demarrage Windows (pour qu'il s'ouvre avant le bridge).
# Executer en tant que l'utilisateur qui ouvre MT5 (pas forcement Admin).
# Usage: .\scripts\install_mt5_bridge_task.ps1

$CORE_DIR = "C:\trader-assistant-core"
$TaskName = "TraderAssistant-MT5-Bridge"
$ScriptPath = "$CORE_DIR\scripts\start_mt5_bridge_user_session.ps1"

if (-not (Test-Path $ScriptPath)) {
    Write-Host "Script introuvable: $ScriptPath"
    exit 1
}

# Supprimer la tache si elle existe deja (mise a jour)
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -NoProfile -File `"$ScriptPath`"" `
    -WorkingDirectory $CORE_DIR
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Lance le bridge MT5 (meme session que le terminal) pour trader-assistant-core" | Out-Null

Write-Host "Tache installee: $TaskName"
Write-Host "  -> Au demarrage de la session, le bridge sera lance ~50 s apres connexion."
Write-Host "  -> Mettez MT5 dans le Dossier de demarrage pour qu'il s'ouvre en premier."
Write-Host "  -> Pour lancer maintenant (sans redemarrer): Start-ScheduledTask -TaskName $TaskName"
