# Lance MT5 au demarrage du SYSTEME (session 0) en mode portable pour connexion broker.
# Prerequis: C:\MT5Portable cree (.\scripts\setup_mt5_portable.ps1) et une fois connecte + auto-login.
# Le batch lance C:\MT5Portable\terminal64.exe /portable (voir MT5_PORTABLE_SESSION0.md).
# Executer en Administrateur. Usage: .\scripts\install_mt5_at_system_startup.ps1

$TaskName = "MT5-AtStartup-Session0"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatchPath = Join-Path $ScriptDir "start_mt5_session0.bat"
if (-not (Test-Path $BatchPath)) {
    Write-Host "Batch introuvable: $BatchPath"
    exit 1
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
$Action = New-ScheduledTaskAction -Execute $BatchPath -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
# NT AUTHORITY\SYSTEM = session 0 au demarrage (obligatoire pour que le bridge NSSM voie MT5)
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -User "NT AUTHORITY\SYSTEM" -RunLevel Highest | Out-Null
Write-Host "Tache installee: MT5 sera lance au demarrage du systeme (session 0) via $BatchPath"
Write-Host "Le bridge NSSM (session 0) pourra le voir. Redemarrez le VPS pour tester."
