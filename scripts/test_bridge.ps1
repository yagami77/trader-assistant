# Test rapide du bridge MT5 (sessions + HTTP).
# Usage: .\scripts\test_bridge.ps1

$CORE = "C:\trader-assistant-core"
Set-Location $CORE

Write-Host "=== 1. Sessions (MT5 + bridge) ==="
& "$CORE\scripts\check_mt5_session.ps1"

Write-Host "`n=== 2. Endpoints bridge (127.0.0.1:8080) ==="
$pingOk = $false
$healthOk = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/ping" -UseBasicParsing -TimeoutSec 5
    $pingOk = ($r.StatusCode -eq 200)
    Write-Host "  /ping  -> $($r.StatusCode) $($r.Content)"
} catch {
    Write-Host "  /ping  -> Erreur: $($_.Exception.Message)"
}
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/health" -UseBasicParsing -TimeoutSec 25
    $healthOk = ($r.StatusCode -eq 200)
    Write-Host "  /health -> $($r.StatusCode) $($r.Content)"
} catch {
    Write-Host "  /health -> Erreur: $($_.Exception.Message)"
}
$tickOk = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/tick?symbol=XAUUSD" -UseBasicParsing -TimeoutSec 10
    $tickOk = ($r.StatusCode -eq 200)
    $j = $r.Content | ConvertFrom-Json
    Write-Host "  /tick  -> $($r.StatusCode) bid=$($j.bid) ask=$($j.ask)"
} catch {
    Write-Host "  /tick  -> Erreur: $($_.Exception.Message)"
}

Write-Host ""
if ($pingOk -and $healthOk -and $tickOk) {
    Write-Host "OK: Bridge et MT5 operatifs (health + tick)."
} elseif ($pingOk -and $healthOk) {
    Write-Host "OK: Bridge et MT5 connecte (/health). Verifier /tick (symbole XAUUSD)."
} elseif ($pingOk) {
    Write-Host "Bridge repond mais MT5 non connecte (/health 503). MT5 portable + auto-login en session 0 ?"
} else {
    Write-Host "Bridge ne repond pas. Verifier le service: nssm status mt5-bridge ; ou redemarrer: .\deploy\windows\restart_prod.ps1"
}
