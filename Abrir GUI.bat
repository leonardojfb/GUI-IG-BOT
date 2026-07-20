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

rem 2) Derive pythonw from the working system python.  Do not resolve the
rem    WindowsApps pythonw.exe alias: it is a Store stub and exits silently.
for /f "usebackq delims=" %%P in (`python -c "import sys; print(sys.executable)" 2^>nul`) do set "PYTHON_EXE=%%P"
if defined PYTHON_EXE (
    for %%P in ("%PYTHON_EXE%") do set "PYW=%%~dpPpythonw.exe"
    if exist "%PYW%" (
        start "" "%PYW%" "%~dp0launcher.py"
        exit /b
    )
)

rem 3) Last resort: the py launcher in windowless mode.
start "" py -w launcher.py
exit /b
