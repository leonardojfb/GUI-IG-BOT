# Rendimiento global de renderizado — Diseño

## Objetivo

Permitir que la persona usuaria elija cuántos videos se procesan en paralelo en Forge, Tandas y Edición, sin que las tres pantallas diverjan ni que una actualización borre su preferencia. El máximo disponible se calcula en la máquina actual para respetar CPU y RAM libres.

## Alcance

- Una preferencia global llamada **Videos en paralelo**, visible y sincronizada en Forge, Tandas y Edición.
- Persistencia fuera del checkout en `%LOCALAPPDATA%\\MetodoIG\\render_performance.json`.
- Límite calculado por núcleos lógicos y RAM libre al momento de leer la configuración.
- Render por lote concurrente en los tres flujos.
- Presupuesto de hilos FFmpeg por trabajo para evitar que varios procesos intenten usar toda la CPU cada uno.

No se cambia el formato de salida, las reglas de Forge, los nombres de tanda, la distribución, ni las operaciones de Telegram.

## Modelo de capacidad

Un módulo nuevo, `render_performance.py`, será dueño de la capacidad y de la persistencia. Expone una configuración inmutable para una ejecución:

```python
@dataclass(frozen=True)
class RenderPerformance:
    max_workers: int
    workers: int
    ffmpeg_threads: int
    logical_cpus: int
    available_memory_bytes: int
```

`max_workers` es `min(logical_cpus, max(1, available_memory_bytes // 2 GiB))`, con mínimo absoluto de uno. El valor elegido se normaliza a ese intervalo. La primera vez usa `min(2, max_workers)`, conservando el comportamiento histórico de Tandas sin hacer que Forge o Edición comiencen con una carga extrema.

`ffmpeg_threads` es `max(1, logical_cpus // workers)`. Cada trabajo de CPU recibe ese valor con `-threads`; el total planificado no supera los núcleos lógicos. Los codificadores acelerados por hardware conservan su selección/fallback actual.

La RAM y los núcleos se leen con APIs estándar de Python/Windows, sin una dependencia nueva. Si la memoria no puede consultarse, el límite usa sólo CPU. El límite es una protección operativa, no una garantía contra archivos inválidos, disco lleno o una GPU ya ocupada.

## Interfaz

Cada pantalla tendrá la misma fila compacta:

```
Videos en paralelo: [ 1 ────────●────── 8 ]  4 de 8 para este equipo
```

- El `CTkSlider` permite sólo enteros entre 1 y el máximo de la máquina actual.
- El texto muestra valor elegido y máximo; si la preferencia guardada se recorta porque la máquina tiene menos recursos, se persiste el valor válido y se informa de forma no bloqueante.
- La barra aparece en el bloque de configuración, antes del botón de inicio, en Forge, Tandas y Edición.
- Cambiar cualquier barra actualiza las otras dos y guarda inmediatamente el valor.
- La confirmación de Forge y los estados de proceso indican cuántos videos se ejecutarán en paralelo.

## Ejecución concurrente

Al presionar el botón, la pantalla toma un `RenderPerformance` snapshot. El valor no vuelve a leerse durante esa ejecución.

- **Tandas:** `videos.process_tandas(..., performance=...)` crea su `ThreadPoolExecutor` con `performance.workers`. `render_video_pair(..., ffmpeg_threads=...)` usa el presupuesto sólo en el fallback CPU; no altera los intentos NVIDIA/QSV.
- **Edición:** `_editor_render_batch` procesa los trabajos con el mismo número de workers y llama `video_editor.render_video(..., ffmpeg_threads=...)`.
- **Forge:** los trabajos FFmpeg se ejecutan concurrentemente. Cada futuro devuelve sus datos de registro. Después de que todos finalicen, el hilo worker de la GUI escribe `forge_video_registry` y `metadata_fingerprints` secuencialmente en SQLite para evitar contención.

Si un trabajo falla, el error identifica su archivo de origen. Los resultados ya generados se conservan y no se ejecutan escrituras SQLite parciales de Forge.

## Pruebas

- `render_performance.py`: lectura/escritura, default, cálculo por CPU/RAM, fallback de memoria y clamping de valores guardados.
- `videos.py`: el executor recibe el número elegido y el fallback CPU recibe los hilos calculados.
- `video_editor.py`: el comando FFmpeg incorpora el presupuesto de hilos.
- `gui_premium_v7.py`: las tres pantallas construyen el control global y cada flujo pasa el mismo snapshot al ejecutor correcto.
- Forge: la colección concurrente produce registros y la escritura SQLite continúa siendo única/secuencial.

## Compatibilidad y actualización

El JSON vive bajo LocalAppData y no en el ZIP de release: los paquetes normales siguen siendo código solamente y el valor sobrevive reinstalaciones o actualizaciones. Si el directorio o JSON no existe, se crea al guardar la primera preferencia. Un JSON ilegible se ignora y se reestablece un valor seguro.
