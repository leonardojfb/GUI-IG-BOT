# Diseño: Horarios Configurables + Timezones por Set — Método IG Bot

**Fecha:** 2026-05-19  
**Estado:** Aprobado  
**Alcance:** `organizadortg.py`, `database.py`, `gui_premium_v7.py`

---

## Problema

El bot envía todos los mensajes de Telegram de una pasada (sin delay real). El `SCHEDULE` en `organizadortg.py` es hardcodeado y global — no diferencia por VA ni por categoría. Los mensajes tampoco muestran información de timezone, por lo que la VA no sabe en qué hora local debe postear.

## Objetivo

1. Hacer el schedule configurable por set (VA + categoría) y por día de semana desde la GUI.
2. Mostrar en cada mensaje de Telegram la hora en dos zonas: ET (audiencia USA) → timezone local de la VA.
3. Mantener el flujo de envío actual (todo de golpe, sin scheduling real).

---

## Componentes

### 1. Base de datos (`database.py`)

**Columna nueva en `virtual_assistants`:**
```sql
ALTER TABLE virtual_assistants ADD COLUMN timezone TEXT DEFAULT 'America/Argentina/Buenos_Aires';
```

**Tabla nueva `schedule_config`:**
```sql
CREATE TABLE IF NOT EXISTS schedule_config (
    va_name     TEXT NOT NULL,
    category    TEXT NOT NULL,       -- 'promo', 'suicide', 'general'
    day_of_week INTEGER NOT NULL,    -- 0=Lun … 6=Dom
    time_slots  TEXT NOT NULL,       -- JSON array: ["8:00 AM","1:00 PM","7:00 PM"]
    PRIMARY KEY (va_name, category, day_of_week)
);
```

**Métodos nuevos en `DatabaseManager`:**
- `get_schedule_config(va_name, category, day_of_week) → row | None`
- `set_schedule_config(va_name, category, day_of_week, time_slots: list)`
- `delete_schedule_config(va_name, category, day_of_week)` — para "restaurar default"
- `get_va_timezone(va_name) → str` — devuelve timezone IANA o default ART
- `set_va_timezone(va_name, timezone: str)`

**Migración:** `DatabaseManager.__init__` ejecuta los `ALTER TABLE` y `CREATE TABLE` con `IF NOT EXISTS` / `try/except` para no romper DBs existentes.

---

### 2. Lógica de schedule con fallback (`organizadortg.py`)

**SCHEDULE hardcodeado pasa a ser constante de fallback:**
```python
DEFAULT_SCHEDULE = {
    0: ["8:00 AM", "1:00 PM", "7:00 PM", "9:00 AM"],
    1: ["8:00 AM", "12:00 PM", "7:00 PM", "9:00 AM"],
    2: ["9:00 AM", "1:00 PM", "9:00 PM", "10:00 AM"],
    3: ["8:00 AM", "1:00 PM", "7:00 PM", "9:30 AM"],
    4: ["9:00 AM", "1:00 PM", "8:00 PM", "10:00 AM"],
    5: ["11:00 AM", "3:00 PM", "8:00 PM", "12:00 PM"],
    6: ["12:00 PM", "4:00 PM", "9:00 PM", "1:00 PM"]
}
```
Todos los tiempos están expresados en **Eastern Time (ET)**.

**Nueva función `get_slots_for_set`:**
```python
def get_slots_for_set(va_name, category, day_of_week, db) -> list[str]:
    row = db.get_schedule_config(va_name, category, day_of_week)
    if row:
        return json.loads(row['time_slots'])
    return DEFAULT_SCHEDULE[day_of_week]
```

Reemplaza la línea `tiempos = SCHEDULE[fecha_envio.weekday()]` por una llamada a `get_slots_for_set` usando el `va_name` y `category` del set actual en el loop.

**Nueva función `convert_et_to_va_tz`:**
```python
def convert_et_to_va_tz(time_str: str, va_tz_str: str) -> tuple[str, str]:
    """
    Convierte "8:00 AM" (ET) al timezone de la VA.
    Retorna ("8:00 AM ET (Nueva York)", "9:00 AM ART (Buenos Aires)")
    """
```
Usa `zoneinfo` (stdlib Python 3.9+). Si `zoneinfo` no está disponible, fallback a `pytz`.

**Tabla de abreviaturas:**
| Timezone IANA | Abreviatura | Ciudad |
|---|---|---|
| `America/New_York` | ET | Nueva York |
| `America/Argentina/Buenos_Aires` | ART | Buenos Aires |
| `America/Chicago` | CT | Chicago |
| `America/Los_Angeles` | PT | Los Ángeles |
| `Europe/Madrid` | CET | Madrid |
| `Europe/London` | GMT/BST | Londres |

**Formato del mensaje resultante:**
```
PROMO
Día: 2026-05-19
⏰ 8:00 AM ET (Nueva York)
   → 9:00 AM ART (Buenos Aires)
Formato: Reel
```

---

### 3. UI (`gui_premium_v7.py`)

#### 3a. Timezone por VA (en panel admin de VAs)

Agrega un dropdown `CTkOptionMenu` al lado del campo TG ID en cada fila de VA:

```
[VA: Karenita]  [TG ID: ...]  [Timezone: America/Argentina/Buenos_Aires ▼]  [Guardar]
```

Opciones predefinidas (lista en el código):
```python
TIMEZONE_OPTIONS = [
    "America/Argentina/Buenos_Aires",
    "America/New_York",
    "America/Chicago",
    "America/Los_Angeles",
    "Europe/Madrid",
    "Europe/London",
]
```

Al presionar Guardar llama a `db.set_va_timezone(va_name, selected_tz)`.

#### 3b. Panel "⏰ Configurar Horarios" (nueva subsección en pestaña Telegram)

Ubicación: colapsable, entre el filtro de cuentas y el botón "Iniciar Bot".

**Layout:**

- Header con botón `[▶ Configurar Horarios]` para expandir/colapsar.
- Cuando está expandido: `CTkScrollableFrame` con una fila por set.
- Cada fila muestra: `VA | Categoría | Lun | Mar | Mié | Jue | Vie | Sáb | Dom | [Editar] [Default]`
- Las celdas muestran los slots actuales en formato compacto (ej: `8,13,19`) o "default" en gris si no hay config.
- `[Editar]` abre `CTkToplevel` con 7 campos de texto (uno por día), pre-rellenados con los slots actuales. Formato de entrada: horas separadas por coma (`8:00 AM, 1:00 PM, 7:00 PM`). Tiene botón `[Guardar]` y `[Cancelar]`.
- `[Default]` llama a `db.delete_schedule_config` para los 7 días del set y refresca la grilla.

**Generación de filas:** al abrir el panel, se detectan las combinaciones (VA × categoría) presentes en CALENDARIO_POSTEO. Si CALENDARIO_POSTEO no existe, se muestran solo las VAs de la DB con categorías conocidas (promo, suicide, general).

---

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `database.py` | Migración `timezone` + tabla `schedule_config` + 5 métodos nuevos |
| `organizadortg.py` | `DEFAULT_SCHEDULE`, `get_slots_for_set()`, `convert_et_to_va_tz()`, actualización de `meta` string, carga de `va_timezone` en `get_accounts_with_va_info()` |
| `gui_premium_v7.py` | Dropdown timezone en panel VA + panel "Configurar Horarios" colapsable |

## Archivos NO modificados

- `telegram_core.py` — sin cambios
- `telegram_state_v11.json` — sin cambios
- Estructura de CALENDARIO_POSTEO — sin cambios

---

## Criterios de aceptación

1. Un set sin config en DB muestra "default" en la grilla y usa `DEFAULT_SCHEDULE` al enviar.
2. Un set con config guardada usa sus propios slots al enviar.
3. El mensaje Telegram muestra dos líneas de timezone correctamente convertidas.
4. La timezone de una VA nueva es ART por defecto.
5. El botón `[Default]` restaura el comportamiento anterior sin errores.
6. DBs existentes migran sin errores al arrancar (columna y tabla creadas si no existen).