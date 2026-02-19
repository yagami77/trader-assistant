# Redemarrage prod — trader-core + trader-runner (option: sans mt5-bridge)
# Executer en Administrateur si services NSSM installes
# Usage: .\restart_prod.ps1
#        .\restart_prod.ps1 -SkipBridge   # ne redémarre PAS mt5-bridge (bridge manuel)

param([switch]$SkipBridge)

$ErrorActionPreference = "Continue"
$CORE_DIR = "C:\trader-assistant-core"

Write-Host "=== Mise a jour prod trader-assistant-core ==="

# 1) Init DB (migrations) — charge .env.local pour utiliser la meme DB que l'API
Write-Host "`n1. Init DB..."
try {
    Push-Location $CORE_DIR
    $env:PYTHONPATH = $CORE_DIR
    & "$CORE_DIR\.venv\Scripts\python.exe" -c "
from pathlib import Path
_env = Path('.env.local')
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env)
    except ImportError: pass
from app.infra.db import init_db
init_db()
print('DB OK')
"
    if ($LASTEXITCODE -eq 0) { Write-Host "DB OK" } else { Write-Host "DB init skipped (check manually)" }
} catch {
    Write-Host "DB init: $($_.Exception.Message)"
} finally {
    Pop-Location
}

# 2) Cloturer tous les trades actifs EN PREMIER (API doit etre up)
# Utilise reset-active-trade qui appelle clear_all_active_trades() pour effacer tous les jours
Write-Host "`n2. Cloture setup actif (reset trade)..."
$envLocal = Join-Path $CORE_DIR ".env.local"
$adminToken = $null
if (Test-Path $envLocal) {
    $line = Get-Content $envLocal -ErrorAction SilentlyContinue | Where-Object { $_ -match "^ADMIN_TOKEN=(.+)$" } | Select-Object -First 1
    if ($line -match "^ADMIN_TOKEN=(.+)$") { $adminToken = $Matches[1].Trim() }
}
if ($adminToken) {
    $resetDone = $false
    foreach ($attempt in 1..3) {
        try {
            $headers = @{ "X-Admin-Token" = $adminToken }
            $res = Invoke-WebRequest -Uri "http://127.0.0.1:8081/admin/reset-active-trade?silent=true" -Method POST -Headers $headers -TimeoutSec 15 -UseBasicParsing
            if ($res.StatusCode -eq 200) {
                $j = $res.Content | ConvertFrom-Json
                Write-Host "  Reset OK: $($j.rows_cleared) trade(s) efface(s)"
                $resetDone = $true
                break
            } else { Write-Host "  Reset: status $($res.StatusCode) (tentative $attempt/3)" }
        } catch {
            Write-Host "  Reset: $($_.Exception.Message) (tentative $attempt/3, API peut-etre en demarrage)"
            if ($attempt -lt 3) { Start-Sleep -Seconds 3 }
        }
    }
    if (-not $resetDone) { Write-Host "  Reset echoue apres 3 tentatives" }
} else {
    Write-Host "  ADMIN_TOKEN absent (skip)"
}

# 3) Vider __pycache__ pour forcer rechargement du code
Write-Host "`n3. Nettoyage __pycache__..."
Get-ChildItem -Path $CORE_DIR -Include __pycache__ -Recurse -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  __pycache__ supprime"

# 3) Redemarrer services NSSM (si installes)
$NSSM = "C:\tools\nssm\nssm.exe"
if (Test-Path $NSSM) {
    Write-Host "`n4. Restart services..."
    # Forcer GO_MIN_SCORE=90 et A_PLUS_MIN_SCORE=90 pour trader-core (setups A+ uniquement sur Telegram)
    $stCore = & $NSSM status trader-core 2>$null
    if ($LASTEXITCODE -eq 0) {
        $extra = & $NSSM get trader-core AppEnvironmentExtra 2>$null
        if (-not $extra) { $extra = "" }
        $extra = $extra.Trim()
        if ($extra -and $extra -notmatch "GO_MIN_SCORE=") { $extra = "$extra GO_MIN_SCORE=90 A_PLUS_MIN_SCORE=90" }
        elseif (-not $extra) { $extra = "GO_MIN_SCORE=90 A_PLUS_MIN_SCORE=90" }
        & $NSSM set trader-core AppEnvironmentExtra $extra 2>$null
    }
    $services = @("trader-core", "trader-runner")
    if (-not $SkipBridge) { $services = @("mt5-bridge") + $services }
    if ($SkipBridge) { Write-Host "  (mt5-bridge non redémarre - SkipBridge)" }
    foreach ($svc in $services) {
        $st = & $NSSM status $svc 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  Stopping $svc..."
            & $NSSM stop $svc 2>$null
            Start-Sleep -Seconds 3
            Write-Host "  Starting $svc..."
            & $NSSM start $svc 2>$null
            if ($LASTEXITCODE -eq 0) { Write-Host "  $svc OK" } else { Write-Host "  $svc start failed" }
        } else {
            Write-Host "  $svc not installed (skip)"
        }
    }
} else {
    Write-Host "`n3. NSSM non trouve - redemarrage manuel:"
    Write-Host "   - MT5 bridge: python -m uvicorn services.mt5_bridge.main:app --host 127.0.0.1 --port 8080"
    Write-Host "   - API: run_core.bat"
    Write-Host "   - Runner: python -m app.scripts.runner_loop --interval 300"
}

# 4) Health check + version
Write-Host "`n4. Health check..."
Start-Sleep -Seconds 5
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8081/health" -TimeoutSec 5 -UseBasicParsing
    if ($r.StatusCode -eq 200) {
        $json = $r.Content | ConvertFrom-Json
        $ver = $json.version
        Write-Host "API OK (port 8081) - version: $ver"
    } else {
        Write-Host "API: status $($r.StatusCode)"
    }
} catch {
    Write-Host "API: $($_.Exception.Message)"
}

Write-Host "`n=== Pret pour Telegram ==="
