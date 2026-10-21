# Captions generales TRIAL por archivo

## Objetivo

La pantalla TRIAL permite elegir General o Individual una sola vez para toda la distribución. Individual conserva los captions manuales por origen y es el valor inicial. General toma un único TXT elegido arriba de la lista de cuentas y asigna un caption a cada archivo Forge calendarizado, incluso cuando varios archivos comparten origen.

## Datos y reparto

Se reutiliza el parser de TXT que usa Telegram. Un TXT inexistente o sin captions impide distribuir en General. El TXT elegido es único para la ejecución; para cada tanda, se ordenan sus asignaciones por día, slot, cuenta y archivo. Ese orden consume los textos distintos del TXT en una secuencia compartida por todas las cuentas de esa tanda: cada caption aparece una vez antes de volver al primero, aunque el TXT contenga líneas duplicadas. La distribución fija `caption_mode=general` y el texto literal `caption` en cada entrada del manifiesto. En Individual fija `caption_mode=individual` y conserva la resolución por origen actual.

## Pantalla y envío

Arriba de la lista de cuentas hay un selector General/Individual y un único control para elegir o quitar el TXT. Las filas de cuenta conservan su selector de tanda. En Individual se habilita el panel de editores por origen de cada cuenta; en General se ocultan esos paneles y se usa el TXT global. La vista previa lista el caption asignado a cada archivo, además de las cuentas y días existentes. Telegram usa el caption del manifiesto para General. Los calendarios TRIAL antiguos, sin modo General, mantienen la resolución de captions por origen. El TXT solo afecta nuevas distribuciones; los captions ya escritos permanecen estables si cambia el archivo o el orden de envío.

## Verificación

Pruebas para el único selector y TXT globales, el panel Individual por cuenta, parser compartido, ciclos de captions entre cuentas de la misma tanda, aislamiento entre tandas, vista previa y manifiesto coincidentes, TXT faltante, y envío de General frente a Individual y calendarios TRIAL antiguos. No se reescriben los calendarios existentes durante esta implementación.
