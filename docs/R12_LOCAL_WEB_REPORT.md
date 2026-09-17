# R12 Web local

Fecha: 2026-09-17

## Alcance validado

- `LocalWebService` escucha únicamente en loopback por defecto y no inicia
  procesos durante el import.
- `/health` expone estado mínimo sin secretos.
- `/api/accounts`, `/api/content`, `/api/calendar` y `/api/history` exigen
  `Authorization: Bearer <token>` y responden JSON sin cache.
- La primera versión es read-only: no agrega endpoints POST/PUT/DELETE ni
  puede alterar cuentas, manifest, calendario o historial.
- El servidor usa solo la librería estándar, mantiene `Pillow` y la GUI fuera
  del camino de arranque y puede detenerse sin dejar un thread vivo.
- Release/updater incluyen el módulo de forma aditiva; bootstrap permanece
  compatible con instalaciones antiguas.
- La raíz sirve una shell navegable que carga las cuatro vistas por API con el
  token introducido en memoria del navegador; no persiste el token.
- `gui_premium_v7.py` expone `Abrir panel local` en Actualizaciones, inicia el
  servicio bajo demanda, copia el token temporal y lo detiene en cierre.
- Con `calendar_import_root` configurado, el panel ofrece
  `/api/calendar/import-preview` y `/api/calendar/import`: ambos exigen Bearer,
  el primero no escribe, y el segundo exige `confirm=true`, limita el destino a
  la raíz configurada y delega en la importación atómica R18.

## Verificacion

- `tests/test_local_web.py`: token obligatorio, health, cuatro modelos de
  lectura y apagado limpio.
- Prueba de release/updater agregada a `test_release_package_manifest.py`.

## Limites

No se declaran escrituras remotas ni publicación de plataforma. Las mutaciones
locales quedan limitadas al import de paquetes de calendario; reservas,
publicación y acciones sobre cuentas aún requieren comandos explícitos y
auditoría.
