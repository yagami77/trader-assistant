# Lance MT5 en Session 0 apres 30 s (pour alignement avec bridge NSSM).
# Appele par la tache MT5-AtStartup-Session0.
$MT5_EXE = "C:\Program Files\MetaTrader 5\terminal64.exe"
if (-not (Test-Path $MT5_EXE)) {
    $MT5_EXE = "${env:ProgramFiles(x86)}\MetaTrader 5\terminal64.exe"
}
Start-Sleep -Seconds 30
if (Test-Path $MT5_EXE) {
    $workDir = Split-Path $MT5_EXE
    Start-Process -FilePath $MT5_EXE -WorkingDirectory $workDir -WindowStyle Hidden
}
