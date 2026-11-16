# Selector de orden para copias TRIAL

## Objetivo

Agregar en `Logística > TRIAL` un selector global que permita elegir el orden de las copias antes de previsualizar o distribuir:

- `Intercalado`: `ID1-c1, ID2-c1, ID3-c1, ID1-c2, ID2-c2...`
- `Agrupado por ID`: `ID1-c1, ID1-c2, ID1-c3, ID2-c1, ID2-c2...`

`Intercalado` continúa siendo el valor predeterminado para conservar el comportamiento de v1.0.54.

## Alcance

El selector se aplica a todas las cuentas incluidas en una ejecución TRIAL. Afecta tanto la vista previa como la escritura de `calendar_manifest.json`, por lo que Telegram recibe luego el mismo orden mostrado al usuario.

El cambio no afecta `Por Tandas`, `Por Cuentas`, calendarios normales, captions, filtros de Telegram ni el historial de envíos.

## Comportamiento de asignación

El planificador recibe un nuevo argumento explícito `order_mode`, con valores internos `interleaved` y `grouped`. La identidad de grupo usa `origin_identity` verificado cuando existe y, como respaldo, `source_key_from_filename()`.

Ambos modos ordenan las copias de un mismo origen por el sufijo numérico `__cNN`. `Intercalado` recorre una copia de cada origen por ronda. `Agrupado por ID` consume todas las copias de un origen antes de pasar al siguiente.

El selector solo cambia el orden del pool. Se conservan estas reglas existentes:

- cada archivo físico se asigna una sola vez en toda la ejecución;
- `MAX` reparte el total disponible entre las cuentas que comparten una tanda;
- un período fijo conserva `videos por día × días` por cuenta y bloquea la escritura cuando faltan archivos;
- compartir una tanda entre cuentas no crea ni reutiliza copias adicionales.

## Interfaz

En la fila superior de configuración TRIAL, junto a `Videos/día por cuenta` y `Días`, se agrega:

`Orden: [Intercalado | Agrupado por ID]`

El valor vive durante la sesión de la GUI y se lee en el momento de construir el plan. La vista previa incluye una línea `Orden: ...` para que la elección quede visible antes de distribuir.

No se persiste el selector en base de datos ni en configuración, porque describe una decisión de cada ejecución y el valor seguro al iniciar sigue siendo `Intercalado`.

## Enfoques considerados

### Recomendado: un planificador con modo explícito

Agregar `order_mode` a `build_trial_account_plan()` y centralizar los dos recorridos en la función que ordena el pool. Mantiene una sola implementación para cupos, faltantes y reparto entre cuentas.

### Reordenar el manifiesto después de planificar

Mover entradas después de calcular el plan reduciría el cambio al planificador, pero haría que la selección de archivos por cuenta y la secuencia de captions pudieran diferir de la vista previa. Se descarta.

### Duplicar el planificador completo

Crear un planificador agrupado separado aislaría los modos, pero duplicaría las reglas de `MAX`, faltantes y tandas compartidas. Se descarta por riesgo de divergencia.

## Validación

Las pruebas deben demostrar:

1. Omitir `order_mode` conserva exactamente el orden intercalado actual.
2. `order_mode="grouped"` produce todas las copias consecutivas por identidad.
3. El agrupamiento respeta `origin_identity` aunque los nombres de archivo sean distintos.
4. En una tanda compartida, ningún archivo se duplica y los cupos permanecen iguales.
5. La GUI crea un solo selector global con `Intercalado` predeterminado.
6. Vista previa y distribución pasan el mismo modo al planificador y muestran el modo elegido.
7. Las pruebas existentes de TRIAL, captions y Logística continúan pasando.

