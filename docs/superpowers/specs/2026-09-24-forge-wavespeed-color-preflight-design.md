# Forge: clasificación automática de color para WaveSpeed sin tags

## Decisión aprobada

Retirar de Forge la casilla «Sin tags: SDR BT.709 ya verificado». El usuario elige únicamente el perfil de salida iPhone SDR o iPhone HLG. La clasificación de la entrada ocurre en el preflight, de igual manera en preview y procesamiento.

## Regla

Una fuente sin ninguno de los tres campos `color_primaries`, `color_transfer` y `color_space` se puede tratar como SDR BT.709 sólo si **todas** estas señales coinciden:

- archivo MP4 con marca `isom` cuyo nombre sigue el patrón de salida conocido `wavespeed_<identificador>.mp4`;
- stream de vídeo H.264, `yuv420p` de 8 bits;
- tag de formato `AIGC` presente y estructuralmente legible como JSON (sin registrar ni mostrar su contenido privado).

Esta combinación reconoce la salida WaveSpeed observada en `wavespeed_223c4e71308a474a8834c39de5acccc5.mp4`; es una regla operativa calibrada por el piloto SDR, no una prueba matemática de BT.709. La suposición se guarda por archivo en el log de Forge y se muestra resumida en el preview. No se aplica por el mero hecho de que un archivo tenga 8 bits, contenga `AIGC`, o se llame WaveSpeed por separado.

Las fuentes con tags BT.709 completos o BT.2020/HLG completos conservan la clasificación existente. Tags parciales, valores contradictorios, HEVC/10 bits sin tags, fuentes desconocidas y archivos sin las tres señales WaveSpeed siguen bloqueados con un mensaje legible: Forge no cambia el perfil de salida ni el contenido para ocultar la incertidumbre.

## Flujo y límites

El preflight lee cada fuente una vez y devuelve color, razón de clasificación, y bloqueos. Preview y Procesar usan el mismo preflight. El usuario no ve ningún check técnico. Un lote puede contener fuentes etiquetadas y WaveSpeed sin tags reconocidas; los demás archivos fallan antes de generar copias. El perfil Legacy MP4 no cambia.

La regla automática no corrige la conversión SDR→HLG: el usuario observó HLG lavado y SDR mejor en el iPhone. Para ese origen, la recomendación actual sigue siendo iPhone SDR hasta calibrar HLG visualmente. El QC técnico no debe presentarse como aprobación visual del HDR.

## Verificación

- Test de clasificación positiva con fixture de las tres señales, para iPhone SDR e iPhone HLG.
- Tests negativos al quitar individualmente el nombre, el tag `AIGC`, el codec/8 bits, o al añadir un tag de color parcial.
- Test de GUI que comprueba que la casilla desaparece y que preview/procesamiento usan el mismo preflight sin override manual.
- Ejecutar la prueba de preflight sobre la fuente WaveSpeed real en modo lectura y la regresión Forge/Logística. No modificar el archivo fuente ni las tandas piloto.
