# Horarios Configurables + Timezones por Set — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir configurar horarios de posteo por set (VA + categoría) y por día de la semana desde la GUI, con timezone por VA y display dual ET → hora local en cada mensaje de Telegram.

**Architecture:** Tres capas: (1) DB — nueva tabla `schedule_config` + columna `timezone` en `virtual_assistants` con migración no destructiva; (2) Lógica — `organizadortg.py` resuelve slots con fallback a constante `DEFAULT_SCHEDULE` y convierte ET → tz de la VA usando `zoneinfo`; (3) UI — dropdown de timezone en panel admin de VAs + panel colapsable "Configurar Horarios" en pestaña Telegram con grilla editable por set.

**Tech Stack:** Python 3.14, SQLite3, `zoneinfo` (stdlib), CustomTkinter (`ctk`), `unittest` (stdlib).

**Reference spec:** `docs/superpowers/specs/2026-05-19-metodo-ig-schedule-timezone-design.md`

---

## Archivos afectados

| Archivo | Acción | Resumen |
|---|---|---|
| `database.py` | Modify | Migración + 5 métodos nuevos |
| `organizadortg.py` | Modify | `DEFAULT_SCHEDULE`, `get_slots_for_set()`, `convert_et_to_va_tz()`, format del `meta` |
| `gui_premium_v7.py` | Modify | Dropdown TZ + panel "Configurar Horarios" |
| `tests/test_database_schedule.py` | Create | Tests de los métodos nuevos de DB |
| `tests/test_timezone_conversion.py` | Create | Tests de `convert_et_to_va_tz` |
| `tests/test_schedule_fallback.py` | Create | Tests de `get_slots_for_set` |

**Convención de tests:** se usa `unittest` (stdlib, sin dependencias nuevas). Se ejecutan con `py -m unittest tests/<archivo>.py`.

---

## Task 1: Migración DB — columna `timezone` en `virtual_assistants`

**Files:**
- Modify: `database.py:87-99` (extender `_migrate_columns`)
- Test: `tests/test_database_schedule.py` (nuevo)

- [ ] **Step 1: Crear directorio tests/ y archivo de test inicial**

Crear `tests/__init__.py` vacío y `tests/test_database_schedule.py`:

```python
# tests/test_database_schedule.py
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TimezoneColumnTest(unittest.TestCase):
    def setUp(self):
        self.tmp_db_fd, self.tmp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tmp_db_fd)
        import database
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_db_path

    def tearDown(self):
        import database
        database.DB_PATH = self._original_db_path
        if os.path.exists(self.tmp_db_path):
            os.unlink(self.tmp_db_path)

    def test_timezone_column_exists_after_init(self):
        from database import DatabaseManager
        db = DatabaseManager()
        cur = db.conn.cursor()
        cur.execute("PRAGMA table_info(virtual_assistants)")
        cols = [row["name"] for row in cur.fetchall()]
        self.assertIn("timezone", cols)
        db.close()

    def test_timezone_default_is_buenos_aires(self):
        from database import DatabaseManager
        db = DatabaseManager()
        db.add_va("TestVA")
        cur = db.conn.cursor()
        cur.execute("SELECT timezone FROM virtual_assistants WHERE name = ?", ("TestVA",))
        row = cur.fetchone()
        self.assertEqual(row["timezone"], "America/Argentina/Buenos_Aires")
        db.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `py -m unittest tests/test_database_schedule.py -v`
Expected: FAIL — la columna `timezone` no existe.

- [ ] **Step 3: Agregar migración en `database.py`**

En `database.py`, dentro de `_migrate_columns` (línea 87-99), agregar al final de la lista `migrations`:

```python
    def _migrate_columns(self):
        """Agrega columnas nuevas si aún no existen (migraciones no destructivas)."""
        migrations = [
            "ALTER TABLE virtual_accounts ADD COLUMN ig_status TEXT DEFAULT 'unknown'",
            "ALTER TABLE virtual_accounts ADD COLUMN ig_label  TEXT DEFAULT 'nuevo'",
            "ALTER TABLE virtual_assistants ADD COLUMN timezone TEXT DEFAULT 'America/Argentina/Buenos_Aires'",
        ]
        cur = self.conn.cursor()
        for sql in migrations:
            try:
                cur.execute(sql)
                self.conn.commit()
            except Exception:
                pass  # Columna ya existe
```

- [ ] **Step 4: Ejecutar el test y verificar que pasa**

Run: `py -m unittest tests/test_database_schedule.py -v`
Expected: PASS — 2 tests OK.

- [ ] **Step 5: Commit**

```bash
git add database.py tests/__init__.py tests/test_database_schedule.py
git commit -m "feat(db): add timezone column to virtual_assistants with ART default"
```

---

## Task 2: Tabla `schedule_config` en DB

**Files:**
- Modify: `database.py:11-68` (agregar `CREATE TABLE` al SCHEMA)
- Test: `tests/test_database_schedule.py` (agregar caso)

- [ ] **Step 1: Agregar test que valida la existencia de la tabla**

Agregar al final de `tests/test_database_schedule.py` (antes de `if __name__`):

```python
class ScheduleConfigTableTest(unittest.TestCase):
    def setUp(self):
        self.tmp_db_fd, self.tmp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tmp_db_fd)
        import database
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_db_path

    def tearDown(self):
        import database
        database.DB_PATH = self._original_db_path
        if os.path.exists(self.tmp_db_path):
            os.unlink(self.tmp_db_path)

    def test_schedule_config_table_exists(self):
        from database import DatabaseManager
        db = DatabaseManager()
        cur = db.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedule_config'")
        row = cur.fetchone()
        self.assertIsNotNone(row)
        db.close()

    def test_schedule_config_primary_key_composite(self):
        from database import DatabaseManager
        db = DatabaseManager()
        cur = db.conn.cursor()
        cur.execute("PRAGMA table_info(schedule_config)")
        pk_cols = [row["name"] for row in cur.fetchall() if row["pk"] > 0]
        self.assertEqual(set(pk_cols), {"va_name", "category", "day_of_week"})
        db.close()
```

- [ ] **Step 2: Ejecutar tests y verificar que fallan**

Run: `py -m unittest tests/test_database_schedule.py -v`
Expected: 2 nuevos tests FAIL (no such table: schedule_config).

- [ ] **Step 3: Agregar CREATE TABLE al SCHEMA**

En `database.py:11-68`, agregar al final del string `SCHEMA` (antes del `"""` de cierre):

```python
CREATE TABLE IF NOT EXISTS schedule_config (
    va_name     TEXT NOT NULL,
    category    TEXT NOT NULL,
    day_of_week INTEGER NOT NULL,
    time_slots  TEXT NOT NULL,
    PRIMARY KEY (va_name, category, day_of_week)
);
```

- [ ] **Step 4: Ejecutar tests y verificar que pasan**

Run: `py -m unittest tests/test_database_schedule.py -v`
Expected: 4 tests OK.

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_database_schedule.py
git commit -m "feat(db): add schedule_config table with (va_name, category, day_of_week) PK"
```

---

## Task 3: Métodos DB — `get_schedule_config`, `set_schedule_config`, `delete_schedule_config`

**Files:**
- Modify: `database.py` (agregar métodos al final de la clase `DatabaseManager`, antes de la siguiente sección)
- Test: `tests/test_database_schedule.py` (agregar casos)

- [ ] **Step 1: Agregar tests para los 3 métodos**

Agregar al final de `tests/test_database_schedule.py` (antes de `if __name__`):

```python
class ScheduleConfigCRUDTest(unittest.TestCase):
    def setUp(self):
        self.tmp_db_fd, self.tmp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tmp_db_fd)
        import database
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_db_path
        from database import DatabaseManager
        self.db = DatabaseManager()

    def tearDown(self):
        self.db.close()
        import database
        database.DB_PATH = self._original_db_path
        if os.path.exists(self.tmp_db_path):
            os.unlink(self.tmp_db_path)

    def test_set_and_get_schedule_config(self):
        self.db.set_schedule_config("VA1", "promo", 0, ["8:00 AM", "1:00 PM"])
        row = self.db.get_schedule_config("VA1", "promo", 0)
        self.assertIsNotNone(row)
        import json
        slots = json.loads(row["time_slots"])
        self.assertEqual(slots, ["8:00 AM", "1:00 PM"])

    def test_get_returns_none_when_missing(self):
        row = self.db.get_schedule_config("NoExiste", "promo", 0)
        self.assertIsNone(row)

    def test_set_overwrites_existing(self):
        self.db.set_schedule_config("VA1", "promo", 0, ["8:00 AM"])
        self.db.set_schedule_config("VA1", "promo", 0, ["9:00 PM", "11:00 PM"])
        row = self.db.get_schedule_config("VA1", "promo", 0)
        import json
        self.assertEqual(json.loads(row["time_slots"]), ["9:00 PM", "11:00 PM"])

    def test_delete_schedule_config(self):
        self.db.set_schedule_config("VA1", "promo", 0, ["8:00 AM"])
        self.db.delete_schedule_config("VA1", "promo", 0)
        self.assertIsNone(self.db.get_schedule_config("VA1", "promo", 0))
```

- [ ] **Step 2: Ejecutar tests y verificar que fallan**

Run: `py -m unittest tests/test_database_schedule.py -v`
Expected: 4 nuevos tests FAIL (AttributeError: no attribute 'set_schedule_config').

- [ ] **Step 3: Implementar los 3 métodos en `database.py`**

En `database.py`, después del método `update_va_telegram_group` (línea 140), agregar una nueva sección:

```python
    # ==================== SCHEDULE CONFIG ====================
    def get_schedule_config(self, va_name: str, category: str, day_of_week: int):
        """Devuelve la fila de schedule_config para el set, o None si no existe."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM schedule_config WHERE va_name = ? AND category = ? AND day_of_week = ?",
            (va_name, category, day_of_week),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def set_schedule_config(self, va_name: str, category: str, day_of_week: int, time_slots: list):
        """Inserta o reemplaza el schedule de un set para un día."""
        import json
        cur = self.conn.cursor()
        cur.execute(
            """INSERT OR REPLACE INTO schedule_config
               (va_name, category, day_of_week, time_slots)
               VALUES (?, ?, ?, ?)""",
            (va_name, category, day_of_week, json.dumps(time_slots)),
        )
        self.conn.commit()

    def delete_schedule_config(self, va_name: str, category: str, day_of_week: int):
        """Elimina la config de un set para un día — el set volverá al fallback DEFAULT_SCHEDULE."""
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM schedule_config WHERE va_name = ? AND category = ? AND day_of_week = ?",
            (va_name, category, day_of_week),
        )
        self.conn.commit()
```

- [ ] **Step 4: Ejecutar tests y verificar que pasan**

Run: `py -m unittest tests/test_database_schedule.py -v`
Expected: 8 tests OK.

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_database_schedule.py
git commit -m "feat(db): add get/set/delete_schedule_config methods"
```

---

## Task 4: Métodos DB — `get_va_timezone`, `set_va_timezone`

**Files:**
- Modify: `database.py` (sección VAs)
- Test: `tests/test_database_schedule.py`

- [ ] **Step 1: Agregar tests**

Agregar al final de `tests/test_database_schedule.py` (antes de `if __name__`):

```python
class VATimezoneTest(unittest.TestCase):
    def setUp(self):
        self.tmp_db_fd, self.tmp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tmp_db_fd)
        import database
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_db_path
        from database import DatabaseManager
        self.db = DatabaseManager()

    def tearDown(self):
        self.db.close()
        import database
        database.DB_PATH = self._original_db_path
        if os.path.exists(self.tmp_db_path):
            os.unlink(self.tmp_db_path)

    def test_get_va_timezone_returns_default_for_new_va(self):
        self.db.add_va("VA1")
        tz = self.db.get_va_timezone("VA1")
        self.assertEqual(tz, "America/Argentina/Buenos_Aires")

    def test_set_and_get_va_timezone(self):
        self.db.add_va("VA1")
        self.db.set_va_timezone("VA1", "America/New_York")
        tz = self.db.get_va_timezone("VA1")
        self.assertEqual(tz, "America/New_York")

    def test_get_va_timezone_returns_default_when_va_missing(self):
        tz = self.db.get_va_timezone("NoExiste")
        self.assertEqual(tz, "America/Argentina/Buenos_Aires")
```

- [ ] **Step 2: Ejecutar tests y verificar que fallan**

Run: `py -m unittest tests/test_database_schedule.py -v`
Expected: 3 nuevos tests FAIL.

- [ ] **Step 3: Implementar los métodos en `database.py`**

En `database.py`, después de `update_va_telegram_group` (línea 140), agregar:

```python
    def get_va_timezone(self, va_name: str) -> str:
        """Devuelve el timezone IANA de una VA. Si la VA no existe o no tiene tz, devuelve ART."""
        cur = self.conn.cursor()
        cur.execute("SELECT timezone FROM virtual_assistants WHERE name = ?", (va_name,))
        row = cur.fetchone()
        if row and row["timezone"]:
            return row["timezone"]
        return "America/Argentina/Buenos_Aires"

    def set_va_timezone(self, va_name: str, timezone: str):
        """Actualiza el timezone IANA de una VA."""
        cur = self.conn.cursor()
        cur.execute("UPDATE virtual_assistants SET timezone = ? WHERE name = ?", (timezone, va_name))
        self.conn.commit()
```

- [ ] **Step 4: Ejecutar tests y verificar que pasan**

Run: `py -m unittest tests/test_database_schedule.py -v`
Expected: 11 tests OK.

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_database_schedule.py
git commit -m "feat(db): add get/set_va_timezone methods"
```

---

## Task 5: Constante `DEFAULT_SCHEDULE` y función `get_slots_for_set` en `organizadortg.py`

**Files:**
- Modify: `organizadortg.py:249-254` (extraer SCHEDULE a constante de módulo) + agregar función nueva
- Test: `tests/test_schedule_fallback.py` (nuevo)

- [ ] **Step 1: Crear test**

Crear `tests/test_schedule_fallback.py`:

```python
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class GetSlotsForSetTest(unittest.TestCase):
    def setUp(self):
        self.tmp_db_fd, self.tmp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.tmp_db_fd)
        import database
        self._original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp_db_path
        from database import DatabaseManager
        self.db = DatabaseManager()

    def tearDown(self):
        self.db.close()
        import database
        database.DB_PATH = self._original_db_path
        if os.path.exists(self.tmp_db_path):
            os.unlink(self.tmp_db_path)

    def test_falls_back_to_default_schedule_when_no_config(self):
        from organizadortg import get_slots_for_set, DEFAULT_SCHEDULE
        slots = get_slots_for_set("VA1", "promo", 0, self.db)
        self.assertEqual(slots, DEFAULT_SCHEDULE[0])

    def test_returns_custom_slots_when_config_exists(self):
        from organizadortg import get_slots_for_set
        self.db.set_schedule_config("VA1", "promo", 2, ["11:00 AM", "5:00 PM"])
        slots = get_slots_for_set("VA1", "promo", 2, self.db)
        self.assertEqual(slots, ["11:00 AM", "5:00 PM"])

    def test_default_schedule_has_all_seven_days(self):
        from organizadortg import DEFAULT_SCHEDULE
        for d in range(7):
            self.assertIn(d, DEFAULT_SCHEDULE)
            self.assertGreater(len(DEFAULT_SCHEDULE[d]), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar test y verificar que falla**

Run: `py -m unittest tests/test_schedule_fallback.py -v`
Expected: FAIL — `get_slots_for_set` no existe.

- [ ] **Step 3: Refactor de `organizadortg.py`**

En `organizadortg.py`:

3a. Mover el `SCHEDULE` que está dentro de `execute_telegram_plan` (líneas 249-254) a una constante a nivel de módulo, justo después de los imports y antes de `def load_json` (línea 24). Renombrar a `DEFAULT_SCHEDULE`:

```python
# --- 1.5. SCHEDULE DEFAULT (horarios estratégicos en Eastern Time / Nueva York) ---
DEFAULT_SCHEDULE = {
    0: ["8:00 AM", "1:00 PM", "7:00 PM", "9:00 AM"],
    1: ["8:00 AM", "12:00 PM", "7:00 PM", "9:00 AM"],
    2: ["9:00 AM", "1:00 PM", "9:00 PM", "10:00 AM"],
    3: ["8:00 AM", "1:00 PM", "7:00 PM", "9:30 AM"],
    4: ["9:00 AM", "1:00 PM", "8:00 PM", "10:00 AM"],
    5: ["11:00 AM", "3:00 PM", "8:00 PM", "12:00 PM"],
    6: ["12:00 PM", "4:00 PM", "9:00 PM", "1:00 PM"],
}
```

3b. Eliminar las líneas 249-254 (el `SCHEDULE = {...}` dentro de la función).

3c. Agregar la función `get_slots_for_set` después del `DEFAULT_SCHEDULE`:

```python
def get_slots_for_set(va_name: str, category: str, day_of_week: int, db_manager) -> list:
    """
    Devuelve los time slots configurados para un set (VA + categoría) en un día.
    Si no hay config en DB, cae al DEFAULT_SCHEDULE estratégico ET.
    """
    row = db_manager.get_schedule_config(va_name, category, day_of_week)
    if row:
        import json
        return json.loads(row["time_slots"])
    return DEFAULT_SCHEDULE[day_of_week]
```

- [ ] **Step 4: Ejecutar test y verificar que pasa**

Run: `py -m unittest tests/test_schedule_fallback.py -v`
Expected: 3 tests OK.

- [ ] **Step 5: Commit**

```bash
git add organizadortg.py tests/test_schedule_fallback.py
git commit -m "feat(bot): extract DEFAULT_SCHEDULE + add get_slots_for_set fallback resolver"
```

---

## Task 6: Función `convert_et_to_va_tz` en `organizadortg.py`

**Files:**
- Modify: `organizadortg.py` (agregar función + tabla de abreviaturas)
- Test: `tests/test_timezone_conversion.py` (nuevo)

- [ ] **Step 1: Crear test**

Crear `tests/test_timezone_conversion.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TimezoneConversionTest(unittest.TestCase):
    def test_et_to_art_basic(self):
        from organizadortg import convert_et_to_va_tz
        et_label, local_label = convert_et_to_va_tz("8:00 AM", "America/Argentina/Buenos_Aires")
        self.assertIn("ET", et_label)
        self.assertIn("Nueva York", et_label)
        self.assertIn("ART", local_label)
        self.assertIn("Buenos Aires", local_label)
        # Diferencia ART vs ET es +1h (con DST puede ser +2h)
        self.assertTrue(
            local_label.startswith("9:00 AM") or local_label.startswith("10:00 AM"),
            f"Expected 9 or 10 AM, got {local_label}",
        )

    def test_et_to_et_same_time(self):
        from organizadortg import convert_et_to_va_tz
        et_label, local_label = convert_et_to_va_tz("8:00 AM", "America/New_York")
        self.assertTrue(local_label.startswith("8:00 AM"))

    def test_pm_time(self):
        from organizadortg import convert_et_to_va_tz
        et_label, local_label = convert_et_to_va_tz("7:00 PM", "America/Argentina/Buenos_Aires")
        self.assertIn("7:00 PM", et_label)

    def test_unknown_timezone_falls_back_to_art(self):
        from organizadortg import convert_et_to_va_tz
        et_label, local_label = convert_et_to_va_tz("8:00 AM", "Invalid/Timezone")
        # Fallback debe devolver al menos algo parseable y no crashear
        self.assertIn("ET", et_label)
        self.assertIn("Buenos Aires", local_label)

    def test_madrid_timezone(self):
        from organizadortg import convert_et_to_va_tz
        et_label, local_label = convert_et_to_va_tz("8:00 AM", "Europe/Madrid")
        self.assertIn("Madrid", local_label)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar test y verificar que falla**

Run: `py -m unittest tests/test_timezone_conversion.py -v`
Expected: FAIL — `convert_et_to_va_tz` no existe.

- [ ] **Step 3: Implementar la función en `organizadortg.py`**

En `organizadortg.py`, después de la función `get_slots_for_set`, agregar:

```python
# --- 1.6. TIMEZONE CONVERSION ---
TIMEZONE_LABELS = {
    "America/New_York":              ("ET",  "Nueva York"),
    "America/Argentina/Buenos_Aires":("ART", "Buenos Aires"),
    "America/Chicago":               ("CT",  "Chicago"),
    "America/Los_Angeles":           ("PT",  "Los Ángeles"),
    "Europe/Madrid":                 ("CET", "Madrid"),
    "Europe/London":                 ("GMT", "Londres"),
}


def convert_et_to_va_tz(time_str: str, va_tz_str: str) -> tuple:
    """
    Convierte una hora ET (formato '8:00 AM' o '7:00 PM') al timezone de la VA.
    Devuelve dos strings listos para el mensaje:
        ("8:00 AM ET (Nueva York)", "9:00 AM ART (Buenos Aires)")

    Si va_tz_str es inválido, cae a Buenos Aires.
    """
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo  # type: ignore

    et_tz = ZoneInfo("America/New_York")
    try:
        va_tz = ZoneInfo(va_tz_str)
    except Exception:
        va_tz_str = "America/Argentina/Buenos_Aires"
        va_tz = ZoneInfo(va_tz_str)

    # Parsea "8:00 AM" combinándolo con la fecha de hoy en ET
    today_et = datetime.now(et_tz).date()
    naive = datetime.strptime(time_str.strip(), "%I:%M %p")
    et_dt = datetime.combine(today_et, naive.time(), tzinfo=et_tz)
    local_dt = et_dt.astimezone(va_tz)

    et_abbr, et_city = TIMEZONE_LABELS["America/New_York"]
    local_abbr, local_city = TIMEZONE_LABELS.get(
        va_tz_str, (va_tz_str.split("/")[-1], va_tz_str.split("/")[-1])
    )

    et_label = f"{et_dt.strftime('%I:%M %p').lstrip('0')} {et_abbr} ({et_city})"
    local_label = f"{local_dt.strftime('%I:%M %p').lstrip('0')} {local_abbr} ({local_city})"
    return et_label, local_label
```

- [ ] **Step 4: Ejecutar test y verificar que pasa**

Run: `py -m unittest tests/test_timezone_conversion.py -v`
Expected: 5 tests OK.

- [ ] **Step 5: Commit**

```bash
git add organizadortg.py tests/test_timezone_conversion.py
git commit -m "feat(bot): add convert_et_to_va_tz with IANA timezone support"
```

---

## Task 7: Integrar timezone + slots configurables en `execute_telegram_plan`

**Files:**
- Modify: `organizadortg.py:53-69` (`get_accounts_with_va_info` — agregar timezone)
- Modify: `organizadortg.py:218-322` (`execute_telegram_plan` — usar resolver + conversor)

- [ ] **Step 1: Modificar `get_accounts_with_va_info` para incluir timezone**

En `organizadortg.py:53-69`, actualizar la función completa:

```python
def get_accounts_with_va_info():
    accounts = db.get_all_accounts()
    vas = db.get_vas()
    result = []
    for acc in accounts:
        va_name = acc.get('assigned_va', 'Sin Asignar')
        tg_group_id = DEFAULT_CHAT_ID
        va_timezone = "America/Argentina/Buenos_Aires"
        if va_name != 'Sin Asignar':
            cur = db.conn.cursor()
            cur.execute("SELECT tg_group_id, timezone FROM virtual_assistants WHERE name = ?", (va_name,))
            row = cur.fetchone()
            if row:
                if row['tg_group_id']: tg_group_id = row['tg_group_id']
                if 'timezone' in row.keys() and row['timezone']:
                    va_timezone = row['timezone']
        result.append({
            'username': acc['username'], 'account_type': acc['account_type'],
            'assigned_va': va_name, 'tg_group_id': tg_group_id,
            'va_timezone': va_timezone,
        })
    return result
```

- [ ] **Step 2: Actualizar el loop dentro de `execute_telegram_plan`**

En `organizadortg.py`, dentro de `execute_telegram_plan`, reemplazar el bloque desde la línea ~261 (`for dia in sorted_days:`) hasta el `slot_offset += len(videos)` con esta versión actualizada:

```python
    for dia in sorted_days:
        dia_str = fecha_envio.strftime('%Y-%m-%d')
        day_of_week = fecha_envio.weekday()

        for username, videos in day_account_videos[dia].items():
            if selected_accounts and username not in selected_accounts: continue

            acc_info = next((a for a in accounts if a['username'] == username), None)
            if not acc_info:
                print(f"⚠️ Saltando @{username}: No está en la DB.")
                continue

            chat_id    = acc_info['tg_group_id']
            tag        = _account_tag(acc_info)
            va_name    = acc_info.get('assigned_va', 'Sin Asignar')
            category   = (acc_info.get('account_type') or 'general').strip().lower()
            va_tz      = acc_info.get('va_timezone', 'America/Argentina/Buenos_Aires')

            # Resolver slots por set (VA + categoría) para este día de la semana
            tiempos = get_slots_for_set(va_name, category, day_of_week, db)

            t_id = get_or_create_topic(chat_id, username, tag, topics_state)
            if not t_id:
                print(f"❌ Topic no encontrado para @{username} — saltando.")
                continue

            for i, vid in enumerate(videos):
                if controller and controller.stopped: return f"🛑 Abortado. Enviados: {global_sent}"
                if controller: controller.paused.wait()

                hora_et = tiempos[i % len(tiempos)]
                et_label, local_label = convert_et_to_va_tz(hora_et, va_tz)
                meta = (
                    f"{tag}\n"
                    f"Día: {dia_str}\n"
                    f"⏰ {et_label}\n"
                    f"   → {local_label}\n"
                    f"Formato: Reel"
                )

                print(f"📤 Enviando a @{username} [{tag}] (Día {dia_str} - {hora_et} ET)...")
                msg_res = call_tg("sendMessage", {'chat_id': chat_id, 'text': meta, 'message_thread_id': t_id}, silent=True)
                if not msg_res.get("ok"):
                    desc = str(msg_res.get("description", ""))
                    if "thread not found" in desc:
                        print(f"⚠️ Topic expirado para @{username}, recreando...")
                        t_id = get_or_create_topic(chat_id, username, tag, topics_state, force_recreate=True)
                        save_json(os.path.join(base_dir, STATE_FILE), topics_state)
                        if not t_id:
                            print(f"❌ No se pudo recrear topic para @{username} — saltando cuenta.")
                            break
                        retry_res = call_tg("sendMessage", {'chat_id': chat_id, 'text': meta, 'message_thread_id': t_id})
                        if not retry_res.get("ok"):
                            print(f"❌ Falló el reintento de metadata para @{username} [{hora_et}] — saltando video.")
                            continue
                    else:
                        print(f"⚠️ Error en Telegram API (sendMessage) para @{username}: {msg_res}")

                cap = shuffle_hashtags(random.choice(captions_pool))
                try:
                    ok, t_id = _send_video_to_topic(chat_id, t_id, cap, vid['path'], topics_state, username, tag)
                    if ok:
                        global_sent += 1
                    if t_id:
                        save_json(os.path.join(base_dir, STATE_FILE), topics_state)
                    time.sleep(2)
                except Exception as e: print(f"❌ Error físico: {e}")

        fecha_envio += timedelta(days=1)
```

Notas sobre los cambios:
- Eliminada la variable `slot_offset` — ahora cada set rota sus propios slots con `i % len(tiempos)`.
- `tiempos` se calcula por set (dentro del loop de username) en vez de una vez por día.
- `meta` muestra dos líneas (ET + local).
- El log de consola incluye `{hora_et} ET` para claridad.

- [ ] **Step 3: Eliminar la línea hardcodeada que ya no se usa**

Verificar que en `execute_telegram_plan` ya no exista el bloque `SCHEDULE = {...}` (eliminado en Task 5) ni `tiempos = SCHEDULE[fecha_envio.weekday()]` (reemplazado arriba).

- [ ] **Step 4: Smoke test manual del flujo (sin enviar a Telegram real)**

Crear un script temporal `tests/smoke_execute_plan.py` para verificar que la función arranca sin errores:

```python
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Verificación de que los símbolos nuevos existen e importan correctamente
from organizadortg import (
    DEFAULT_SCHEDULE,
    get_slots_for_set,
    convert_et_to_va_tz,
    TIMEZONE_LABELS,
    execute_telegram_plan,
    get_accounts_with_va_info,
)

print("✅ Todos los símbolos importan correctamente.")
print(f"   DEFAULT_SCHEDULE tiene {len(DEFAULT_SCHEDULE)} días.")
print(f"   TIMEZONE_LABELS tiene {len(TIMEZONE_LABELS)} entradas.")

# Test rápido de conversión
et, art = convert_et_to_va_tz("8:00 AM", "America/Argentina/Buenos_Aires")
print(f"   8:00 AM ET → {art}")
```

Run: `py tests/smoke_execute_plan.py`
Expected output: imprime los 3 mensajes sin errores.

- [ ] **Step 5: Re-correr toda la suite de tests**

Run: `py -m unittest discover tests -v`
Expected: 16+ tests OK (todos los de Tasks 1-6 siguen pasando).

- [ ] **Step 6: Commit**

```bash
git add organizadortg.py tests/smoke_execute_plan.py
git commit -m "feat(bot): integrate per-set schedule + dual-timezone message format"
```

---

## Task 8: UI — Dropdown de timezone en panel admin de VAs

**Files:**
- Modify: `gui_premium_v7.py:1167-1192` (`_admin_load_vas` — agregar dropdown)
- Modify: `gui_premium_v7.py:1269-1274` (`_admin_edit_va_tg` — sin cambio) + nuevo handler

- [ ] **Step 1: Agregar constante `TIMEZONE_OPTIONS` cerca de los otros constants**

En `gui_premium_v7.py`, buscar las constantes globales cerca del inicio (después de imports y constantes de colores). Agregar:

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

Para encontrar el lugar exacto: ubicar el primer bloque de constantes a nivel de módulo (línea ~30-50) y agregar al final.

- [ ] **Step 2: Modificar `_admin_load_vas` para incluir el dropdown**

Reemplazar el método completo `_admin_load_vas` (líneas 1167-1192) por:

```python
    def _admin_load_vas(self):
        for w in self._va_scroll.winfo_children():
            w.destroy()
        cur = self.db.conn.cursor()
        cur.execute("SELECT name, tg_group_id, timezone FROM virtual_assistants ORDER BY name")
        for row in cur.fetchall():
            name = row["name"]
            tg   = row["tg_group_id"] or ""
            tz   = row["timezone"] or "America/Argentina/Buenos_Aires"
            r = ctk.CTkFrame(self._va_scroll, fg_color="transparent")
            r.pack(fill="x", pady=2, padx=4)
            r.grid_columnconfigure(0, weight=1)
            dot_color = NEON_CYAN if tg else TEXT_MUTED
            ctk.CTkLabel(r, text=name, text_color=TEXT_BODY,
                         font=ctk.CTkFont(size=12), anchor="w").grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(r, text="⬤", text_color=dot_color,
                         font=ctk.CTkFont(size=10)).grid(row=0, column=1, padx=(4, 2))

            # Dropdown de timezone
            tz_var = tk.StringVar(value=tz)
            tz_menu = ctk.CTkOptionMenu(
                r, values=TIMEZONE_OPTIONS, variable=tz_var, width=180,
                fg_color=BG_CARD2, button_color=BG_CARD2, text_color=TEXT_BODY,
                command=lambda new_tz, n=name: self._admin_save_va_tz(n, new_tz),
            )
            tz_menu.grid(row=0, column=2, padx=(4, 4))

            ctk.CTkButton(r, text="TG", width=36, height=26, corner_radius=4,
                          fg_color=BG_CARD2, text_color=TEXT_MUTED,
                          hover_color=BORDER,
                          command=lambda n=name, t=tg: self._admin_edit_va_tg(n, t)
                          ).grid(row=0, column=3, padx=(2, 2))
            ctk.CTkButton(r, text="×", width=28, height=26, corner_radius=4,
                          fg_color=DANGER, text_color=TEXT_H1,
                          hover_color=self._darken(DANGER),
                          command=lambda n=name: self._admin_delete_va(n)
                          ).grid(row=0, column=4, padx=(2, 0))
```

- [ ] **Step 3: Agregar el handler `_admin_save_va_tz`**

Después de `_admin_edit_va_tg` (línea ~1274), agregar:

```python
    def _admin_save_va_tz(self, va_name: str, timezone: str):
        """Guarda el timezone seleccionado en el dropdown de una VA."""
        self.db.set_va_timezone(va_name, timezone)
```

- [ ] **Step 4: Smoke test manual de la GUI**

Run: `py gui_premium_v7.py`

Pasos manuales:
1. Ir a la pestaña Admin / VAs.
2. Verificar que cada VA muestra un dropdown con el timezone actual.
3. Cambiar el timezone de una VA a `America/New_York`, cerrar la GUI.
4. Reabrir la GUI y verificar que el cambio persistió.
5. También verificar con: `py -c "from database import DatabaseManager; db = DatabaseManager(); print(db.get_va_timezone('<nombre_va>'))"`.

Expected: el timezone cambia y persiste.

- [ ] **Step 5: Commit**

```bash
git add gui_premium_v7.py
git commit -m "feat(ui): add timezone dropdown to VA admin panel"
```

---

## Task 9: UI — Panel colapsable "Configurar Horarios" en pestaña Telegram

**Files:**
- Modify: `gui_premium_v7.py:1968+` (`_build_tg_frame` — insertar nueva subsección)
- Modify: `gui_premium_v7.py` (agregar 4 métodos nuevos)

- [ ] **Step 1: Agregar constantes de días y categorías por defecto**

Cerca de `TIMEZONE_OPTIONS` (agregado en Task 8), agregar:

```python
DAY_NAMES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
DEFAULT_CATEGORIES = ["promo", "suicide", "general"]
```

- [ ] **Step 2: Reorganizar el grid de `ctrl_card` para insertar el panel**

El `ctrl_card` actual tiene 5 filas (0=header con botón Cargar, 1=filter_row, 2=listbox, 3=bot_ctrl, 4=btn_row). Hay que insertar 2 filas nuevas (toggle button + panel) entre `filter_row` y el listbox, corriendo todo lo posterior hacia abajo.

**Layout objetivo:**
- row=0: hdr_row (sin cambio)
- row=1: filter_row (sin cambio)
- row=2: sched_header (NUEVO — botón toggle)
- row=3: sched_panel (NUEVO — oculto por default, se muestra al togglear)
- row=4: list_tg (movido desde row=2)
- row=5: bot_ctrl (movido desde row=3)
- row=6: btn_row (movido desde row=4)

**Cambios concretos en `_build_tg_frame`:**

(a) Cambiar `ctrl_card.grid_rowconfigure(2, weight=1)` (línea ~1985) por:
```python
        ctrl_card.grid_rowconfigure(4, weight=1)
```

(b) Después del bloque que crea `filter_row` y termina con el botón "✗ Ninguno" (línea ~2014), antes del comentario `# Fila 2: listbox con selección múltiple` (línea ~2016), insertar:

```python
        # Fila 2: Botón toggle del panel de horarios
        self._schedule_panel_expanded = False
        sched_header = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        sched_header.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 0))
        sched_header.grid_columnconfigure(0, weight=1)
        self.btn_toggle_sched = ctk.CTkButton(
            sched_header, text="▶ Configurar Horarios", anchor="w",
            fg_color=BG_CARD2, text_color=TEXT_BODY, hover_color=BORDER,
            command=self._toggle_schedule_panel,
        )
        self.btn_toggle_sched.grid(row=0, column=0, sticky="ew")

        # Fila 3: Panel scrollable (oculto inicialmente — se .grid() en toggle)
        self.sched_panel = ctk.CTkScrollableFrame(ctrl_card, fg_color=BG_INPUT, height=160)
```

(c) Cambiar la línea del listbox (línea ~2020):
```python
        self.list_tg.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
```
por:
```python
        self.list_tg.grid(row=4, column=0, sticky="nsew", padx=20, pady=(0, 10))
```

(d) Cambiar `bot_ctrl.grid(row=3, ...)` (línea ~2024) por `row=5`:
```python
        bot_ctrl.grid(row=5, column=0, sticky="ew", padx=20, pady=(10, 20))
```

(e) Cambiar `btn_row.grid(row=4, ...)` (línea ~2032) por `row=6`:
```python
        btn_row.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 20))
```

**Verificar visualmente con `py gui_premium_v7.py` que el layout sigue correcto antes de continuar (el listbox y los botones de start/pause/stop deben verse en sus posiciones habituales).**

- [ ] **Step 3: Implementar `_toggle_schedule_panel`**

Agregar como método nuevo (después de `_build_tg_frame`):

```python
    def _toggle_schedule_panel(self):
        """Expande o colapsa el panel de configuración de horarios."""
        self._schedule_panel_expanded = not self._schedule_panel_expanded
        if self._schedule_panel_expanded:
            self.btn_toggle_sched.configure(text="▼ Configurar Horarios")
            self.sched_panel.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 4))
            self._refresh_schedule_panel()
        else:
            self.btn_toggle_sched.configure(text="▶ Configurar Horarios")
            self.sched_panel.grid_forget()
```

- [ ] **Step 4: Implementar `_refresh_schedule_panel` (genera la grilla)**

Agregar como método nuevo:

```python
    def _refresh_schedule_panel(self):
        """Reconstruye la grilla de sets × días con los slots actuales (o 'default')."""
        import json
        for w in self.sched_panel.winfo_children():
            w.destroy()

        vas = self.db.get_vas()
        cats = self.db.get_categories() or DEFAULT_CATEGORIES

        # Header
        header = ctk.CTkFrame(self.sched_panel, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(header, text="Set (VA / Categoría)", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11, weight="bold"), width=180,
                     anchor="w").pack(side="left", padx=(4, 4))
        for d in DAY_NAMES:
            ctk.CTkLabel(header, text=d, text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=11, weight="bold"), width=70).pack(side="left")
        ctk.CTkLabel(header, text="", width=120).pack(side="left")  # botones

        # Filas
        for va in vas:
            for cat in cats:
                self._render_set_row(va, cat)

    def _render_set_row(self, va_name: str, category: str):
        import json
        r = ctk.CTkFrame(self.sched_panel, fg_color=BG_CARD2, corner_radius=4)
        r.pack(fill="x", pady=2, padx=2)
        ctk.CTkLabel(r, text=f"{va_name} / {category}", text_color=TEXT_BODY,
                     font=ctk.CTkFont(size=11), width=180, anchor="w").pack(side="left", padx=(4, 4))

        for dow in range(7):
            row = self.db.get_schedule_config(va_name, category, dow)
            if row:
                slots = json.loads(row["time_slots"])
                txt = ",".join(s.replace(":00 ", "").replace(" AM", "a").replace(" PM", "p") for s in slots)
                color = TEXT_BODY
            else:
                txt = "default"
                color = TEXT_MUTED
            ctk.CTkLabel(r, text=txt, text_color=color,
                         font=ctk.CTkFont(size=10), width=70).pack(side="left")

        ctk.CTkButton(r, text="Editar", width=56, height=22, fg_color=NEON_PURPLE,
                      hover_color=self._darken(NEON_PURPLE), text_color=TEXT_H1,
                      command=lambda v=va_name, c=category: self._edit_set_schedule(v, c)
                      ).pack(side="left", padx=(2, 2))
        ctk.CTkButton(r, text="Default", width=56, height=22, fg_color=BG_INPUT,
                      hover_color=BORDER, text_color=TEXT_MUTED,
                      command=lambda v=va_name, c=category: self._reset_set_schedule(v, c)
                      ).pack(side="left", padx=(0, 4))
```

- [ ] **Step 5: Implementar `_edit_set_schedule` (popup)**

Agregar como método nuevo:

```python
    def _edit_set_schedule(self, va_name: str, category: str):
        """Abre un popup para editar los 7 días del set."""
        import json
        from organizadortg import DEFAULT_SCHEDULE

        win = ctk.CTkToplevel(self)
        win.title(f"Horarios — {va_name} / {category}")
        win.geometry("520x420")
        win.grab_set()

        ctk.CTkLabel(win, text=f"⏰ {va_name} / {category}",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT_H1
                     ).pack(pady=(12, 4))
        ctk.CTkLabel(win, text="Horas separadas por coma. Formato: 8:00 AM, 1:00 PM, 7:00 PM",
                     text_color=TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(pady=(0, 8))

        entries = {}
        for dow in range(7):
            row = ctk.CTkFrame(win, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=2)
            ctk.CTkLabel(row, text=DAY_NAMES[dow], width=50, anchor="w",
                         text_color=TEXT_BODY).pack(side="left")
            cfg = self.db.get_schedule_config(va_name, category, dow)
            if cfg:
                current = ", ".join(json.loads(cfg["time_slots"]))
            else:
                current = ", ".join(DEFAULT_SCHEDULE[dow])
            e = ctk.CTkEntry(row, fg_color=BG_INPUT, border_color=BORDER, width=400)
            e.insert(0, current)
            e.pack(side="left", padx=8)
            entries[dow] = e

        def save_all():
            for dow, entry in entries.items():
                raw = entry.get().strip()
                if not raw:
                    self.db.delete_schedule_config(va_name, category, dow)
                    continue
                slots = [s.strip() for s in raw.split(",") if s.strip()]
                self.db.set_schedule_config(va_name, category, dow, slots)
            win.destroy()
            self._refresh_schedule_panel()

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(pady=14)
        ctk.CTkButton(btn_row, text="💾 Guardar", fg_color=SUCCESS, text_color=BG_APP,
                      hover_color=self._darken(SUCCESS), command=save_all).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="Cancelar", fg_color=BG_CARD2, text_color=TEXT_BODY,
                      hover_color=BORDER, command=win.destroy).pack(side="left", padx=6)
```

- [ ] **Step 6: Implementar `_reset_set_schedule`**

Agregar como método nuevo:

```python
    def _reset_set_schedule(self, va_name: str, category: str):
        """Borra la config de los 7 días del set — vuelve al DEFAULT_SCHEDULE."""
        if not messagebox.askyesno(
            "Restaurar default",
            f"¿Restaurar horarios estratégicos ET para {va_name} / {category}?",
            parent=self,
        ):
            return
        for dow in range(7):
            self.db.delete_schedule_config(va_name, category, dow)
        self._refresh_schedule_panel()
```

- [ ] **Step 7: Smoke test manual del panel**

Run: `py gui_premium_v7.py`

Pasos manuales:
1. Ir a la pestaña Telegram.
2. Click en "▶ Configurar Horarios" — debe expandirse y mostrar la grilla.
3. Verificar que todas las celdas muestran "default" inicialmente.
4. Click en "Editar" en una fila — debe abrir el popup con los 7 días pre-rellenos con DEFAULT_SCHEDULE.
5. Cambiar el campo Lun a `10:00 AM, 3:00 PM` y guardar.
6. Verificar que la grilla muestra `10a,3p` en la columna Lun de ese set y "default" en el resto.
7. Click en "Default" — confirmar — verificar que vuelve a "default" en todas las celdas.
8. Cerrar y reabrir la GUI para verificar persistencia.

Expected: todo funciona, datos persisten en `organizador.db`.

- [ ] **Step 8: Commit**

```bash
git add gui_premium_v7.py
git commit -m "feat(ui): add collapsible schedule config panel with per-set editor"
```

---

## Task 10: Verificación end-to-end + cleanup

**Files:**
- Modify: `tests/smoke_execute_plan.py` (extender) o crear `tests/test_message_format.py`

- [ ] **Step 1: Crear test de formato de mensaje (sin enviar a Telegram)**

Crear `tests/test_message_format.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MessageFormatTest(unittest.TestCase):
    def test_meta_message_contains_two_timezones(self):
        from organizadortg import convert_et_to_va_tz
        et_label, local_label = convert_et_to_va_tz("8:00 AM", "America/Argentina/Buenos_Aires")
        tag = "PROMO"
        dia_str = "2026-05-19"
        meta = (
            f"{tag}\n"
            f"Día: {dia_str}\n"
            f"⏰ {et_label}\n"
            f"   → {local_label}\n"
            f"Formato: Reel"
        )
        self.assertIn("PROMO", meta)
        self.assertIn("ET", meta)
        self.assertIn("Nueva York", meta)
        self.assertIn("ART", meta)
        self.assertIn("Buenos Aires", meta)
        self.assertIn("→", meta)
        self.assertEqual(meta.count("\n"), 4)  # 5 líneas → 4 saltos


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr la suite completa**

Run: `py -m unittest discover tests -v`
Expected: todos los tests OK (17+).

- [ ] **Step 3: Smoke test de la GUI completa**

Run: `py gui_premium_v7.py`

Checklist:
- [ ] Pestaña Admin: dropdown TZ funciona y persiste.
- [ ] Pestaña Telegram: panel "Configurar Horarios" expande/colapsa.
- [ ] Edición de un set guarda correctamente.
- [ ] Botón "Default" restaura un set.
- [ ] Cuentas se cargan normalmente (no se rompió `load_organized_accounts`).

- [ ] **Step 4: Verificación criterios de aceptación del spec**

Validar uno por uno los 6 criterios del spec (`docs/superpowers/specs/2026-05-19-metodo-ig-schedule-timezone-design.md` sección "Criterios de aceptación"):

1. Un set sin config muestra "default" y usa `DEFAULT_SCHEDULE` ✓
2. Un set con config usa sus propios slots ✓
3. El mensaje Telegram muestra dos líneas de timezone ✓
4. VA nueva default a ART ✓
5. Botón `[Default]` restaura sin errores ✓
6. DBs existentes migran sin errores ✓ (la migración usa `ALTER TABLE ... DEFAULT` que es no destructiva)

- [ ] **Step 5: Commit final**

```bash
git add tests/test_message_format.py
git commit -m "test: verify message format includes dual timezone display"
```

---

## Resumen de commits esperados

1. `feat(db): add timezone column to virtual_assistants with ART default`
2. `feat(db): add schedule_config table with (va_name, category, day_of_week) PK`
3. `feat(db): add get/set/delete_schedule_config methods`
4. `feat(db): add get/set_va_timezone methods`
5. `feat(bot): extract DEFAULT_SCHEDULE + add get_slots_for_set fallback resolver`
6. `feat(bot): add convert_et_to_va_tz with IANA timezone support`
7. `feat(bot): integrate per-set schedule + dual-timezone message format`
8. `feat(ui): add timezone dropdown to VA admin panel`
9. `feat(ui): add collapsible schedule config panel with per-set editor`
10. `test: verify message format includes dual timezone display`