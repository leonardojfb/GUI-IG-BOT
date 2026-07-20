@echo off
setlocal
cd /d "%~dp0"

rem Prefer the app's own environment.  Instalar GUI.bat puts customtkinter,
rem requests and tzdata here; the system Python normally does not have them.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import customtkinter, requests" >nul 2>&1
    if not errorlevel 1 (
        start "" ".venv\Scripts\python.exe" "%~dp0launcher.py"
        exit /b
    )
)

rem Ask the working `python` command for its real interpreter.  This avoids
rem the broken local venv and the WindowsApps pythonw.exe Store stub.
for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"

if not defined PYTHON_EXE (
    start "" py -3 launcher.py
    exit /b
)

rem launcher.py immediately starts the GUI with the matching pythonw.exe.
rem Starting it with python.exe here is intentional: it is reliable and the
rem small command window closes as soon as the launcher detaches.
start "" "%PYTHON_EXE%" "%~dp0launcher.py"
exit /b
