@echo off
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
    echo No se encontro Python. Instala Python 3.11 o superior y vuelve a ejecutar este archivo.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno local...
    python -m venv .venv
    if errorlevel 1 (
        echo No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)
echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo No se pudieron instalar las dependencias.
    pause
    exit /b 1
)
if not exist "tools\ffmpeg\bin\ffmpeg.exe" (
    echo Falta tools\ffmpeg\bin\ffmpeg.exe. Descarga el ZIP completo de la release.
    pause
    exit /b 1
)
if not exist "tools\ffmpeg\bin\ffprobe.exe" (
    echo Falta tools\ffmpeg\bin\ffprobe.exe. Descarga el ZIP completo de la release.
    pause
    exit /b 1
)
echo Instalacion terminada. Ya puedes abrir Abrir GUI.bat.
pause
