# R00 launch and import inventory

Fecha: 2026-09-11

Este inventario fija la superficie minima que una release R00 debe respetar
antes de publicar cambios por updater. El objetivo es que un cliente que abre el
launcher no ejecute codigo inesperado, no pierda datos locales y no quede con un
paquete incompleto.

## BAT/CMD

| Archivo | Rol | Usuario esperado | Riesgo de update | Contrato R00 |
| --- | --- | --- | --- | --- |
| `Abrir GUI.bat` | Entrada normal para cliente. Busca `.venv`, valida `customtkinter`/`requests`, resuelve `python.exe` real y abre `launcher.py`. | Usuario final | Alto: si apunta a otro Python o carpeta, el update no corre donde el usuario cree. | Debe permanecer en el ZIP normal. No debe escribir datos de usuario ni cambiar version. |
| `Instalar GUI.bat` | Instalacion inicial/reparacion local. Crea `.venv`, instala `requirements.txt` y valida FFmpeg/FFprobe empaquetados. | Usuario final o soporte | Medio: toca dependencias locales, pero no DB ni calendario. | Puede ejecutarse manualmente. No debe sobrescribir `organizador.db`, `update_config.json`, historiales ni calendarios. |
| `launch_gui.bat` | Launcher alternativo heredado. Usa `.venv` si existe, luego `python`/`py`, llama `launcher.py` y deja `pause`. | Soporte/desarrollo | Medio: funcional, pero muestra consola y pausa. | Mantener por compatibilidad; `Abrir GUI.bat` sigue siendo el entrypoint preferido. |
| `preparar_logistica.bat` | Wrapper heredado para `preparar_logistica.ps1` con carpeta/categoria opcional. | Soporte/desarrollo | Medio: depende de un `.ps1` no incluido en `$ReleaseFiles` normal. | No debe tratarse como entrypoint de cliente hasta decidir si `preparar_logistica.ps1` entra al paquete o se retira del flujo. |

## Python release import surface

| Archivo | Import seguro | Efecto top-level observado | Riesgo R00 | Contrato R00 |
| --- | --- | --- | --- | --- |
| `Organizador.py` | Parcial | Llama `ensure_stdout_utf8()` al importar; define rutas desde `__file__`. No abre DB top-level. | Bajo/medio: muta encoding del proceso y sus rutas dependen del modulo cargado. | Apto para import en tests/launcher si se parchean `base_dir`, `source_root`, `output_root` antes de operar. |
| `airtable_sync.py` | Si | Solo define tipos/helpers; requests se ejecuta por funcion. | Bajo | Mantener side-effect-light. |
| `calendar_manifest.py` | Si | Solo define constantes/helpers. | Bajo | Lector/writer compatible; no debe hacer I/O al importar. |
| `cleaner.py` | Si | Define helpers de limpieza; acciones bajo funciones. | Bajo | No ejecutar limpieza en import. |
| `console_encoding.py` | Si | Solo define helper. | Bajo | Puede importarse temprano. |
| `database.py` | Si | Define `DB_PATH` desde `__file__`; no abre conexion hasta `DatabaseManager()`. | Medio: la ruta por defecto cambia segun instalacion importada. | Tests y procesos temporales deben parchear `database.DB_PATH` antes de crear `DatabaseManager()`. |
| `gui_organizador.py` | Parcial | Importa GUI/deps; revisar antes de usar como entrada. | Medio | No es entrypoint cliente R00. |
| `gui_premium_v7.py` | No ligero | Importa Tk/CustomTkinter, instala patch de dropdown, llama `ensure_stdout_utf8()`, `ctk.set_appearance_mode()` y `ctk.set_default_color_theme()`. | Alto: importarlo inicializa estado UI global y puede requerir display/deps. | `launcher.py` debe ejecutarlo como proceso GUI; tests unitarios solo importan con entorno controlado. |
| `gui_unificada.py` | Parcial | GUI heredada; depende de Tk/CustomTkinter y estado local. | Medio/alto | Mantener por compatibilidad, no usar como launcher principal. |
| `launcher.py` | Si | Define rutas y helpers; no abre GUI salvo `main()`. | Bajo | Entry Python oficial. `main()` bloquea si `RECOVERY_REQUIRED`. |
| `metadata_pool.py` | Si | Define constantes FFmpeg y pools; no ejecuta FFmpeg al importar. | Bajo | Apto para import. |
| `organizador_simple.py` | Parcial | Script/GUI heredado; revisar antes de reactivar. | Medio | No usar como entrypoint automatico. |
| `organizadortg.py` | No ligero | Inserta su carpeta en `sys.path`, llama `ensure_stdout_utf8()`, calcula rutas, abre `db = DatabaseManager()` al importar y contiene token Telegram embebido. | Alto: abre SQLite top-level y arrastra estado local; credencial embebida sigue siendo superficie sensible. | En tests hay que cerrar/reabrir `organizadortg.db` contra DB temporal. En R01/R02 conviene mover DB lazy y sacar credenciales de source antes de release publica. |
| `render_performance.py` | Si | Define mediciones/config; sin I/O critico top-level observado. | Bajo | Apto para import. |
| `social_publishing.py` | Si | Define enums/helpers de destinos manuales. | Bajo | Debe permanecer side-effect-free. |
| `styles/__init__.py` | Si | Paquete vacio/ligero. | Bajo | Apto para import. |
| `styles/colors.py` | Si | Constantes de colores/tamanos. | Bajo | Apto para import. |
| `styles/components.py` | Parcial | Define componentes CustomTkinter; importa UI deps. | Medio | Importar solo donde ya se requiere GUI. |
| `telegram_core.py` | Si | Helpers Telegram sin envio top-level. | Bajo | Apto para import. |
| `trial_content.py` | Si | Helpers puros de Trials/calendario. | Bajo | Apto para import. |
| `updater.py` | Si | Define allowlists, excepciones y funciones; no aplica update salvo llamada explicita. | Bajo/medio: funciones escriben backup/status cuando se ejecutan. | Puede importarse desde launcher; `check_and_apply()` debe respetar `RECOVERY_REQUIRED`. |
| `vercuentas.py` | No | Crea `DatabaseManager()`, consulta tabla e imprime cuentas al importar. | Alto: importarlo ejecuta SQL y stdout. | No debe importarse desde GUI/launcher; si se conserva, usarlo solo como script manual o refactorizar bajo `main()`. |
| `video_editor.py` | Si | Define cache dir/lock y constantes; no crea cache hasta funciones. | Bajo | Apto para import. |
| `videos.py` | Parcial | Llama `ensure_stdout_utf8()`, define rutas desde `__file__`; no abre DB top-level. | Medio: rutas dependen del modulo cargado. | Tests y procesos temporales deben parchear `FOLDER_INPUTS`/`FOLDER_OUTPUT_ROOT` antes de render. |

## Riesgos a cerrar despues de R00

- `organizadortg.py` abre SQLite al importar. Esto ya esta mitigado en tests, pero
  es una deuda real para updates atomicos y healthchecks side-effect-free.
- `vercuentas.py` no es import-safe. Si alguna release futura lo importa desde UI
  o updater, ejecutara SQL e imprimira en startup.
- `preparar_logistica.bat` llama a `preparar_logistica.ps1`, pero ese script no
  forma parte del ZIP normal actual. Mantenerlo como herramienta heredada hasta
  decidir si se empaqueta o se retira.
- `gui_premium_v7.py` inicializa CustomTkinter al importar. Los checks de runtime
  del updater no deben importarlo directamente en modo headless.
