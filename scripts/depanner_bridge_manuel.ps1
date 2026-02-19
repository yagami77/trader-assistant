# Depannage: lancer le bridge MANUELLEMENT (meme session que MT5).
# Le bridge NSSM est arrete, MT5 et le bridge tournent en session utilisateur -> /health et /tick OK.
#
# ETAPES (dans l'ordre):
# 1. Arreter le service bridge pour liberer le port 8080
# 2. Lancer MT5 en session utilisateur (double-clic sur le raccourci C:\MT5Portable\terminal64.exe - Shortcut)
# 3. Attendre que MT5 soit connecte au broker (Market Watch avec prix)
# 4. Lancer CE script: il demarre le bridge dans cette session (il verra MT5)
#
# Usage: .\scripts\depanner_bridge_manuel.ps1
# Garder la fenetre ouverte; pour arreter: Ctrl+C puis relancer le service si besoin.

$CORE = "C:\trader-assistant-core"
$ErrorActionPreference = "Stop"

Write-Host "=== Depannage bridge manuel ==="
Write-Host ""

# 1. Arreter le service mt5-bridge
Write-Host "1. Arret du service mt5-bridge..."
try {
    Stop-Service -Name "mt5-bridge" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "   Service arrete."
} catch {
    Write-Host "   (service deja arrete ou non installe)"
}
Write-Host ""

# 2. Rappel
Write-Host "2. MT5 doit tourner dans CETTE session (raccourci C:\MT5Portable) et etre connecte au broker."
Write-Host "   Si pas fait: lancez le raccourci, connectez-vous, puis relancez ce script."
Write-Host ""

# 3. Lancer le bridge en avant-plan (meme session = voit MT5)
Write-Host "3. Demarrage du bridge sur 127.0.0.1:8080 (Ctrl+C pour arreter)..."
Write-Host ""
Set-Location $CORE
$env:PYTHONPATH = $CORE
& "$CORE\.venv\Scripts\python.exe" -m uvicorn services.mt5_bridge.main:app --host 127.0.0.1 --port 8080
