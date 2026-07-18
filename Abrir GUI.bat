@echo off
cd /d "%~dp0"
rem Launch windowless (pythonw) and detach so NO console window ever appears.

rem 1) Prefer the venv's pythonw if the venv actually works.
if exist ".venv\Scripts\pythonw.exe" (
    ".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        start "" ".venv\Scripts\pythonw.exe" launcher.py
        exit /b
    )
)

rem 2) Otherwise use the system pythonw (still windowless).
for %%I in (pythonw.exe) do if not defined PYW set "PYW=%%~$PATH:I"
if defined PYW (
    start "" "%PYW%" launcher.py
    exit /b
)

rem 3) Last resort: the py launcher in windowless mode.
start "" py -w launcher.py
exit /b
