# CHANGELOG — Método IG VIDEOS

Historial completo de cambios basado en el repositorio Git del proyecto.
Rango: 2026-04-25 → 2026-04-26 · 8 commits · Autor: leonardojfb

---

## [433e9d3] — "MALPARIDO" · 2026-04-26 19:56

Commit final. Limpieza y refinamiento del reporte de distribución, incorporación de `organizadortg.py` al tracking de Git.

### Organizador.py (907 líneas → estado actual)
- Reescritura del reporte `preview_distribution_tanda()`:
  - Título cambia a "REPORTE ESTRATÉGICO DE DISTRIBUCIÓN"
  - Desglose por cuenta con columnas: `REAL | FILL-UP`
  - Usa `db.get_all_accounts()` + filtro manual en lugar de `get_accounts_by_type()`
  - Lógica de días: `try/except` al parsear días fijos, fallback a `math.floor()`
  - Calcula fill-up necesario per-cuenta individualmente
- `duplicate import math` acumulado (artifact de edición iterativa — sin efecto funcional)

### database.py
- Pequeños ajustes de métodos

### gui_unificada.py
- Ajustes menores a la GUI V6

### organizadortg.py (208 líneas) — **añadido a Git por primera vez**
- Script de Telegram que organiza y envía videos desde `CALENDARIO_POSTEO/`
- Mantiene estado en `telegram_state_v11.json` y captions en `captions.txt`

---

## [ea51e95] — "CASIII" · 2026-04-26 16:34

Nuevas funciones de distribución conectadas a la GUI, utilidades de debug.

### Nuevos archivos
- **`debug_db.py`** (11 líneas) — helper rápido para inspeccionar la base de datos
- **`vercuentas.py`** (9 líneas) — imprime la lista de cuentas registradas en DB

### Organizador.py
- **Nueva función `preview_distribution_tanda()`** — reporte logístico detallado:
  - Toma `tanda_name`, `category_dest`, `daily_quota`, `use_fillup`, `days_to_organize`
  - Calcula días de alcance real (`total_videos / vids_por_dia_grupo`)
  - Modo `"MAX"`: usa `math.ceil()` para redondear días hacia arriba
  - Proyecta fill-up total necesario
  - Tabla por cuenta con VA asignado y total de videos
- **Nueva función `distribute_tanda()`** — ejecución real de la distribución:
  - Crea carpetas por cuenta en `CALENDARIO_POSTEO/`
  - Copia videos (usa `shutil.copy`)
  - Registra cada video en `fingerprint_history` vía `db.add_video_to_history()`
  - Extrae P1 y P2 del nombre de archivo (`TANDA__P1__P2.mp4`)

### gui_unificada.py — V6 "Gestión Total, Limpieza Masiva y Anti-Choque Global"
- **Nueva clase `WorkerThread`** — ejecuta tareas pesadas en hilo separado sin bloquear la UI
  - Captura resultado con lambda frozen (`lambda r=res: ...`) para evitar closures rotas
  - Llama al callback via `root.after(0, ...)` — thread-safe
- **Nueva clase `SelectionDialog`** — diálogo Toplevel con Combobox + Entry combinados
  - Permite seleccionar un item existente O escribir uno nuevo
  - Dark theme (`#2d2d44`, `#4ecdc4`, `#ff4757`)

### database.py
- Ajustes de métodos de consulta

---

## [3aa8391] — "listo" · 2026-04-26 15:12

Correcciones menores post-refactor de `casi casi`.

### gui_unificada.py
- Bugfixes pequeños (9 cambios de línea)

### videos.py
- Refactor parcial del procesamiento de video (91 cambios de línea)

---

## [599cb5b] — "casi casi" · 2026-04-26 14:46

El commit más grande en volumen de cambios. Gran reescritura de la GUI y limpieza de la DB.

### Nuevo archivo
- **`reparar_db.py`** (61 líneas) — utilidad para reparar inconsistencias en la base de datos SQLite

### database.py — refactor masivo (659 → simplificado)
- Limpieza completa del código heredado
- Consolidación de hotfixes en un único bloque de `ALTER TABLE` iterativo
- Simplificación de métodos CRUD

### gui_unificada.py — mayor overhaul (888 líneas de cambios)
- Reescritura extensa de la interfaz gráfica
- Integración de múltiples pestañas y funcionalidades de gestión

### captions.txt
- Actualización del pool de captions disponibles

---

## [3c7e4ef] — "prueba" · 2026-04-26 13:22

Refactor profundo de `Organizador.py` y reducción del esquema de base de datos a su forma definitiva.

### Organizador.py — Anti-Choque Global + Fill-up mejorado
- **Fix**: Variable `base分配` (tenía un carácter chino) → renombrada `base_count`
- **Nueva función `parse_combination_from_filename()`**:
  - Extrae tupla `(P1, P2)` del nombre de archivo con formato `CATEGORIA__P1ID__P2ID.mp4`
- **Nueva función `get_all_used_combinations()`**:
  - Consulta toda la tabla `fingerprint_history` para obtener combinaciones ya publicadas globalmente (todas las cuentas)
- **Anti-Choque Global por día** — 4 funciones nuevas:
  - `is_p1_used_today(day_number, p1_id)` — verifica si un P1 ya se usó hoy
  - `is_p2_used_today(day_number, p2_id)` — verifica si un P2 ya se usó hoy
  - `mark_p1_used_today(day_number, p1_id)` — marca P1 como usado en el día
  - `mark_p2_used_today(day_number, p2_id)` — marca P2 como usado en el día
  - Dictionaries globales `global_used_p1` y `global_used_p2` para tracking en memoria
- **`generate_fill_up_combinations()` mejorada**:
  - Nuevos params: `used_combinations: set`, `day_number: int`
  - Implementa anti-choque al generar combinaciones fill-up

### database.py — "VERSIÓN DEFINITIVA V6"
- **Tablas eliminadas del schema**: `mix_rules`, `video_types`, `system_config`, `activity_logs`
- **Columnas eliminadas del schema base**: `allowed_video_types`, `status`, `last_post_date`, `tg_topic_id` (se añaden via hotfix si hacen falta)
- `fingerprint_history` simplificada: quita `video_type_id`, añade `p1_source`, `p2_source`
- `batch_tandas` simplificada: quita `status`
- `virtual_accounts` simplificada: quita `allowed_video_types`, `status`, etc. del schema base
- Patrón de inicialización: hotfixes primero → luego `SCHEMA` → rescate de categorías
- Import limpio: eliminados `json`, `datetime`, `typing`
- Conexión con `check_same_thread=False`
- **`add_va()`** ahora usa `INSERT OR IGNORE`
- **Nueva `delete_category()`** — borra una categoría de la tabla `account_categories`

### gui_unificada.py, videos.py
- Ajustes en línea con el nuevo esquema de DB

---

## [4a91093] — "prueba" · 2026-04-25 21:13

Integración con Telegram, versión SAAS de la base de datos, lógica de fill-up inicial.

### Nuevo archivo
- **`telegram_core.py`** (274 líneas) — bot de Telegram para posteo automático:
  - Token hardcodeado, chat ID de grupo
  - `load_clean_captions()` — parsea `captions.txt` con regex
  - `shuffle_hashtags()` — mezcla los hashtags de los captions
  - Lee estado desde `telegram_state_v11.json` y `fingerprint_history.json`
  - Integra `DatabaseManager` para consultar cuentas y VAs

### Organizador.py
- **`FILL_UP_ENABLED = True`** — nuevo flag global
- **`generate_fill_up_combinations()`** — primera versión:
  - Busca carpetas P1/P2 de la tanda en `inputs/`
  - Genera combinaciones cruzadas al azar cuando no hay stock suficiente
- **`check_collision()`** y **`get_account_used_combinations()`** — primera versión del anti-choque por cuenta

### database.py — versión "SAAS COMPLETA"
- Añadidas columnas: `allowed_video_types`, `status`, `tg_topic_id`, `tg_group_id`
- Tabla `mix_rules` — reglas de mezcla P1/P2 (luego eliminada en V6)
- Migraciones en caliente (hotfixes) vía `ALTER TABLE ... ADD COLUMN` con `try/except`
- `update_va_telegram_group()` — vincula un VA a un grupo de Telegram

### gui_unificada.py, videos.py, database.py
- Refactor masivo de las tres piezas principales

---

## [13a4123] — "V1.1" · 2026-04-25 14:07

Primera versión con base de datos SQL. Reemplaza datos estáticos por SQLite.

### Nuevos archivos
- **`database.py`** (568 líneas) — `DatabaseManager` con esquema inicial completo:
  - Tablas: `account_categories`, `virtual_assistants`, `virtual_accounts`, `video_types`, `mix_rules`, `batch_tandas`, `fingerprint_history`, `system_config`, `activity_logs`
  - Métodos CRUD para VAs, cuentas, tipos de video, fingerprints
- **`gui_unificada.py`** (544 líneas) — primera GUI unificada (Tkinter)
- **`organizador.db`** — base de datos SQLite creada

### Archivos migrados a `archive_legacy/`
- `accounts_promo.txt` → `archive_legacy/accounts_promo.txt`
- `accounts_suicide.txt` → `archive_legacy/accounts_suicide.txt`
- `fingerprint_history.json` → `archive_legacy/fingerprint_history.json`
- `telegram_state_v11.json` → `archive_legacy/telegram_state_v11.json`

### Organizador.py
- Importa `DatabaseManager`
- `get_distribution_config()` — lee configuración de distribución desde DB en lugar de constantes hardcodeadas
- `get_categories_from_db()` — obtiene tipos de video activos desde DB

### videos.py
- Ajustes para compatibilidad con nuevo sistema

---

## [e5ec62a] — "Estructura inicial limpia" · 2026-04-25 13:49

Commit inicial. Proyecto desde cero con datos estáticos.

### Archivos creados
| Archivo | Líneas | Propósito |
|---|---|---|
| `Organizador.py` | 121 | Motor de distribución (constantes hardcodeadas) |
| `gui_organizador.py` | 498 | GUI original (Tkinter, primera versión) |
| `organizador_simple.py` | 534 | Versión simplificada del organizador |
| `organizadortg.py` | 172 | Script de Telegram (v1) |
| `videos.py` | 115 | Procesamiento y renombrado de videos |
| `accounts_promo.txt` | — | Lista de cuentas PROMO |
| `accounts_suicide.txt` | — | Lista de cuentas SUICIDE |
| `captions.txt` | 94 | Pool de captions para postear |
| `fingerprint_history.json` | 632 | Historial de videos publicados |
| `telegram_state_v11.json` | 17 | Estado del bot de Telegram |
| `README.txt` | 74 | Documentación inicial |
| `reporte_organizacion.txt` | 10 | Reporte de organización |

### Configuración inicial (`Organizador.py`)
```python
DAILY_GOAL = 46
PREF_SUICIDE = 22
PREF_PROMO = 24
```
- Distribución por entropía (round-robin por P1ID)
- Sin base de datos — datos leídos directo de .txt y .json

---

## Estado actual del proyecto (HEAD)

| Archivo | Líneas | Rol |
|---|---|---|
| `gui_unificada.py` | 962 | GUI principal Tkinter (V6) |
| `Organizador.py` | 907 | Motor de distribución con Fill-up y Anti-Choque |
| `database.py` | 179 | DatabaseManager SQLite V6 (limpio y definitivo) |
| `organizadortg.py` | 208 | Bot / organizador de Telegram |
| `videos.py` | 283 | Procesamiento de videos |
| `telegram_core.py` | ~274 | Core del bot Telegram |
| `reparar_db.py` | 61 | Utilidad de reparación de DB |
| `debug_db.py` | 11 | Debug rápido de DB |
| `vercuentas.py` | 9 | Visor rápido de cuentas |
| `gui_organizador.py` | ~498 | GUI original (legacy, sin uso activo) |
| `organizador_simple.py` | ~534 | Organizador simple (legacy) |

### Tablas SQLite activas (schema V6)
- `account_categories` — pestañas/categorías de la GUI
- `virtual_assistants` — VAs con grupo Telegram opcional
- `virtual_accounts` — cuentas IG con VA asignado
- `batch_tandas` — tandas de videos P1/P2
- `fingerprint_history` — historial de videos publicados por cuenta (anti-choque)
