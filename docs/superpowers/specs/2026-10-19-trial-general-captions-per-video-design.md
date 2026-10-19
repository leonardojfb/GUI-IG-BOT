# Captions generales TRIAL por archivo

## Objetivo

La pantalla TRIAL permite elegir General o Individual por cuenta. Individual conserva los captions manuales por origen y es el valor inicial. General toma el TXT asociado a la tanda y asigna un caption a cada archivo Forge calendarizado, incluso cuando varios archivos comparten origen.

## Datos y reparto

La ruta del TXT pertenece a `trial_tandas`, separada de `batch_tandas`; así funcionan las tandas TRIAL sin fila normal. Se reutiliza el parser de TXT que usa Telegram. Un TXT inexistente o sin captions impide distribuir las cuentas en General. Para cada tanda, se ordenan sus asignaciones por día, slot, cuenta y archivo. Ese orden consume el pool de captions en una sola secuencia compartida por todas las cuentas de la tanda en General: cada elemento aparece una vez antes de volver al primero. Las cuentas en Individual no consumen el pool. La distribución fija `caption_mode=general` y el texto literal `caption` en cada entrada del manifiesto. En Individual fija `caption_mode=individual` y conserva la resolución por origen actual.

## Pantalla y envío

Cada fila de cuenta TRIAL tiene selector de modo y controles para elegir o quitar el TXT de su tanda. Cambiar el modo actualiza el panel: en Individual muestra editores por origen; en General muestra el TXT asociado. La vista previa lista el caption asignado a cada archivo, además de las cuentas y días existentes. Telegram usa el caption del manifiesto para General. Los calendarios TRIAL antiguos, sin modo General, mantienen la resolución de captions por origen. El TXT solo afecta nuevas distribuciones; los captions ya escritos permanecen estables si cambia el archivo o el orden de envío.

## Verificación

Pruebas para persistencia de ruta por tanda TRIAL sin fila normal, parser compartido, ciclos de captions entre cuentas de la misma tanda, aislamiento entre tandas, vista previa y manifiesto coincidentes, TXT faltante, y envío de General frente a Individual y calendarios TRIAL antiguos. No se reescriben los calendarios existentes durante esta implementación.
