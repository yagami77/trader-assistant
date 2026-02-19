# Affiche la session de MT5 (terminal64.exe) et du bridge (process sur 8080).
# Usage: .\scripts\check_mt5_session.ps1

Write-Host "=== Session MT5 (terminal64) ==="
$mt5 = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
if (-not $mt5) {
    Write-Host "  terminal64.exe non lance."
} else {
    foreach ($p in $mt5) {
        Write-Host "  PID: $($p.Id)  SessionId: $($p.SessionId)  (0 = Session 0, autre = session utilisateur)"
    }
}

Write-Host ""
Write-Host "=== Process sur le port 8080 (bridge) ==="
try {
    $conn = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue
    if ($conn) {
        foreach ($c in $conn) {
            $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  PID: $($proc.Id)  SessionId: $($proc.SessionId)  Nom: $($proc.ProcessName)"
            }
        }
    } else {
        Write-Host "  Aucun process sur 8080."
    }
} catch {
    Write-Host "  Erreur: $_"
}

Write-Host ""
Write-Host "Rappel: les services NSSM tournent TOUJOURS en Session 0."
Write-Host "Pour que le bridge voie MT5, MT5 doit etre en Session 0 (tache au demarrage systeme)."
