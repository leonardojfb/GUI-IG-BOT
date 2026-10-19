# Anticolisión diaria de orígenes TRIAL

## Objetivo

Al distribuir TRIAL, reducir al mínimo la repetición del mismo origen entre cuentas en un mismo número de día, incluyendo los TRIAL que ya están en `calendar_manifest.json`. Si la cantidad de orígenes disponibles obliga a repetir, completar la distribución y mostrar cuántas repeticiones fueron inevitables. Mantener el bloqueo actual de distribuciones incompletas.

## Alcance y datos

- La regla se aplica a entradas `delivery_kind="trial"`. Los días son los números `day` de la planificación, no fechas civiles.
- Las cuentas elegidas en la ejecución reemplazarán sus TRIAL actuales. Sus entradas previas se excluyen del cálculo; las de otras cuentas siguen ocupando orígenes en sus respectivos días.
- La identidad preferida es `origin_identity` validada por `DatabaseManager.get_video_transform_source_identity(source_path)`. Si falta, se usa la clave de origen extraída del nombre, limitada a la tanda. No se equiparan claves iguales de tandas distintas sin identidad verificada.
- Cada archivo Forge se asigna como máximo una vez por ejecución, como hoy. Las cuentas continúan usando solo su tanda elegida.

## Asignación

Para cada día y plaza, elegir entre los archivos todavía disponibles de la tanda de esa cuenta. Priorizar primero el origen con menor ocupación en ese día entre las cuentas TRIAL existentes y las ya planificadas en esta ejecución; después, preferir evitar reutilizar el origen en la misma cuenta a lo largo de otros días. Mantener la distribución determinista para que vista previa y ejecución con los mismos datos produzcan el mismo plan.

En el modo de días explícitos se conservan los cupos `videos_per_day × days` y el bloqueo por faltantes. En `MAX`, cada tanda reparte **todos** sus archivos una sola vez entre las cuentas que la eligieron: cada cuenta recibe `total // cuentas` archivos y las primeras `total % cuentas` reciben uno adicional. Por ejemplo, 40 copias para 10 cuentas son 4 por cuenta. Si hay menos copias que cuentas, algunas reciben cero y la vista previa lo indica; esto no se considera un faltante que bloquee `MAX`. Los archivos asignados se distribuyen entre días según `videos_per_day`, conservando la prioridad de anticolisión. No se modifican los archivos de `videos_finales` ni se crean copias físicas de calendario.

## Interfaz y errores

La vista previa muestra por cuenta los videos asignados y un resumen de repeticiones del mismo origen por día, separando las inevitables por capacidad. La confirmación de distribuir muestra el mismo resumen. La distribución escribe las entradas TRIAL mediante `replace_entries` solo después de construir un plan completo; si falla la lectura del manifiesto, se muestra el error y no se escribe un plan basado en una ocupación desconocida.

## Verificación

Pruebas del asignador con dos cuentas y copias de un mismo origen, varias tandas que comparten una identidad verificada, entradas TRIAL previas de otras cuentas, exclusión de entradas que se reemplazan, escasez de orígenes, modo `MAX`, varios videos por día y resultados deterministas. Una prueba de integración comprueba que la vista previa y la escritura usan el mismo cálculo y que `replace_entries` conserva los TRIAL de las otras cuentas.
