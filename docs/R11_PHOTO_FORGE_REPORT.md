# R11 Photo Forge

Fecha: 2026-09-17

## Alcance validado

- `photo_forge.py` congela inputs, perfil, variantes y nombres de salida en
  recipes `recipe_version=1` compatibles con R09.
- `render_photo_variant()` usa Pillow con operaciones versionadas: brillo,
  contraste, color, nitidez, rotacion, espejo, recorte, resize y escala de
  grises.
- La escritura es atomica mediante archivo temporal; una fuente corrupta o un
  render fallido no deja un output parcial promovido.
- `render_photo_preview()` produce una copia limitada a un area maxima y nunca
  modifica la fuente.
- `validate_image()` rechaza bytes corruptos, dimensiones insuficientes y
  relaciones de aspecto fuera de `instagram_post`/`instagram_story`.
- `make_photo_forge_handler()` permite reanudar outputs existentes y registra
  `process_kind=photo_forge` en `video_transform_logs`.
- Con `VaultStorage` inyectado, el output se importa como asset gestionado y se
  enlaza con el asset fuente mediante `vault.integration` y `VaultLineage`.
- `submit_photo_forge_job()` persiste el trabajo con idempotencia opcional.
- `gui_premium_v7.py` expone dentro de Forge una tarjeta Photo Forge con
  selección de imágenes, preview y generación explícita en `fotos_forge/`.

## Compatibilidad

- No se cambia ningún flujo legacy de video, Forge, Tandas o Edición.
- El módulo es import-safe: Pillow se importa dentro de las operaciones y no se
  crean carpetas ni tablas durante el import.
- `photo_forge.py` se incluye en release normal y updater, pero no en bootstrap.

## Verificacion

- `py -m pytest -q tests/test_photo_forge.py`: `4 passed`.
- Se agrega prueba de release/updater e inventario de importación.
- La tarjeta GUI usa el mismo motor Pillow y refresca el panel de logs después
  de generar; los botones de video Forge no cambian.

## Limites

Las pruebas usan imágenes sintéticas y no certifican todavía un lote de fotos
de producción ni una política de publicación externa. La firma perceptual y la
reserva anti-repetición entre cuentas quedan para R14/R17, cuando existan las
reglas de destinos y reutilización.
