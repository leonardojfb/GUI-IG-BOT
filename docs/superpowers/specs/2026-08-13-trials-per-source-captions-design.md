# Trials activos y captions por video fuente

## Objetivo

Permitir que una misma cuenta, conservando su categoría operativa (`main`,
`SPAM`, etc.), reciba contenido normal y contenido Trial. Cada copia de un
video fuente de una tanda Trial debe enviarse a Telegram con exactamente el
mismo caption que se cargó para esa fuente.

## Decisiones

- `TRIALS` deja de representar una categoría de cuenta para este flujo.
- Una cuenta habilitada conserva `account_type` y suma el estado persistido
  `trials_active`.
- Forge tendrá los modos `Normal` y `Trials`. El modo Trials produce una tanda
  registrada explícitamente como Trial, conservando el formato de salida
  `fuente__cNN.ext` ya usado por Forge.
- Logística tendrá una subpestaña `Trials`. Solo podrá elegir tandas Trial y
  cuentas con `trials_active`.
- Trials se calendarizará en una raíz separada de `CALENDARIO_POSTEO`, sin
  alterar ni reemplazar el calendario normal.
- Telegram reutilizará la infraestructura existente de topics Trial, pero
  identificará el flujo por el calendario/tanda Trial, no por el texto de la
  categoría o del username. Cada cuenta tendrá un topic Trial separado del
  topic normal: `TRIALS - @<username> [<categoría>]`.

## Persistencia

La migración no destructiva agrega:

- `virtual_accounts.trials_active INTEGER NOT NULL DEFAULT 0`.
- Una marca de tanda Trial, separada de `batch_tandas` si resulta más seguro
  para compatibilidad con las tandas existentes.
- Una tabla de captions Trial con clave única `(tanda_name, source_key)` y el
  texto del caption. `source_key` es la raíz determinista de Forge, obtenida
  al remover únicamente el sufijo `__cNN` del nombre de salida.

No se migran, renombran ni borran las cuentas históricas cuya categoría o
username contienen `trial`; el nuevo flujo no las seleccionará implícitamente.

## Interfaz y flujo

1. En Cuentas, el usuario activa o desactiva `TRIALS ACTIVOS` sin cambiar la
   categoría ni la VA.
2. En Forge > Trials, carga los videos fuente, define copias y procesa la tanda.
   Forge sigue guardando el registro fuente/salida que ya existe.
3. En Logística > Trials, cada cuenta con `TRIALS ACTIVOS` elige su propia
   tanda. La interfaz agrega todas las fuentes de las tandas seleccionadas,
   usando una clave `(tanda, fuente)` para mostrar cada grupo `__cNN` una vez,
   con miniatura y un campo multilínea para pegar el caption.
4. Guardar persiste el texto por fuente. La previsualización y calendarización
   se bloquean con una lista clara de fuentes faltantes si alguna no tiene
   caption.
5. La distribución Trial usa las reglas existentes de Logística pero escribe
   exclusivamente en el calendario Trial para las cuentas activas. Cada
   archivo Forge solo puede calendarizarse una vez: si dos cuentas eligieron la
   misma tanda, se muestra el grupo de cuentas, disponibles, requeridos y
   faltantes. Al confirmar, se usan solo los archivos existentes; nunca se
   reutiliza metadata ni se generan copias extra.
6. Al enviar, Telegram reconoce el calendario Trial, resuelve `source_key` del
   archivo calendarizado y usa el caption persistido literal. No aplica la
   rotación ni el shuffle de hashtags del flujo normal. Todas las copias de la
   fuente reciben el mismo texto y el topic Trial de la cuenta.

## Reutilización de código existente

Se extienden, no se duplican, los componentes actuales:

- El formato `__cNN` y `forge_video_registry` de Forge para descubrir fuentes.
- La planificación/copia de Logística y el constructor de nombres calendarizados.
- Los helpers de topics Trial, estado Telegram y soporte de rutas largas.
- Las pruebas actuales de Forge, captions, Logística y routing Telegram.

Los helpers que hoy deducen Trial desde `account_type` o `username` se
encapsularán para recibir un `delivery_kind` explícito. El flujo normal queda
intacto y continúa usando sus pools/rotación de captions por tanda.

## Pruebas

- Migración y toggle `trials_active` sin modificar `account_type`.
- Descubrimiento de tres fuentes y sus copias en una tanda Forge Trial.
- Guardado/lectura de captions Trial por fuente y bloqueo al faltar uno.
- Resolución exacta: `vid1__c01`, `vid1__c02` y `vid1__c03` reciben el mismo
  caption literal; `vid2` usa solo el suyo.
- Logística Trial selecciona solo cuentas activas y usa solo el calendario Trial.
- Selector individual cuenta-tanda, advertencia de tanda repetida y reparto sin
  duplicar archivos cuando el pool no alcanza.
- Miniaturas asíncronas/cacheadas junto a cada fuente/caption Trial.
- Telegram genera/usa topic Trial separado, sin cambiar el topic normal.
- Regresión: las tandas y captions normales mantienen su comportamiento actual.
