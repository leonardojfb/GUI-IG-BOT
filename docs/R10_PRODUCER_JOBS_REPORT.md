# R10 Productores a Jobs

Fecha: 2026-09-17

## Adaptadores

- `producer_jobs.py` congela entradas de Tandas, Forge y Edicion en recipes `recipe_version=1` y steps deterministas.
- `build_tanda_job_spec()` crea un step por tanda y conserva carpetas P1/P2, roots y snapshot de rendimiento.
- `build_forge_job_spec()` crea un step por video/copia, conserva metadata iPhone, efectos, fuerza, overrides, output y `copy_number`.
- `build_editor_job_spec()` crea un step por video, conserva overlays, perfil, output y threads FFmpeg.
- `validate_video_profile()` centraliza dimensiones, duracion y aspect ratio usando el probe existente.
- `make_editor_handler()` valida entrada/salida, ejecuta `video_editor.render_video()`, registra transform log y reanuda si el output ya existe.
- `make_forge_handler()` valida entrada/salida, ejecuta `metadata_pool.apply_variant_and_metadata()`, registra params/perfiles y reanuda output existente.
- `make_tanda_handler()` delega en `videos.process_tandas()` dentro de un step duradero, limita temporalmente las rutas globales del modulo y las restaura siempre.
- `submit_tanda_job()`, `submit_forge_job()` y `submit_editor_job()` persisten estas recipes usando el contrato R09 y aceptan `idempotency_key`.

## Compatibilidad

- Ningun entrypoint legacy fue reemplazado. Los flujos actuales de GUI y scripts siguen funcionando como antes.
- El adaptador se distribuye en releases normales y updater, fuera del bootstrap.
- No se importan GUI, FFmpeg ni productores con efectos laterales desde `producer_jobs.py`.
- La ejecución es opt-in: un consumidor crea el job y pasa el handler a `job_runner.run_until_idle()` o `recover_and_run()`.

## Verificacion

- `py -m pytest -q tests/test_producer_jobs.py tests/test_durable_jobs.py tests/test_job_runner.py tests/test_r09_contract.py tests/test_release_package_manifest.py`: 32 passed.
- `py -m py_compile producer_jobs.py durable_jobs.py job_runner.py`.

## Limites

Los tests usan handlers y probes controlados. No se declara aquí un render FFmpeg de producción ni una ejecución contra una instalación real; R10 deja la integración durable lista para que la GUI/productores la habiliten de forma gradual.
