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
| `catalog/__init__.py` | Si | Solo declara el paquete. | Bajo | Apto para import. |
| `catalog/service.py` | Si | Define `CatalogService`; no abre DB ni ejecuta migraciones hasta instanciar/llamar metodos. | Bajo | Servicio R03 sobre `DatabaseManager`; mantiene wrappers legacy hasta migrar consumidores. |
| `captions/__init__.py` | Si | Solo reexporta modelos/servicios. | Bajo | Apto para import; no abre DB ni archivos. |
| `captions/importer.py` | Si | Define parser/preview de TXT; no lee archivos hasta `preview_txt()`. | Bajo | Parser unico R05 para captions por parrafos y bloques historicos. |
| `captions/service.py` | Si | Define `CaptionService`; no abre DB hasta instanciar con `DatabaseManager`. | Bajo/medio | Servicio R05 para pools, versiones, snapshots, bindings y migracion conservadora. |
| `vault/__init__.py` | Si | Solo declara el paquete. | Bajo | Apto para import. |
| `vault/backfill.py` | Si | Define backfill de referencias; no escanea DB ni archivos hasta llamada explicita. | Bajo/medio | R04 registra referencias historicas externas sin copiar bytes durante update. |
| `vault/calendar_usage.py` | Si | Define registro idempotente de usos desde manifest; no abre DB hasta llamar funciones. | Bajo/medio | R06 enlaza calendario con usos Vault cuando ya existe asset resoluble; no crea archivos ni cambia manifest. |
| `vault/integration.py` | Si | Define enlace explicito entre transform logs y Vault; no importa archivos hasta llamada explicita. | Bajo/medio | R04 permite registrar outputs gestionados despues de render confirmado. |
| `vault/lineage.py` | Si | Define linaje y usos de assets; no abre DB hasta instanciar `VaultLineage`. | Bajo/medio | R06 registra derivaciones y usos append-only sin mover archivos ni calendarizar por si mismo. |
| `vault/migration.py` | Si | Define plan/ejecucion explicita de migracion externa a managed; no copia hasta llamada explicita. | Bajo/medio | R04 estima bytes y migra ubicaciones seleccionadas conservando referencias externas. |
| `vault/query.py` | Si | Define consultas y membresias de biblioteca; no abre DB hasta instanciar/llamar metodos. | Bajo | Servicio R04 para familias, colecciones y busqueda paginada. |
| `vault/reuse.py` | Si | Define auditoria de candidatos por firmas y usos; no abre DB hasta instanciar/llamar metodos. | Bajo/medio | R06 reporta posibles reutilizaciones sin bloquear, mover archivos ni modificar calendario. |
| `vault/signatures.py` | Si | Define firmas auditables de assets; no abre DB ni lee archivos hasta instanciar/llamar metodos. | Bajo/medio | R06 guarda firmas tecnicas y busquedas por firma sin decidir reutilizacion automaticamente. |
| `vault/storage.py` | Si | Define hash/storage helpers; no lee ni copia archivos hasta llamar metodos. | Bajo/medio | Servicio R04; import gestionado usa copia temporal y promocion atomica. |
| `vault/thumbnails.py` | Si | Define cache de miniaturas; Pillow se importa solo al generar imagenes. | Bajo/medio | R04 crea thumbnails de imagen y reporta corruptos/sin soporte sin romper biblioteca. |
| `cleaner.py` | Si | Define helpers de limpieza; acciones bajo funciones. | Bajo | No ejecutar limpieza en import. |
| `console_encoding.py` | Si | Solo define helper. | Bajo | Puede importarse temprano. |
| `database.py` | Si | Define `DB_PATH` desde `__file__`; no abre conexion hasta `DatabaseManager()`. | Medio: la ruta por defecto cambia segun instalacion importada. | Tests y procesos temporales deben parchear `database.DB_PATH` antes de crear `DatabaseManager()`. |
| `gui_organizador.py` | Parcial | Importa GUI/deps; revisar antes de usar como entrada. | Medio | No es entrypoint cliente R00. |
| `gui_premium_v7.py` | No ligero | Importa Tk/CustomTkinter, instala patch de dropdown, llama `ensure_stdout_utf8()`, `ctk.set_appearance_mode()` y `ctk.set_default_color_theme()`. | Alto: importarlo inicializa estado UI global y puede requerir display/deps. | `launcher.py` debe ejecutarlo como proceso GUI; tests unitarios solo importan con entorno controlado. |
| `gui_unificada.py` | Parcial | GUI heredada; depende de Tk/CustomTkinter y estado local. | Medio/alto | Mantener por compatibilidad, no usar como launcher principal. |
| `launcher.py` | Si | Define rutas y helpers; no abre GUI salvo `main()`. | Bajo | Entry Python oficial. `main()` bloquea si `RECOVERY_REQUIRED`. |
| `manifest_migration_cli.py` | Si | Define parser CLI y helpers; no migra manifest salvo `main()`/comando explicito. | Bajo/medio | Herramienta R07 para preview/apply de migracion v1->v2; debe permanecer fuera de bootstrap y dentro de release normal. |
| `shared_planner.py` | Si | Solo define el preview puro del planificador; no abre DB, no escribe archivos y no inicia servicios al importar. | Bajo | Contrato R08 para integrar Por Tandas y Por Cuentas gradualmente; debe permanecer fuera de bootstrap y dentro de release normal. |
| `shared_planner_sources.py` | Si | Define lectores read-only de cuentas y tandas; no modifica SQLite ni filesystem. | Bajo | Adaptador R08 para alimentar previews con fuentes concretas; debe permanecer fuera de bootstrap y dentro de release normal. |
| `shared_planner_apply.py` | Si | Solo transforma assignments a un preview de manifest v2; no escribe por si mismo. | Bajo | R08 exige confirmacion y revision protegida del manifest antes de aplicar. |
| `planner_reservations.py` | Si | Solo define funciones; crea su tabla cuando se solicita una reserva explicita. | Bajo/medio | R08 usa SQLite con TTL y conflicto atomico; fuera de bootstrap y dentro de release normal. |
| `durable_jobs.py` | Si | Solo define la maquina de estados; crea tablas unicamente por `ensure_job_schema()`. | Bajo/medio | R09 persiste recipes, steps, leases, checkpoints y eventos sin mutar DB al importar. |
| `job_runner.py` | Si | Solo define handlers/executor; no inicia workers al importar. | Bajo | R09 ejecuta jobs solo cuando un consumidor invoca `run_until_idle()` o `recover_and_run()`. |
| `producer_jobs.py` | Si | Define recipes y handlers opt-in; no ejecuta Tandas, Forge ni FFmpeg al importar. | Bajo/medio | R10 conecta productores solo mediante `submit_*_job()` y `job_runner`; entrypoints legacy permanecen intactos. |
| `photo_forge.py` | Si | Define recipes y funciones Pillow lazy; no abre GUI, DB ni archivos al importar. | Bajo/medio | R11 ejecuta variantes solo mediante `render_*()` o `job_runner`; la fuente no se sobrescribe. |
| `local_web.py` | Si | Define servidor loopback y rutas read-only; no inicia servidor al importar. | Bajo/medio | R12 solo escucha cuando `LocalWebService.start()` es invocado y exige Bearer token para datos. |
| `metadata_pool.py` | Si | Define constantes FFmpeg y pools; no ejecuta FFmpeg al importar. | Bajo | Apto para import. |
| `organizador_simple.py` | Parcial | Script/GUI heredado; revisar antes de reactivar. | Medio | No usar como entrypoint automatico. |
| `organizadortg.py` | No ligero | Inserta su carpeta en `sys.path`, llama `ensure_stdout_utf8()`, calcula rutas, abre `db = DatabaseManager()` al importar y contiene token Telegram embebido. | Alto: abre SQLite top-level y arrastra estado local; credencial embebida sigue siendo superficie sensible. | En tests hay que cerrar/reabrir `organizadortg.db` contra DB temporal. En R01/R02 conviene mover DB lazy y sacar credenciales de source antes de release publica. |
| `render_performance.py` | Si | Define mediciones/config; sin I/O critico top-level observado. | Bajo | Apto para import. |
| `social_publishing.py` | Si | Define enums/helpers de destinos manuales. | Bajo | Debe permanecer side-effect-free. |
| `styles/__init__.py` | Si | Paquete vacio/ligero. | Bajo | Apto para import. |
| `styles/colors.py` | Si | Constantes de colores/tamanos. | Bajo | Apto para import. |
| `styles/components.py` | Parcial | Define componentes CustomTkinter; importa UI deps. | Medio | Importar solo donde ya se requiere GUI. |
| `telegram_core.py` | Si | Helpers Telegram sin envio top-level; Pyrogram se importa de forma lazy al crear el cliente. | Bajo | Apto para import en runtime limpio sin instalar dependencias heredadas. |
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
