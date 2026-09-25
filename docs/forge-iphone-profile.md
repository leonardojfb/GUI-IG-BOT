# Forge: perfiles MOV tipo iPhone

Estado de implementación local a 2026-09-24. El perfil predeterminado sigue siendo `Legacy MP4` hasta completar la calibración visual y una prueba de entrega real. `iPhone SDR` es provisional: aún no se aportó una captura SDR de iPhone para compararlo campo por campo.

## Uso

1. Añadir los vídeos de la tanda y elegir `iPhone SDR` o `iPhone HLG` en Forge. La selección se aplica a toda la tanda; no cambia sola por archivo.
2. Generar el preview. Muestra cuántas fuentes tienen BT.709/SDR, BT.2020/HLG y color desconocido. Una salida WaveSpeed reconocida (nombre de origen, MP4 `isom`, H.264 de 8 bits, tag AIGC estructuralmente legible y los tres tags de color ausentes) se interpreta automáticamente como SDR BT.709; la suposición queda en el log de la copia. Las fuentes con tags parciales, contradictorios o procedencia no reconocida se bloquean. No hay casilla técnica que decidir.
3. Confirmar el formato MOV, los efectos y el conteo. Forge guarda `__cNN.mov` sólo después de verificar codec, color, audio, tags, orden de átomos, decodificación completa y una comparación automática de brillo/saturación con la fuente.
4. Si una copia falla, el estado `forge_batch_status.json` de la tanda queda `incomplete`; Logística no distribuye esa tanda. Repetir `Procesar` con el mismo nombre/perfil y las fuentes pendientes reintenta sólo esas copias con sus números y metadata reservados. Los temporales fallidos se eliminan; las copias aprobadas permanecen.

`iPhone HLG` produce HEVC Main 10 `hvc1`, 10 bits, BT.2020/HLG, 24 FPS objetivo, MOV `qt`, AAC-LC 48 kHz estéreo si la fuente contiene audio. `iPhone SDR` produce HEVC Main, 8 bits, BT.709. Ambos mantienen las dimensiones visuales salvo el ajuste a pares y la autorrotación de una fuente que declare orientación. La ruta sin microediciones también transcodifica para cumplir el perfil. HLG→SDR no está calibrado y se bloquea; fuentes sin audio no reciben audio inventado.

Los tags de salida son QuickTime `make=Apple`, `model` y `software` (valor de versión, por ejemplo `26.4`, no `iOS 26.4`). No se escriben operador, ubicación ni fecha de la captura de referencia. No se copian pistas `mebx` ni datos de sensor. La ubicación de una copia nueva sólo puede añadirse si se implementa y activa explícitamente una opción; el Forge actual la omite. La metadata y el códec pueden coincidir con un patrón observado, pero no prueban que la cámara de un iPhone capturó los píxeles.

## Comparación piloto (1 segundo por clip)

| Campo | `IMG_9050.MOV` | HLG→HLG nuevo | salida SDR existente | SDR→HLG nuevo |
| --- | --- | --- | --- | --- |
| Contenedor / marca | MOV `qt` | MOV `qt` | MP4 `isom` | MOV `qt` |
| Vídeo | HEVC Main 10 `hvc1` | HEVC Main 10 `hvc1` | H.264 High `avc1` | HEVC Main 10 `hvc1` |
| Color | BT.2020/HLG 10-bit | BT.2020/HLG 10-bit | BT.709 SDR 8-bit | BT.2020/HLG 10-bit |
| Audio | AAC-LC 48 kHz estéreo | AAC-LC 48 kHz estéreo | AAC-LC 44.1 kHz estéreo | AAC-LC 48 kHz estéreo |
| Pistas `mebx` | 5 | 0 (no inventadas) | 0 | 0 |
| Marca de software | `26.4` | `26.4` | `iOS 18.1` | `26.4` |
| Vista SDR, YAVG (0–255) | 175.0 | 173.0 | 85.6 | 83.9 |
| Vista SDR, saturación media | 5.51 | 5.51 | 10.40 | 10.20 |
| Tamaño piloto | referencia 27.5 MB / 11.96 s | 1.34 MB / 1 s | 2.24 MB / 5.77 s | 0.32 MB / 1 s |

La conversión SDR→HLG usa `npl=291` como punto inicial: en el piloto, `npl=100` oscurecía la vista SDR (YAVG ~60.7). Las métricas se calculan sobre una misma vista SDR de HLG, con `zscale` y `tonemap=hable`, y no sustituyen la revisión en una pantalla HDR. En esta máquina, recodificar un segundo de referencia 4K tomó ~4.4 s y un segundo de SDR 1080×1920 a HLG ~1.6 s, ambos con 4 hilos; son medidas locales, no una promesa de rendimiento por tanda.

El usuario comparó una tanda WaveSpeed real en iPhone: HLG se veía lavado y SDR mejor. Por ahora, para ese origen se recomienda **iPhone SDR**; la clasificación automática de la entrada no corrige el aspecto de la salida HLG. HLG requiere recalibración visual antes de usarse en tandas de ese origen.

## Calibración pendiente del usuario

Los pilotos locales se guardan en `.superpowers/pilot/reference_hlg.mov` y `.superpowers/pilot/sdr_to_hlg_291.mov` del worktree aislado y no se empaquetan. Revisar el segundo junto a su fuente SDR en un iPhone con pantalla HDR y en un reproductor SDR. Confirmar piel, blancos, sombras, saturación, brillo al cambiar entre escenas y ausencia de bandas. Para certificar `iPhone SDR`, aportar un vídeo SDR recién grabado en el mismo iPhone. Después se fijan los umbrales y se decide el perfil predeterminado.

## Entrega

Las pruebas locales comprueban `videos_finales`→Logística→manifest y el MIME `video/quicktime` en el envío simulado. No se ha enviado ningún archivo a Telegram real. La [Bot API de Telegram](https://core.telegram.org/bots/api#sendvideo) garantiza reproducción de vídeos MPEG4 en `sendVideo` y advierte que otros formatos pueden enviarse como documento; por ello MOV/HEVC/HLG necesita una prueba real antes de habilitar entrega automática. Si no funciona, se debe generar una copia MP4/SDR de entrega, conservar el MOV maestro y enlazar ambas rutas en el manifest. No sustituir silenciosamente el maestro.
