# Campaña E2E de trazabilidad multimedia Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ejecutar una campaña reproducible que procese, distribuya y envíe nueve tandas multimedia, y que compare el resultado final con el proceso real de cada tanda para detectar mezclas de archivos, captions, cuentas, VAs y orígenes.

**Architecture:** El plan agrega un manifiesto de prueba, un fixture aislado y un smoke E2E que usa los motores actuales (`video_editor.py`, `videos.py`, `metadata_pool.py`, `Organizador.py` y `organizadortg.py`). Telegram se intercepta con un sender falso que registra cada `chat_id`, topic, archivo y caption; un auditor compara ese registro con el manifiesto, SQLite, `videos_finales/` y `CALENDARIO_POSTEO/`. La GUI se verifica manualmente contra el mismo fixture, sin tocar la base operativa.

**Tech Stack:** Python 3, `pytest`, FFmpeg/FFprobe, SQLite, SHA-256, `video_editor.py`, `videos.py`, `metadata_pool.py`, `Organizador.py`, `organizadortg.py` y `launcher.py`.

## Global Constraints

## Addendum aprobado: captions solo en Logística

- Tandas, Edición y Forge generan o registran multimedia; no seleccionan ni reemplazan captions.
- Logística asigna o quita un `.txt` directamente a la tanda elegida y lo persiste en `batch_tandas.captions_file_path`.
- Telegram no recibe un archivo global: por cada MP4 calendarizado extrae `__TANDA_<nombre>__`, usa el pool persistido de esa tanda y deja `None` cuando no hay asignación.
- El smoke hace una sola corrida para los 27 archivos y exige los captions propios de `ED_A`, `TA_B` y `FO_C`; las otras seis tandas deben salir sin caption.
- Logística añade deliberadamente el sufijo `# ID_<16>` a cada copia calendarizada; el auditor valida esa mutación exacta en vez de exigir un SHA-256 idéntico.

- Checkout: `fix/forge-sin-distribucion` dentro de `IG GUI ACTUALIZADA (Legacy funcional)\Método IG VIDEOS v2.0`.
- Requisitos literales: `3 categorías distintas`, `3 va's distintos` y `3 tandas distintas de cada uno ... (Edición, Tanda, Forge)`.
- Cada tanda es una carpeta/resultante multimedia procesada, no solamente una fila de `batch_tandas`.
- Se crearán exactamente nueve tandas de salida: `ED_A`, `ED_B`, `ED_C`, `TA_A`, `TA_B`, `TA_C`, `FO_A`, `FO_B`, `FO_C`.
- Se usarán exactamente tres categorías (`PRUEBA_CAT_A`, `PRUEBA_CAT_B`, `PRUEBA_CAT_C`), tres VAs (`PRUEBA_VA_A`, `PRUEBA_VA_B`, `PRUEBA_VA_C`) y nueve cuentas, tres por categoría y una por cada VA.
- Habrá un caption distinto por cada tipo de procesado: `ED_A` (Edición), `TA_B` (Tandas) y `FO_C` (Forge). Las otras seis tandas tendrán caption vacío o inexistente.
- La primera ejecución usará una DB clonada y un sender Telegram falso. No se enviará nada a grupos reales durante esta fase.
- No se editarán `organizador.db`, `videos_finales/`, `CALENDARIO_POSTEO/` ni los archivos de producción fuera de un directorio temporal de la prueba.
- El criterio de éxito no depende del orden aleatorio: se compararán conjuntos de hashes, origen, destino y captions normalizados.
- Toda ejecución dejará un `run_id`, un manifiesto y un reporte PASS/FAIL/INCONCLUSIVE; no se aceptará “pasó” solo porque una carpeta o ruta exista.

---

### Task 1: Crear el manifiesto de datos y la base aislada

**Files:**
- Create: `tests/fixtures/e2e_pipeline_matrix.json`
- Create: `tests/support/__init__.py`
- Create: `tests/support/e2e_pipeline.py`
- Test: `tests/smoke_e2e_pipeline.py`

**Interfaces:**
- `load_matrix(path: str) -> dict` carga y valida los nombres exactos de la campaña.
- `seed_database(db_path: str, matrix: dict) -> None` crea categorías, VAs, cuentas, Telegram IDs falsos, tandas y horarios.
- `make_run_root() -> pathlib.Path` crea un directorio temporal fuera de las carpetas operativas.
- `sha256_file(path: pathlib.Path) -> str` devuelve la identidad física de cada archivo.
- `write_manifest(path: pathlib.Path, data: dict) -> None` guarda entradas append-only para cada etapa.

- [ ] **Step 1: Definir la matriz fija**

El JSON debe contener estos valores, sin nombres generados al azar:

```json
{
  "categories": ["PRUEBA_CAT_A", "PRUEBA_CAT_B", "PRUEBA_CAT_C"],
  "vas": [
    {"name": "PRUEBA_VA_A", "telegram_id": "TEST_CHAT_A"},
    {"name": "PRUEBA_VA_B", "telegram_id": "TEST_CHAT_B"},
    {"name": "PRUEBA_VA_C", "telegram_id": "TEST_CHAT_C"}
  ],
  "accounts": [
    {"username": "prueba_a_va_a", "category": "PRUEBA_CAT_A", "va": "PRUEBA_VA_A"},
    {"username": "prueba_a_va_b", "category": "PRUEBA_CAT_A", "va": "PRUEBA_VA_B"},
    {"username": "prueba_a_va_c", "category": "PRUEBA_CAT_A", "va": "PRUEBA_VA_C"},
    {"username": "prueba_b_va_a", "category": "PRUEBA_CAT_B", "va": "PRUEBA_VA_A"},
    {"username": "prueba_b_va_b", "category": "PRUEBA_CAT_B", "va": "PRUEBA_VA_B"},
    {"username": "prueba_b_va_c", "category": "PRUEBA_CAT_B", "va": "PRUEBA_VA_C"},
    {"username": "prueba_c_va_a", "category": "PRUEBA_CAT_C", "va": "PRUEBA_VA_A"},
    {"username": "prueba_c_va_b", "category": "PRUEBA_CAT_C", "va": "PRUEBA_VA_B"},
    {"username": "prueba_c_va_c", "category": "PRUEBA_CAT_C", "va": "PRUEBA_VA_C"}
  ],
  "tandas": {
    "ED_A": {"stage": "edicion", "category": "PRUEBA_CAT_A", "caption": "CAP_ED_A.txt"},
    "ED_B": {"stage": "edicion", "category": "PRUEBA_CAT_B", "caption": null},
    "ED_C": {"stage": "edicion", "category": "PRUEBA_CAT_C", "caption": null},
    "TA_A": {"stage": "tanda", "category": "PRUEBA_CAT_A", "caption": null},
    "TA_B": {"stage": "tanda", "category": "PRUEBA_CAT_B", "caption": "CAP_TA_B.txt"},
    "TA_C": {"stage": "tanda", "category": "PRUEBA_CAT_C", "caption": null},
    "FO_A": {"stage": "forge", "category": "PRUEBA_CAT_A", "caption": null},
    "FO_B": {"stage": "forge", "category": "PRUEBA_CAT_B", "caption": null},
    "FO_C": {"stage": "forge", "category": "PRUEBA_CAT_C", "caption": "CAP_FO_C.txt"}
  }
}
```

- [ ] **Step 2: Sembrar la DB temporal**

Usar `DatabaseManager` con `database.DB_PATH` apuntando al archivo temporal. Insertar los tres categories, los tres VAs con los `telegram_id` de prueba, las nueve cuentas, y un horario `8:00 AM` para cada combinación VA/categoría en el día 0. Guardar una copia JSON del estado inicial para compararla con el estado final.

- [ ] **Step 3: Aislar las rutas importadas**

Después de crear la DB, recargar los módulos y apuntar sus globales al mismo run root:

```python
videos.FOLDER_INPUTS = str(run_root / "inputs")
videos.FOLDER_OUTPUT_ROOT = str(run_root / "videos_finales")
Organizador.source_root = str(run_root / "videos_finales")
Organizador.output_root = str(run_root / "CALENDARIO_POSTEO")
organizadortg.input_root = str(run_root / "CALENDARIO_POSTEO")
organizadortg.base_dir = str(run_root)
database.DB_PATH = str(run_root / "organizador.db")
organizadortg.db = database.DatabaseManager()
```

El arnés debe cerrar todas las conexiones abiertas y borrar únicamente su propio directorio temporal al terminar.

---

### Task 2: Generar fixtures multimedia con identidad visible y hashable

**Files:**
- Modify: `tests/support/e2e_pipeline.py`
- Test: `tests/smoke_e2e_pipeline.py`

**Interfaces:**
- `create_video(path: pathlib.Path, color: str, marker: str) -> None` crea un MP4 corto con FFmpeg.
- `create_photo(path: pathlib.Path, color: str, marker: str) -> None` crea una imagen de overlay.
- `create_captions(path: pathlib.Path, label: str) -> None` escribe un caption multilinea con hashtags exclusivos.
- `record_asset(stage, tanda, source, output, metadata) -> None` registra el vínculo de entrada y salida.

- [ ] **Step 1: Crear tres fixtures de Edición**

Crear un video base y una foto por cada tanda, con marcadores únicos `ED_A_SOURCE`, `ED_B_SOURCE`, `ED_C_SOURCE` y `ED_A_PHOTO`, `ED_B_PHOTO`, `ED_C_PHOTO`. Renderizar una salida por tanda con `video_editor.render_video`, usando una posición/frame distintos por tanda. Cada carpeta `videos_finales/ED_*` debe terminar con exactamente tres archivos; para lograrlo, usar tres videos base del mismo grupo y una foto común de ese grupo. Registrar video base, foto, frame, duración, tamaño y hash.

- [ ] **Step 2: Crear tres fixtures de Tandas**

Para cada categoría crear `inputs/TA_A_P1`, `inputs/TA_A_P2`, y equivalentes B/C. Cada tanda tendrá un P1 y tres P2 con marcadores únicos. Registrar el tanda en `batch_tandas` con `videos.DatabaseManager.add_tanda`; dejar el caption vacío en `TA_A` y `TA_C`, y asociar `CAP_TA_B.txt` a `TA_B`. Ejecutar `videos.render_tanda("TA_A")`, `videos.render_tanda("TA_B")` y `videos.render_tanda("TA_C")` con las rutas parcheadas. Cada carpeta debe producir exactamente tres combinaciones. Después de cada etapa, registrar también `ED_*`, `TA_*` y `FO_*` en `batch_tandas`; solo `ED_A`, `TA_B` y `FO_C` deben conservar su ruta de captions.

- [ ] **Step 3: Crear tres fixtures de Forge**

Usar una fuente ya procesada de cada grupo para demostrar linaje entre etapas: `FO_A` toma una salida de `ED_A`, `FO_B` toma una salida de `TA_B`, y `FO_C` toma una salida de `ED_C`. Procesar una fuente con tres copias (`c01`, `c02`, `c03`) por tanda. Usar configuraciones distintas: `FO_A` `Default/Default`, `FO_B` `Custom` con `crop` y `mirror`, y `FO_C` `Alto/Light`. Registrar `forge_video_registry`, `metadata_fingerprints`, configuración de efectos, fuerza, source hash y output hash.

- [ ] **Step 4: Crear los tres archivos de captions**

`CAP_ED_A.txt` debe contener exactamente el texto corporal `CAPTION_ED_A_UNIQUE` y hashtags `#ed_a_one #ed_a_two`. `CAP_TA_B.txt` debe contener `CAPTION_TA_B_UNIQUE` y hashtags `#ta_b_one #ta_b_two`. `CAP_FO_C.txt` debe contener `CAPTION_FO_C_UNIQUE` y hashtags `#fo_c_one #fo_c_two`. Los tres deben tener dos líneas de texto y una línea de hashtags, para comprobar que el parser conserva el párrafo y no separa cada línea en mensajes.

---

### Task 3: Verificar Edición, Tandas y Forge antes de Logística

**Files:**
- Modify: `tests/support/e2e_pipeline.py`
- Test: `tests/smoke_e2e_pipeline.py`
- Reference: `video_editor.py`, `videos.py`, `metadata_pool.py`, `database.py`

- [ ] **Step 1: Auditar Edición**

Comparar el manifiesto con cada archivo generado: tres outputs por `ED_*`, hash distinto al video de entrada, duración conservada dentro de la tolerancia de FFmpeg, dimensiones válidas y presencia del overlay en el frame configurado. Un output ausente, un output extra o un output cuyo hash no corresponda al source/photo esperados es FAIL.

- [ ] **Step 2: Auditar Tandas**

Para cada `TA_*`, comprobar que el conjunto de nombres corresponde a la combinación cartesiana P1×P2 y que cada nombre usa el contrato real de `videos.py`: `TA_A__P1ID__P2ID.mp4`, `TA_B__P1ID__P2ID.mp4` o `TA_C__P1ID__P2ID.mp4`. El prefijo es el nombre de la tanda; el comparador usa la categoría del manifiesto por separado. Confirmar que `batch_tandas.captions_file_path` apunta a `CAP_TA_B.txt` para `TA_B` y queda vacío para `TA_A` y `TA_C`. No buscar captions dentro del MP4: en este checkout el caption es un dato de tanda/Telegram, no una pista de video.

- [ ] **Step 3: Auditar Forge**

Comprobar tres archivos por `FO_*`, tres filas de `forge_video_registry` por fuente y tres fingerprints únicos. Verificar que cada output remite a la fuente correcta y que las copias no son byte-identical cuando hay micro-edición habilitada. Registrar por separado que el nombre actual `source__cNN.mp4` no contiene necesariamente `CATEGORIA__P1__P2`; esto será una observación para Logística, no una falsa aprobación.

- [ ] **Step 4: Ejecutar las pruebas unitarias existentes**

```powershell
py -m pytest tests/test_video_editor.py tests/test_tanda_sync.py tests/test_forge_ui.py tests/test_forge_presets.py tests/test_variant_strength.py tests/test_telegram_captions.py tests/test_message_format.py -q
```

Expected: el resultado se registra con cantidad exacta de tests y fallos; no se extrapola el resultado al flujo E2E.

---

### Task 4: Distribuir las nueve tandas con Logística

**Files:**
- Modify: `tests/support/e2e_pipeline.py`
- Test: `tests/smoke_e2e_pipeline.py`
- Reference: `Organizador.py`, `gui_premium_v7.py:2417-2777`

- [ ] **Step 1: Ejecutar preview por tanda**

Para cada tanda ejecutar `Organizador.preview_distribution_tanda(tanda, category, 1, False, "1")`. El preview debe listar la categoría correcta, tres cuentas destino y tres videos disponibles. Guardar el texto del preview en el reporte y no considerarlo evidencia suficiente sin inspeccionar el filesystem.

- [ ] **Step 2: Ejecutar la distribución real aislada**

Limpiar solo el `CALENDARIO_POSTEO` temporal y llamar a `Organizador.distribute_tanda(tanda, category, 1, False, "1")` para cada pareja `ED_A/TA_A/FO_A → PRUEBA_CAT_A`, `ED_B/TA_B/FO_B → PRUEBA_CAT_B` y `ED_C/TA_C/FO_C → PRUEBA_CAT_C`. Usar `random.seed(260726)` antes de cada llamada y conservar el texto devuelto.

El resultado esperado son 27 archivos, nueve por categoría, ubicados únicamente en `CALENDARIO_POSTEO/Dia_1/<cuenta>`. No activar fill-up; si falta un archivo, se marca FAIL y no se compensa copiándolo manualmente.

- [ ] **Step 3: Comparar distribución contra la matriz**

Para cada archivo de calendario comprobar:

```text
hash calendario == hash de una salida de videos_finales
categoría del archivo == categoría de la cuenta destino
tanda en el nombre __TANDA_<nombre> == tanda esperada
cuenta pertenece a la categoría esperada
assigned_va de la cuenta pertenece a uno de los tres VAs válidos
```

Un archivo de `ED_A`, `TA_A` o `FO_A` dentro de una cuenta B/C es mezcla de categoría/tanda y debe abrir un FAIL individual con ruta, hash, tanda esperada, cuenta real y VA real.

- [ ] **Step 4: Probar la ruta de dos tandas**

En un segundo run root, ejecutar `distribute_tanda("ED_A", "PRUEBA_CAT_A", 1, False, "1", tanda_name_2="FO_A")`. Verificar que el calendario contiene los seis archivos de ambos orígenes y que el campo `TANDA_<nombre>` no se pierde ni se reemplaza. Esta prueba cubre la selección de segunda tanda de la pestaña “Por Tandas”.

- [ ] **Step 5: Revisar anti-colisión y Forge**

Consultar `fingerprint_history` y aplicar `Organizador.parse_combination_from_filename` al nombre fuente antes del sufijo de Logística. Para Tandas, P1/P2 deben ser no nulos. Para Forge, el nombre fuente `source__cNN` no contiene P1/P2 completos; comparar en su lugar con `forge_video_registry` y registrar el riesgo de anti-colisión de Forge, aunque el destino de cuenta haya sido correcto.

---

### Task 5: Ejecutar Telegram completo con sender falso y conservar evidencia

**Files:**
- Modify: `tests/support/e2e_pipeline.py`
- Create: `tests/support/fake_telegram.py`
- Test: `tests/smoke_e2e_pipeline.py`
- Reference: `organizadortg.py`, `gui_premium_v7.py:3028-3172`

**Interfaces:**
- `FakeTelegramSender.events: list[dict]` contiene metadata y video events.
- `FakeTelegramSender.fake_call(method, data) -> dict` reemplaza `call_tg`.
- `FakeTelegramSender.fake_send_video(...) -> tuple[bool, str]` reemplaza `_send_video_to_topic`.
- `run_telegram_capture(start_date, selected_accounts, captions_file) -> list[dict]` ejecuta `execute_telegram_plan` con los parches activos.

- [ ] **Step 1: Interceptar sin red**

Reemplazar `organizadortg.call_tg`, `organizadortg.get_or_create_topic`, `organizadortg._send_video_to_topic` y `organizadortg.time.sleep`. El fake debe devolver topics deterministas `TOPIC::<telegram_id>::<username>`, registrar el `chat_id` derivado del VA y no abrir nunca una URL HTTP.

- [ ] **Step 2: Mandar todo en una sola corrida**

Seleccionar las nueve cuentas con videos y ejecutar una sola llamada a `execute_telegram_plan` sobre el `Dia_1` generado. El evento esperado es uno por cada uno de los 27 archivos de calendario. Verificar que el `chat_id` de cada evento corresponde al VA de la cuenta y que el topic incluye la misma cuenta.

- [ ] **Step 3: Ejecutar la corrida con un solo archivo de captions**

Pasar `CAP_ED_A.txt`, que es lo que permite actualmente la GUI mediante `self.acct_cap_file or self.tandas_cap_file`. Guardar el resultado sin corregirlo. La comparación debe exigir que `ED_A` use `CAPTION_ED_A_UNIQUE`, `TA_B` use `CAPTION_TA_B_UNIQUE`, `FO_C` use `CAPTION_FO_C_UNIQUE` y que las otras seis tandas no tengan caption. Si cualquiera de los tres captions aparece en una tanda no propietaria, abrir FAIL por contaminación.

- [ ] **Step 4: Ejecutar la corrida sin archivo de captions**

Repetir la corrida completa con `captions_file=None`. El resultado esperado del contrato solicitado es: `ED_A`, `TA_B` y `FO_C` conservan sus captions por tanda; las otras seis siguen sin caption. Si alguno se pierde, registrar que la información de caption no viaja de `batch_tandas` a Telegram cuando todo se manda junto.

La expectativa puede fallar con el checkout actual porque `start_tg_bot` selecciona un solo archivo global y `execute_telegram_plan` usa un solo `pool` que cicla por índice. Ese fallo es precisamente uno de los bugs prioritarios a confirmar con evidencia, no una razón para adaptar el esperado.

---

### Task 6: Implementar el comparador final proceso-versus-resultado

**Files:**
- Modify: `tests/support/e2e_pipeline.py`
- Create: `tests/support/e2e_audit.py`
- Test: `tests/smoke_e2e_pipeline.py`

**Interfaces:**
- `audit_filesystem(manifest, videos_root, calendar_root) -> list[dict]` audita existencia, hashes, conteos y destinos.
- `audit_database(manifest, db_path) -> list[dict]` audita categorías, VAs, cuentas, tandas, historial y Forge registry.
- `audit_telegram(manifest, events) -> list[dict]` audita chat, topic, archivo y caption.
- `render_audit_report(findings, output_path) -> None` escribe JSON y Markdown con cada finding.

- [ ] **Step 1: Normalizar captions antes de comparar**

Comparar el texto corporal con espacios normalizados y hashtags como conjunto, porque `caption_for_video` puede barajar el orden de hashtags. Mantener el contenido multilinea y comprobar que un caption sin archivo produce `None` o ausencia de la clave `caption`, nunca el texto de otro tanda.

- [ ] **Step 2: Aplicar los invariantes de identidad**

El auditor debe emitir un finding individual para cada incumplimiento de:

```text
I1: cada output pertenece a exactamente una tanda y conserva su hash.
I2: cada tanda tiene exactamente tres outputs procesados.
I3: cada tanda se distribuye solo a las tres cuentas de su categoría.
I4: cada cuenta conserva su VA y su Telegram ID.
I5: no se mezclan tandas dentro de una cuenta si la matriz no lo permite.
I6: ED_A, TA_B y FO_C conservan captions distintos y propios.
I7: las otras seis tandas no reciben caption.
I8: ningún caption aparece en una tanda no propietaria.
I9: Telegram envía exactamente una vez cada archivo calendarizado.
I10: el topic de Telegram coincide con la cuenta y el chat del VA.
I11: Tanda y Forge dejan registro consultable de su fuente.
```

- [ ] **Step 3: Generar el informe**

Escribir `audit.json` y `audit.md` dentro del run root. La tabla Markdown debe incluir `stage`, `tanda`, `source_hash`, `output_hash`, `category_expected`, `account_actual`, `va_actual`, `caption_expected`, `caption_actual` y `status`. El resumen debe diferenciar `PASS`, `FAIL` e `INCONCLUSIVE`; una excepción del entorno no se convertirá en PASS.

---

### Task 7: Agregar casos negativos y variaciones para encontrar bugs

**Files:**
- Modify: `tests/support/e2e_pipeline.py`
- Modify: `tests/smoke_e2e_pipeline.py`
- Test: `tests/test_telegram_captions.py`
- Test: `tests/test_tanda_sync.py`
- Test: `tests/test_video_editor.py`

- [ ] **Step 1: Probar captions**

Ejecutar captions multilinea con línea en blanco interna, hashtags exclusivos, archivo vacío, ruta inexistente y tres archivos distintos. Registrar si se agrupa cada párrafo como un caption y si el fallback convierte texto de una tanda en caption de otra.

- [ ] **Step 2: Probar Edición**

Ejecutar un video desaparecido entre preview y render, tamaño de overlay 0, overlay 100%, dos fotos y dos videos. El resultado esperado es error identificable para el archivo perdido, overlay invisible con tamaño 0 y una salida por cada pareja válida.

- [ ] **Step 3: Probar Tandas**

Ejecutar P1 vacío, P2 vacío, tanda no registrada, carpeta renombrada y segunda tanda igual a la primera. Verificar que no se crean archivos silenciosamente incompletos y que `list_and_sync_tandas` no muestra fantasmas.

- [ ] **Step 4: Probar Forge**

Ejecutar sin preview, copias `0`, source inexistente, re-procesado de la misma tanda y `Custom` con rango invertido. Confirmar que el guardado no pisa las copias anteriores y que cada salida conserva una entrada independiente en `forge_video_registry`.

- [ ] **Step 5: Probar Logística**

Ejecutar inventario insuficiente, categoría sin cuentas, tanda inexistente, destino existente y fill-up activado/desactivado. Comparar si la operación deja calendario parcial tras un error; cualquier parcial no documentado es un bug de consistencia.

- [ ] **Step 6: Probar Telegram**

Simular topic inexistente, dos cuentas con VAs distintos, selección de una sola cuenta, pausa/detención y archivo de más de 49 MB. Verificar que un error de una cuenta no redirige sus archivos al chat de otra y que el retry mantiene cuenta, chat y caption.

---

### Task 8: Verificación manual de la GUI y cierre de evidencia

**Files:**
- Reference: `launcher.py`, `gui_premium_v7.py`, `video_editor.py`, `videos.py`, `Organizador.py`, `organizadortg.py`
- Create after execution: `docs/test-reports/2026-07-26-e2e-multimedia-logistica-telegram.md`

- [ ] **Step 1: Abrir la GUI con el fixture temporal**

Iniciar con `py launcher.py` usando la copia aislada de la aplicación. Confirmar visualmente las nueve tandas, tres categorías, tres VAs y nueve cuentas. No iniciar Telegram real.

- [ ] **Step 2: Repetir el flujo en pantalla**

Abrir Edición, Tandas, Forge, Logística y Telegram. En cada pantalla guardar captura o log del nombre de tanda, cantidad de archivos, preview, cuentas seleccionadas y caption mostrado. El smoke programático sigue siendo la fuente de comparación; la captura solo prueba que la GUI expone el mismo estado.

- [ ] **Step 3: Ejecutar las verificaciones de cierre**

```powershell
py -m pytest tests -q
py -m compileall video_editor.py videos.py metadata_pool.py Organizador.py organizadortg.py gui_premium_v7.py -q
py tests/smoke_execute_plan.py
py -m pytest tests/smoke_e2e_pipeline.py -q
git diff --check
```

El reporte debe incluir la salida real de cada comando, el `run_id`, la cantidad esperada/real de archivos y todos los findings. Si el comparador confirma el problema del caption global, se reporta como bug reproducido con rutas y eventos concretos, no como “Telegram no funciona” genérico.

- [ ] **Step 4: Gate opcional de Telegram real**

Solo después de que el sender falso y el auditor pasen los invariantes de cuenta/VA/tanda, y con autorización explícita, repetir usando tres grupos de prueba reales. La credencial no debe estar escrita en el código ni en el reporte; debe llegar por variable segura. Si no hay grupos y credencial de prueba, el estado correcto es `INCONCLUSIVE`, no PASS.

## Self-review del plan

- Cobertura de requisitos: Edición (Tasks 2–3), Tandas (Tasks 2–3), Forge (Tasks 2–3), tres categorías/VAs/cuentas (Task 1), nueve tandas resultantes (Task 1), captions distintos y ausencia de captions (Task 2 y Task 5), Logística (Task 4), Telegram en una sola corrida (Task 5), comparación proceso-versus-final (Task 6) y búsqueda de fallos negativos (Task 7).
- Contrato de identidad: Tandas se auditan por el nombre real `tanda_name__P1__P2`; la categoría se compara desde el manifiesto y la cuenta. Forge se audita además por `forge_video_registry` porque su salida `source__cNN` puede no contener P1/P2.
- Separación de riesgos: DB y filesystem temporales, Telegram falso primero, y gate real independiente.
- Resultado no supuesto: un smoke actual de imports no se presenta como E2E; `tests/smoke_e2e_pipeline.py` será el smoke que compara proceso y resultado.
