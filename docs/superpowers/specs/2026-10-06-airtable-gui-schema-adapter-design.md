# Adaptador GUI para el esquema real de Airtable

## Objetivo

Permitir que el espejo GUI → Airtable use el formato existente de la tabla `CUENTAS EVE`, evitando que un PATCH sea rechazado por diferencias de tipo o por opciones vacías.

## Diseño aprobado

La base local conserva sus valores actuales (`0/1`, texto y cadenas vacías). Antes de construir el plan de espejo, la integración lee el esquema de la tabla y transforma los valores al tipo real de cada columna:

- `singleSelect`: solo se envían opciones existentes; los valores vacíos se omiten.
- `Trials desbloqueados`: `0/1` se convierte a la opción equivalente de Airtable (`No`/`Sí`, según las opciones reales).
- `singleLineText`/`multilineText`: se envían como texto.
- `url`: se envía solo una URL válida y se omite si está vacía.

Si una cuenta contiene un valor que no existe entre las opciones de un `singleSelect`, la sincronización falla antes de cualquier escritura y muestra el campo, el valor y la cuenta afectada.

## Alcance

- Modificar `airtable_sync.py` para leer y aplicar el esquema al plan GUI → Airtable.
- Añadir pruebas en `tests/test_airtable_sync.py` para el caso real de PATCH rechazado y para valores no mapeables.
- No cambiar la base SQLite, no borrar registros remotos automáticamente y no tocar otros flujos Airtable.

## Verificación

- Ejecutar primero una prueba nueva en rojo que reproduzca el payload incompatible.
- Ejecutar la prueba enfocada de Airtable y después la compilación de `airtable_sync.py` y `gui_premium_v7.py`.
- La verificación local no se considerará prueba de una mutación real hasta ejecutar el botón contra Airtable y confirmar el resultado remoto.
