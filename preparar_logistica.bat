@echo off
setlocal

set "TARGET=%~1"
if not defined TARGET set "TARGET=%CD%"

set "CATEGORY=%~2"
if not defined CATEGORY set "CATEGORY=PROMO EVE"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0preparar_logistica.ps1" -Folder "%TARGET%" -Category "%CATEGORY%"
if errorlevel 1 (
    echo.
    echo Ocurrio un error. Revisa el mensaje anterior.
)
pause
