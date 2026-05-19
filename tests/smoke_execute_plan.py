import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
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
