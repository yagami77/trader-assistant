# Ferme les processus MT5 (terminal64/terminal32) qui tournent en session UTILISATEUR.
# Garde intact l'instance en Session 0 (celle que voit le bridge NSSM).
# Usage: .\scripts\kill_mt5_user_session.ps1

$MT5_NAMES = @("terminal64", "terminal32")
$killed = 0

foreach ($name in $MT5_NAMES) {
    $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
        if ($p.SessionId -ne 0) {
            Write-Host "Arret de $name PID $($p.Id) (Session $($p.SessionId) - session utilisateur)"
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            $killed++
        } else {
            Write-Host "Conserve $name PID $($p.Id) (Session 0 - utilise par le bridge)"
        }
    }
}

if ($killed -eq 0) {
    Write-Host "Aucun MT5 en session utilisateur a fermer."
} else {
    Write-Host "Fait: $killed processus MT5 (session utilisateur) arrete(s). Le bridge utilise l'instance Session 0."
}
