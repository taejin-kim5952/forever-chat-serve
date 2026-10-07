@echo off
rem ============================================================
rem  Stops the api-manager server (port 18100) only.
rem
rem  ASCII ONLY - not even in comments. cmd reads a .bat with the
rem  console code page (949 on Korean Windows); UTF-8 Korean bytes
rem  desync the parser. All messages live in scripts/stop.py.
rem
rem  Kills only the process holding that one port, so stopping the
rem  MCP window never takes API Manager down with it.
rem
rem  stop.py only uses the standard library, so any Python works:
rem  the venv may well be broken when you need to stop the server.
rem ============================================================
cd /d "%~dp0"
title API Manager - stop 18100

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "scripts\stop.py" --port 18100
) else (
    py -3 "scripts\stop.py" --port 18100
    if errorlevel 1 python "scripts\stop.py" --port 18100
)

echo.
pause
