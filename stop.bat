@echo off
rem ============================================================
rem  Stops the server started by the launcher .bat next to this file.
rem
rem  ASCII ONLY - not even in comments. cmd reads a .bat with the
rem  console code page (949 on Korean Windows); UTF-8 Korean bytes
rem  desync the parser and it starts running fragments of words as
rem  commands. All messages live in scripts/stop.py instead.
rem
rem  stop.py only uses the standard library, so any Python works:
rem  the venv may well be broken when you need to stop the server.
rem ============================================================
cd /d "%~dp0"
title API Manager - stop

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "scripts\stop.py"
) else (
    py -3 "scripts\stop.py"
    if errorlevel 1 python "scripts\stop.py"
)

echo.
pause
