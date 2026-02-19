# Supprime le service NSSM mt5-bridge pour utiliser a la place la tache Planificateur
# (bridge en session utilisateur = meme session que MT5, connexion fiable).
# Executer en Administrateur.
# Usage: .\scripts\remove_mt5_bridge_nssm.ps1

$NSSM = "C:\tools\nssm\nssm.exe"

if (-not (Test-Path $NSSM)) {
    Write-Host "NSSM non trouve. Rien a supprimer."
    exit 0
}

$st = & $NSSM status mt5-bridge 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Arret et suppression du service mt5-bridge..."
    & $NSSM stop mt5-bridge 2>$null
    Start-Sleep -Seconds 2
    & $NSSM remove mt5-bridge confirm 2>$null
    Write-Host "Service mt5-bridge supprime. Utilisez install_mt5_bridge_task.ps1 pour lancer le bridge a l'ouverture de session."
} else {
    Write-Host "Service mt5-bridge non installe (deja en mode tache ou jamais installe)."
}
