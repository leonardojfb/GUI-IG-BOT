@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        ".venv\Scripts\python.exe" launcher.py
        exit /b
    )
) 
where python >nul 2>&1
if not errorlevel 1 (
    python launcher.py
) else (
    py launcher.py
)
pause
