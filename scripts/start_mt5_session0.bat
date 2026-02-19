@echo off
REM Lance MT5 en Session 0 (SYSTEM) via le RACCOURCI connecte (terminal64.exe - Shortcut).
REM Appele par la tache MT5-AtStartup-Session0. Bridge NSSM = session 0.

set "MT5_WORKDIR=C:\MT5Portable"
set "SHORTCUT=%MT5_WORKDIR%\terminal64.exe - Shortcut.lnk"
set "MT5_EXE=%MT5_WORKDIR%\terminal64.exe"

timeout /t 30 /nobreak >nul

if exist "%SHORTCUT%" (
    start "" /D "%MT5_WORKDIR%" "%SHORTCUT%"
) else if exist "%MT5_EXE%" (
    start "" /D "%MT5_WORKDIR%" "%MT5_EXE%" /portable
) else (
    echo MT5 introuvable: raccourci ou %MT5_EXE%
    exit /b 1
)
exit /b 0
