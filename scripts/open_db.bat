@echo off
REM Ouvre la base SQLite (DB Browser for SQLite si installe, sinon sqlite3)
set DB=c:\trader-assistant-core\data\trader_assistant.db
if exist "C:\Program Files\DB Browser for SQLite\DB Browser for SQLite.exe" (
    start "" "C:\Program Files\DB Browser for SQLite\DB Browser for SQLite.exe" "%DB%"
) else if exist "C:\Program Files (x86)\DB Browser for SQLite\DB Browser for SQLite.exe" (
    start "" "C:\Program Files (x86)\DB Browser for SQLite\DB Browser for SQLite.exe" "%DB%"
) else (
    echo DB: %DB%
    echo Pour une interface graphique, installez "DB Browser for SQLite": https://sqlitebrowser.org/
    sqlite3 "%DB%" .schema
)
