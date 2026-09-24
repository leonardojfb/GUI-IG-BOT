# Forge iPhone Reference Profile Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` task by task; track each task with a failing test, implementation, and fresh verification.

> Plan de implementación para el checkout Legacy. No modificar los videos existentes ni el archivo de referencia. Ejecutar en una rama o worktree aislado creado desde `origin/main` cuando se inicie el trabajo de código; incorporar de forma selectiva cualquier cambio necesario del checkout activo, que actualmente tiene modificaciones sin confirmar.

**Objetivo:** que Forge pueda generar copias con un perfil técnico coherente con el video de iPhone aportado por el usuario, conservando las microediciones, el registro de copias y la integración con Logística y Telegram.

**Referencia:** `iphonevidref/IMG_9050.MOV` (SHA-256 `FDCEE04FD56A4762AA1534123C524038B54F68B4E4D7C457705A379501E1B35F`). La captura tiene `qt`/MOV, HEVC `hvc1` Main 10, 10 bits, BT.2020/HLG, ~24 fps con variación de timestamps, AAC-LC estéreo 48 kHz, `moov` al final y cinco pistas `mebx` de datos de cámara. El modelo, la versión de iOS y la ubicación son tags descriptivos; no cambian el aspecto de los píxeles. Las pistas `mebx` contienen datos temporales asociados a la captura y no se deben copiar desde la referencia a clips distintos.

**Estado actual:** `metadata_pool.py::apply_variant_and_metadata` codifica H.264 High de 8 bits, AAC 128 kbps, y escribe tags MP4 `isom`. `apply_metadata_to_video` usa `-c copy` si no hay efectos. `gui_premium_v7.py::forge_process` conserva la extensión de la fuente en el nombre de salida. Las salidas analizadas tienen 2 streams, audio 32/44.1 kHz y color sin declarar. La mayoría de lectores de `videos_finales` aceptan `.mov`, pero algunas pruebas y rutas auxiliares asumen `.mp4`.

## Decisiones de diseño

1. Añadir dos perfiles explícitos, `iPhone HLG` y `iPhone SDR`, y conservar el perfil actual durante la validación. Los perfiles nuevos producen `.mov` y comparten un constructor de argumentos para las rutas con y sin efectos; esta última también debe transcodificar si el codec, audio, color o contenedor no cumplen el perfil seleccionado.
2. `iPhone HLG` codifica HEVC Main 10 `hvc1`, `yuv420p10le`, a ~24 fps y keyframes aproximadamente cada 0.8 s, según la referencia. `iPhone SDR` es provisional hasta recibir una captura iPhone SDR: codifica HEVC Main de 8 bits con BT.709 correcto. Mantener la resolución de la fuente salvo el ajuste mínimo a dimensiones pares que requiera el codec. La variación temporal de la cámara no se copiará artificialmente; la aceptación se basará en reproducción correcta y timing consistente.
3. Codificar audio AAC-LC, 48 kHz, estéreo, cerca de 160 kbps. Para fuentes sin audio, mantener la política actual de Forge salvo decisión explícita del producto; no inventar audio grabado por micrófono.
4. El perfil de color se elige una vez para la tanda y el resultado debe ser homogéneo. El preview inspecciona cada entrada y cuenta fuentes SDR, HLG y de color desconocido. Las fuentes sin tags de color procedentes de un generador conocido se tratan con una regla explícita y registrada de entrada SDR BT.709; otros archivos sin tags se señalan para identificar su color antes de procesar. Para una tanda `iPhone HLG`, conservar HLG/BT.2020 si la fuente ya lo es y convertir SDR mediante transformaciones reales de primarias, transferencia y luminancia. Calibrar la conversión una vez con una tanda piloto vista en un reproductor HDR y otro SDR. Luego Forge debe comprobar automáticamente cada salida: tags y decodificación, histograma de luminancia, clipping de altas luces/sombras, saturación y una comparación de la vista SDR del HLG con la fuente. Si una salida falla, detenerla e informar el archivo y la medida; no cambiarla silenciosamente a SDR ni marcar píxeles SDR como HLG. El usuario puede escoger `iPhone SDR` para toda la tanda y volver a procesarla. Registrar entrada, transformación y salida por archivo.
5. Escribir MOV con marca `qt`, tiempos y tags QuickTime coherentes. Usar claves `com.apple.quicktime.make`, `.model` y `.software` en el formato observado, sin copiar la fecha ni la ubicación de `IMG_9050.MOV`. Mantener ubicación sólo si la configuración de Forge la pide; el operador móvil no aparece en la referencia y no es necesario. No crear pistas `mebx` vacías ni reutilizar datos de sensores de otro clip.
6. Mantener `moov` al final para asemejar la estructura observada en `IMG_9050.MOV`. No usar `+faststart` en este perfil. Dejar el MP4 actual disponible para destinos que exijan MP4.

### Task 1: Perfilar capacidades y fijar el contrato

**Archivos:** `metadata_pool.py`; crear `tests/test_forge_iphone_profile.py`.

- [ ] Registrar con `ffprobe` un informe JSON de la referencia y de dos entradas representativas de Forge; incluir codec, color, FPS, audio, tags, streams y atom boxes. Conservar sólo el informe técnico en los tests, nunca los MOV/MP4 privados.
- [ ] Comprobar que el FFmpeg del release soporta `libx265`, AAC, MOV `qt` y los filtros de color requeridos. Tanto `C:\ffmepg\bin\ffmpeg.exe` como `tools/ffmpeg/bin/ffmpeg.exe` anuncian `libx265` y AAC en este checkout; falta verificar el ejecutable distribuido y los filtros antes de activar el perfil.
- [ ] Escribir tests del contrato de salida: `.mov`, `hevc/hvc1/Main 10/yuv420p10le`, 24 fps objetivo, audio AAC-LC 48 kHz estéreo, tags QuickTime esperados, y ausencia de `mebx` inventados. Definir una función de validación reutilizable que devuelva errores concretos por campo.

**Aceptación:** el perfil y la validación pueden describir una salida correcta o fallida sin depender de la GUI ni de la DB.

### Task 2: Codificación y color en el motor de Forge

**Archivos:** `metadata_pool.py`; `tests/test_forge_iphone_profile.py`; actualizar `tests/test_forge_concurrency.py`.

- [ ] Extraer la construcción de argumentos de FFmpeg a una función de perfil, para que `apply_variant_and_metadata` y `apply_metadata_to_video` compartan codec, audio, color, contenedor y tags.
- [ ] Añadir pruebas que fallen primero para cuatro fuentes: H.264 SDR con audio a 32 kHz, H.264 SDR con audio a 44.1 kHz, HEVC HLG con audio a 48 kHz y video sin audio. Cubrir con efectos y sin efectos.
- [ ] Implementar HEVC Main 10 `hvc1`, audio AAC-LC 48 kHz estéreo, keyframes ~0.8 s y dimensiones pares. Medir y acotar bitrate/CRF para evitar pérdida visible y crecimiento excesivo. Respetar `ffmpeg_threads` y registrar tiempo de render.
- [ ] Implementar color por tipo de fuente. Los filtros de color y ruido actuales (`eq`, `noise`) pueden afectar a la precisión HDR: probarlos en 10 bits/HLG y adaptar o desactivar sólo el filtro incompatible dentro del perfil nuevo, con un error o aviso explícito en el log.
- [ ] Ejecutar un preflight antes del primer render: contar entradas SDR/HLG/desconocidas, reconocer los generadores cuyas salidas sin tags se han calibrado como SDR BT.709, confirmar que todas tienen una ruta de conversión al perfil elegido y señalar las restantes con nombre y razón. El perfil de salida no se cambia automáticamente durante el trabajo.
- [ ] Añadir control de calidad automático sobre una muestra temporal de cada fuente y sobre cada salida final: decodificación, tags, clipping, luminancia y saturación; comparar la versión SDR de la salida HLG con la fuente para detectar desviaciones grandes. Guardar umbrales calibrados con la tanda piloto, error medido y estado aprobado/rechazado. No aprobar una copia sólo porque `ffprobe` acepta el archivo.
- [ ] Escribir cada copia en un archivo temporal de la carpeta de salida. Validarla antes de moverla a su nombre `__cNN.mov` y antes de registrar la copia en DB. Si falla, retirar sólo su temporal, conservar el error por fuente/copia y permitir reintentar esa copia con el mismo número reservado; las demás copias validadas pueden quedar disponibles, pero la tanda se muestra `incompleta` hasta resolver los fallos.
- [ ] Evitar la ruta `-c copy` cuando la salida no cumple el perfil. Si la fuente ya cumple codec/color/audio, permitir remux sin pérdida sólo tras verificar que el resultado conserva el contrato.

**Aceptación:** las cuatro fuentes producen salida decodificable; `ffprobe` confirma los campos exigidos; el control automático rechaza fixtures deliberadamente lavados, oscuros y recortados; la tanda piloto no muestra color lavado, clipping ni bandas nuevas evidentes en HDR ni en su vista SDR.

### Task 3: Metadata QuickTime y nombres de archivo

**Archivos:** `metadata_pool.py`, `gui_premium_v7.py`, `trial_content.py`; `tests/test_forge_concurrency.py`, `tests/test_forge_ui.py`, `tests/test_forge_iphone_profile.py`.

- [ ] Escribir tests de los tags QuickTime. La versión de software debe representarse como `26.4`, no `iOS 26.4`, cuando se use el valor de referencia. Validar combinaciones modelo/iOS que Forge ya genera. No añadir operador móvil al archivo nuevo.
- [ ] Generar nombres `__cNN.mov` para el perfil nuevo y reservar números comparando copias `.mp4` y `.mov` del mismo origen para evitar choques. Conservar el enlace source→output en el registro de Forge y en el log de transformaciones.
- [ ] Mostrar el perfil seleccionado, el formato final y el conteo de fuentes SDR/HLG/desconocidas en preview y confirmación de Forge. Registrar `profile`, codec, color de entrada/salida, conversión, audio y ruta final en el log para auditar cada copia.
- [ ] Probar `make/model/software`, GPS opcional, fecha de salida coherente si se escribe, y estructura `ftyp qt`/`mdat`/`moov`. No copiar tags ni pistas temporales del archivo de referencia.

**Aceptación:** dos copias del mismo origen salen con nombres únicos, la metadata coincide con el perfil y el registro existente sigue encontrándolas.

### Task 4: Consumidores de `.mov` y regresión completa

**Archivos a revisar y modificar sólo si una prueba falla:** `database.py`, `Organizador.py`, `gui_premium_v7.py`, `organizadortg.py`, `calendar_manifest.py`, `social_publishing.py`, `trial_content.py`, `tests/support/e2e_pipeline.py` y sus tests de Logística/Telegram.

- [ ] Recorrer Forge→`videos_finales`→Logística→calendario/manifest→Telegram con una salida `.mov`. Ajustar los puntos que filtren sólo `*.mp4`, asuman `video/mp4`, o pierdan la identidad `__cNN` al cambiar la extensión. Logística debe ver únicamente copias validadas y registradas; una tanda `incompleta` requiere una decisión explícita de usar sólo las copias aprobadas o esperar el reintento, sin presentarse como completada.
- [ ] Confirmar con un video de prueba que el destino real acepta MOV/HEVC Main 10/HLG; si no lo acepta, producir una copia de entrega MP4/SDR desde el MOV maestro y relacionar ambas rutas en el manifest. No reemplazar silenciosamente el maestro.
- [ ] Ejecutar los tests enfocados de Forge, Logística y Telegram y un flujo completo en carpeta temporal. Verificar integridad de salida con `ffmpeg -err_detect explode -xerror -i <salida> -map 0 -f null -` y comparar `ffprobe` contra el contrato.
- [ ] Medir CPU, RAM, duración y tamaño con la concurrencia actual (`render_performance.py`). Ajustar sólo el máximo de workers del perfil HEVC si la medición muestra saturación o fallos; no cambiar el rendimiento del perfil existente.

**Aceptación:** al menos dos fuentes, una con audio y una sin audio, generan copias; Logística y Telegram consumen el formato elegido; no cambian ni se sobrescriben archivos existentes en `videos_finales`.

### Task 5: Entrega y reversión

**Archivos:** documentación breve de Forge y tests modificados.

- [ ] Documentar el perfil, su rendimiento, cuándo usa HLG o SDR y cómo leer la validación técnica. Incluir comparación real de `IMG_9050.MOV` frente a dos salidas nuevas, campo por campo.
- [ ] Mantener el perfil anterior seleccionable como reversión. Elegir el perfil predeterminado (`iPhone HLG` o `iPhone SDR`) sólo después de pasar los tests, la comparación visual y la prueba del destino final con una tanda SDR representativa.
- [ ] Empaquetar una actualización sólo con código y tests; excluir el MOV de referencia, `videos_finales`, DB, tokens y demás estado de ejecución. Verificar el FFmpeg empaquetado antes de declarar la entrega lista.

**Límite de aceptación:** el perfil puede reproducir formato, codec, audio, color y tags pertinentes. La textura del sensor, el rango dinámico que no exista en la fuente y las pistas de sensor `mebx` no pueden aparecer fielmente mediante metadata de FFmpeg; la revisión visual debe evaluar esos límites por separado.
