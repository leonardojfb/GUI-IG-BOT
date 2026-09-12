# Actualizaciones de la GUI

La aplicacion se abre mediante `Abrir GUI.bat` o `launch_gui.bat`. El launcher consulta `update_config.json`, descarga el ZIP indicado por el manifiesto, verifica SHA-256 y luego abre `gui_premium_v7.py`.

Tambien puedes configurar el manifiesto y el token desde la pestaña `Actualizaciones` de la GUI. El token se muestra enmascarado y se guarda solo en el archivo local del cliente.

## Configuracion inicial

1. Instala Python 3.11 o superior en la PC del socio.
2. Ejecuta una vez `Instalar GUI.bat` para crear `.venv` e instalar `requirements.txt`.
3. Copia `update_config.example.json` sobre `update_config.json`.
4. Usa el manifiesto de `https://raw.githubusercontent.com/leonardojfb/GUI-IG-BOT/main/release-manifest.json`.
5. Si el repositorio es privado, agrega un token de solo lectura en `access_token` o usa la variable de entorno `IG_GUI_UPDATE_TOKEN`. No subas ese archivo con el token a GitHub.

Si `manifest_url` esta vacia o no hay internet, la GUI se abre con la version local.

## Diagnostico local

Antes de publicar o al revisar una instalacion de cliente, ejecuta:

```powershell
py updater.py --healthcheck
```

El comando no consulta internet ni importa la GUI. Devuelve JSON con version
local, canal, manifiesto resuelto, archivos faltantes y cualquier bloqueo
`RECOVERY_REQUIRED` por `.update_status.json` o `.update_journal.json`.

## Publicar una version

1. Cambia `version` y `release_date` en `version.json`.
2. Ejecuta `powershell -ExecutionPolicy Bypass -File .\build_release.ps1 -Notes "Descripcion breve"`.
3. Publica `releases\MetodoIG-vX.Y.Z.zip` en GitHub Releases.
4. Sube el ZIP como asset de la release `vX.Y.Z` en GitHub y publica `release-manifest.json` en la URL configurada. Para repositorios privados el actualizador resuelve el asset por la API de GitHub usando el token; no modifica la URL a mano.

Para la primera entrega puedes ejecutar el build con `-IncludeClientDatabase`
para incluir una plantilla limpia `organizador.default.db`. No empaquetes
`update_config.json`: cada cliente conserva su configuracion local de canal,
manifiesto y token. Las releases posteriores no incluyen ni reemplazan
`organizador.db`.

Las releases normales no contienen `organizador.db`, estados de Telegram, historiales, configuraciones, cuentas, calendarios ni videos. Solo la entrega inicial puede incluir `organizador.db` mediante `-IncludeClientDatabase`; el actualizador nunca escribe ese archivo ni los demás datos del socio.
