# Forge: línea base técnica (2026-09-24)

Inspección de solo lectura con `ffprobe -show_format -show_streams -of json` y `ffprobe -v trace`. El vídeo de referencia y las dos salidas existentes permanecen fuera del repositorio. Se omiten coordenadas, fecha de captura y otros valores privados; sólo se registran los tipos de tags pertinentes.

| Campo | `IMG_9050.MOV` (iPhone) | `0824(1)__c01.mp4` | `0824(1)__c02.mp4` |
| --- | --- | --- | --- |
| Formato / major brand | MOV / `qt  ` | MP4 / `isom` | MP4 / `isom` |
| Átomos principales | `ftyp`, `mdat`, `moov` | `ftyp`, `mdat`, `moov` | `ftyp`, `mdat`, `moov` |
| Vídeo | HEVC Main 10 `hvc1` | H.264 High `avc1` | H.264 High `avc1` |
| Tamaño / píxeles | 3840×2160 / `yuv420p10le` | 1080×1920 / `yuv420p` | 1080×1920 / `yuv420p` |
| FPS medio | 7175/299 ≈ 24 | 30 | 1700/57 ≈ 29.82 |
| Rango / primarias / transferencia / matriz | `tv` / BT.2020 / HLG / BT.2020nc | `tv` / BT.709 / BT.709 / BT.709 | `tv` / BT.709 / BT.709 / BT.709 |
| Audio | AAC-LC, 48 kHz, 2 canales | AAC-LC, 44.1 kHz, 2 canales | AAC-LC, 44.1 kHz, 2 canales |
| Pistas | 1 vídeo + 1 audio + 5 datos `mebx` | 1 vídeo + 1 audio | 1 vídeo + 1 audio |
| Tags de formato | `com.apple.quicktime.make/model/software`, ubicación, fecha | `make/model`, QuickTime `software/model/network`, ubicación | mismos tipos de tags |
| Valor de software | `26.4` | `iOS 18.1` | `iOS 26.0.1` |

La referencia tiene SHA-256 `FDCEE04FD56A4762AA1534123C524038B54F68B4E4D7C457705A379501E1B35F`. No se copian sus pistas `mebx`, coordenadas ni fecha. El FFmpeg en `PATH` de este entorno anuncia `libx265`, AAC y `zscale`; el binario empaquetado `tools/ffmpeg/bin/ffmpeg.exe` no está presente en el worktree Git y aún requiere verificación en el artefacto de release.
