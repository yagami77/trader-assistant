# Prepare C:\MT5Portable pour lancer MT5 en session 0 (SYSTEM) avec /portable.
# Une fois le dossier en place, lancer UNE FOIS MT5 portable en tant qu'utilisateur,
# se connecter au broker et activer "Connexion automatique".
# Executer ce script en Administrateur.
# Usage: .\scripts\setup_mt5_portable.ps1

$PortableDir = "C:\MT5Portable"
$Source = "C:\Program Files\MetaTrader 5"
if (-not (Test-Path $Source)) {
    $Source = "${env:ProgramFiles(x86)}\MetaTrader 5"
}
if (-not (Test-Path $Source)) {
    Write-Host "ERREUR: MetaTrader 5 introuvable. Installez MT5 puis relancez ce script."
    exit 1
}

if (Test-Path $PortableDir) {
    $exe = Join-Path $PortableDir "terminal64.exe"
    if (Test-Path $exe) {
        Write-Host "C:\MT5Portable existe deja (terminal64.exe present)."
        Write-Host "Pour recopier: supprimez C:\MT5Portable puis relancez ce script."
        exit 0
    }
}

Write-Host "Copie de $Source vers $PortableDir..."
New-Item -ItemType Directory -Path $PortableDir -Force | Out-Null
robocopy $Source $PortableDir /E /COPY:DAT /R:2 /W:5 /NFL /NDL /NJH /NJS | Out-Null
# robocopy: 0-7 = succes (0=rien a copier, 1=copie ok), 8+ = erreur
if ($LASTEXITCODE -ge 8) {
    Write-Host "ERREUR: echec copie (code $LASTEXITCODE)"
    exit 1
}
Write-Host "OK: $PortableDir pret."
Write-Host ""
Write-Host "ETAPE MANUELLE OBLIGATOIRE (une seule fois):"
Write-Host "  1. Fermez toute instance MT5 (session utilisateur)."
Write-Host "  2. Lancez:  C:\MT5Portable\terminal64.exe /portable"
Write-Host "  3. Connectez-vous au compte broker."
Write-Host "  4. Activez 'Connexion automatique' (ou equivalent)."
Write-Host "  5. Verifiez que les ticks arrivent (ex: graphique XAUUSD)."
Write-Host "  6. Fermez MT5. Ensuite la tache au demarrage lancera ce meme MT5 en session 0 (SYSTEM) avec les memes identifiants."
