@echo off
rem ============================================================
rem  Double-click launcher - mcp-manager pack (port 18101).
rem
rem  ASCII ONLY on purpose. cmd reads a .bat with the console code
rem  page (949 on Korean Windows), so UTF-8 Korean text breaks the
rem  parser - lines get split and labels are skipped. All messages
rem  and logic live in scripts/launch.py instead.
rem
rem  One .bat per pack. If a single launcher started both servers,
rem  one of them could die unnoticed and you could not tell which
rem  window serves which domain.
rem ============================================================
cd /d "%~dp0"
title MCP Server - port 18101

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "scripts\launch.py" mcp-manager --port 18101
) else (
    rem First run: no venv yet. Python 3.11 builds it - 3.12+ has no
    rem chroma-hnswlib wheel and needs a C++ compiler.
    py -3.11 "scripts\launch.py" mcp-manager --port 18101
    if errorlevel 1 (
        echo.
        echo  [ERROR] Python 3.11 not found.
        echo          Run:  py install 3.11
        echo.
    )
)

echo.
pause
