# Telegram: exclusión global por origin publicado

## Objetivo

Evitar que Telegram publique cualquier variación de un video cuyo `origin` lógico ya fue marcado como `Publicado`, incluso si la variación tiene otro archivo, otro hash, otra cuenta o pertenece a otra tanda.

La comparación exacta por `SHA-256` se conserva para compatibilidad y para detectar la misma variación.

## Comportamiento

- Se omite un video si su SHA-256 está en `Videos publicados`.
- También se omite si su identidad persistida de `origin` ya está publicada.
- La regla es global: no depende de cuenta, tanda ni topic.
- Los registros históricos que solo contienen `SHA-256` siguen siendo válidos.
- Si Airtable no puede verificarse, Telegram mantiene el fail-closed actual y no envía videos.

## Identidad y flujo de datos

1. El calendario persistirá en cada entrada la identidad estable del origin asociada a la variación.
2. Telegram calculará el hash del archivo y obtendrá un identificador compacto derivado de esa identidad persistida.
3. El botón `Publicado` transportará el hash y el identificador compacto sin superar el límite de `callback_data` de Telegram.
4. El webhook persistirá en Airtable el `SHA-256` y el identificador/valor de origin junto con los datos de trazabilidad existentes.
5. La lectura de Airtable devolverá ambos conjuntos: hashes publicados y origins publicados.
6. `execute_telegram_plan()` filtrará antes de crear topics o jobs de envío.

La identidad canónica será la existente en el historial de transformación (`source_identity`/identidad persistida equivalente), no una reconstrucción basada únicamente en P1/P2 ni en el nombre visible del archivo.

## Compatibilidad y seguridad

- Se conserva el formato antiguo `pub:<hash>` para callbacks existentes.
- Los callbacks nuevos usarán un formato compacto validado estrictamente.
- El webhook no marcará el mensaje como publicado si no puede guardar el registro completo.
- El identificador compacto debe tener colisiones prácticamente imposibles y el valor canónico persistido debe quedar trazable en Airtable.

## Pruebas de aceptación

- Misma variación y mismo hash: se omite.
- Misma origin con otra variación/hash: se omite.
- Origin distinto aunque comparta cuenta, tanda o nombre parcial: se envía.
- Registro antiguo de Airtable solo con hash: continúa omitiendo por hash.
- Origin publicado en una cuenta: se omite en todas las demás cuentas.
- Error de Airtable: no se crean topics ni se envían videos.
- Callback antiguo y callback nuevo: ambos son aceptados según sus datos disponibles.

## Alcance

Incluye el manifiesto de calendario, el planificador Telegram, el lector Airtable, el webhook Railway y sus pruebas/documentación. No cambia las reglas de Logística por Cuentas ni el historial anti-colisión de P1/P2.
