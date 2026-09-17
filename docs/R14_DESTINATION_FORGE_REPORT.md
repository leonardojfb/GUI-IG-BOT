# R14 Forge por destinos

Fecha: 2026-09-17

## Alcance validado

- `preview_destination_forge()` expande cada video por cuenta, contenedor,
  perfil y cantidad de copias.
- La cuenta se normaliza case-insensitive y el lane se congela como
  `contenedor:perfil` para evitar colisiones entre destinos incompatibles.
- `reserve_destination_preview()` delega en la reserva atomica R08, con TTL,
  deteccion de conflicto y comprobacion de cobertura del preview.
- El modulo no renderiza ni publica: la reserva es un gate previo al job R10.
- `build_destination_forge_job_spec()` y `submit_destination_forge_job()` convierten
  assignments validados en steps `forge.copy` R09 con salida aislada por
  cuenta/contenedor/perfil.
- `reconcile_destination_reservation()` comprueba cobertura exacta y libera la
  reserva despues de que el consumidor procese el job; antes guarda una fila
  idempotente por assignment (incluido `copy_number`) en
  `destination_forge_history`; ambas tablas reparan también una instalación
  parcialmente migrada que conserve la unicidad antigua.
- La GUI Forge expone un bloque opt-in con filas
  `cuenta|contenedor|perfil|copias`, muestra las asignaciones y permite
  reservar el preview con confirmacion; el preview no crea jobs ni archivos.
- La misma tarjeta puede cargar un snapshot read-only de ios-remote y mostrar
  su identidad antes de preparar destinos; el fallback manual sigue visible.
- Si hay snapshot cargado, `bind_destinations_to_snapshot()` exige que cada
  cuenta/perfil resuelva a un único contenedor y conserva `remote_container_id`,
  `profile_version` y `snapshot_hash` en el assignment y el job.
- Release/updater incluyen el contrato sin modificar bootstrap.

## Limites

La consulta real de perfiles ios-remote, la validacion de snapshots y la
confirmacion visual post-render quedan pendientes. El historial registra la
reconciliacion local de la reserva, no prueba un render ni un dispositivo
fisico.
