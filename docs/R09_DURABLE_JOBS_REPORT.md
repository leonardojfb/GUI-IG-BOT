# R09 Durable Jobs

Fecha: 2026-09-17

## Contrato implementado

- `durable_jobs.py` persiste jobs, pasos y eventos con la conexion SQLite existente.
- `create_job()` guarda recipes versionadas, steps ordenados, dependencias, intentos y backoff.
- `claim_next_step()` exige dependencias satisfechas, marca `blocked` ante fallo/cancelacion y entrega leases exclusivos con `lease_token`.
- `record_step_checkpoint()` conserva progreso; `complete_step()` guarda resultados; `fail_step()` aplica retry/backoff.
- `recover_expired_steps()` recupera leases vencidos de forma idempotente y conserva el backoff configurado.
- `job_runner.py` ejecuta handlers inyectados y permite `recover_and_run()` tras reinicio.

## Compatibilidad

- Los modulos son import-safe y se incluyen en release normal/updater, fuera del bootstrap.
- `video_transform_logs` y productores legacy permanecen intactos; R10 conectara sus handlers reales.

## Verificacion

- Focal R09/release: `25 passed`.
- Suite completa: `469 passed, 2 skipped, 7 subtests passed`.
- Compilacion: `py -m py_compile durable_jobs.py job_runner.py`.

## Limites

R09 no valida FFmpeg real, productores Tandas/Forge/Edicion ni publicacion externa. Esas integraciones corresponden a R10-R15.
