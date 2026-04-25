import os
import shutil
import sys
import random
from collections import defaultdict

# --- CONFIGURACIÓN DE RUTAS ---
base_dir = os.path.dirname(os.path.abspath(__file__))
# Origen: Carpetas creadas por el nuevo videos.py
source_root = os.path.join(base_dir, "videos_finales")
output_root = os.path.join(base_dir, "CALENDARIO_POSTEO")

# Parámetros de distribución diaria (Ajustables según volumen)
DAILY_GOAL = 46
PREF_SUICIDE = 22
PREF_PROMO = 24

print("🔍 --- INICIANDO ORGANIZACIÓN POR ENTROPÍA (MODO PERSISTENTE) ---")

def ensure_structure():
    if not os.path.exists(source_root):
        print(f"❌ ERROR: No se encuentra la carpeta raíz de videos: {source_root}")
        sys.exit()
    if not os.path.exists(output_root): os.makedirs(output_root)

# --- 1. INDEXACIÓN Y CLASIFICACIÓN ---
def get_inventory():
    """Escanea las subcarpetas de origen y agrupa por P1ID."""
    inventory = {
        "SUICIDE": defaultdict(list),
        "PROMO": defaultdict(list)
    }
    
    for cat in ["suicide", "promo"]:
        cat_path = os.path.join(source_root, cat)
        if not os.path.exists(cat_path): continue
        
        cat_key = cat.upper()
        files = [f for f in os.listdir(cat_path) if f.lower().endswith(('.mp4', '.mov'))]
        
        for f in files:
            # Parsing del estándar: CATEGORIA__P1ID__P2ID.mp4
            try:
                parts = f.split("__")
                p1_id = parts[1] # Extraemos el ID del fondo visual
                inventory[cat_key][p1_id].append(f)
            except IndexError:
                print(f"⚠️ Archivo con formato inválido: {f}")
                inventory[cat_key]["unknown"].append(f)

    # Barajar cada grupo para maximizar la aleatoriedad de P2
    for cat in inventory:
        for p1 in inventory[cat]:
            random.shuffle(inventory[cat][p1])
            
    return inventory

# --- 2. SELECTOR BALANCEADO (ROUND-ROBIN) ---
def pick_balanced(cat_bins, count):
    """Selecciona videos rotando entre diferentes P1IDs para evitar repeticiones."""
    selected = []
    p1_keys = [k for k in cat_bins.keys() if cat_bins[k]]
    if not p1_keys: return selected
    
    random.shuffle(p1_keys)
    pointer = 0
    
    while len(selected) < count:
        available_keys = [k for k in p1_keys if cat_bins[k]]
        if not available_keys: break
        
        current_p1 = available_keys[pointer % len(available_keys)]
        if cat_bins[current_p1]:
            selected.append(cat_bins[current_p1].pop(0))
        
        pointer += 1
    return selected

# --- 3. DISTRIBUCIÓN POR DÍAS ---
def distribute():
    ensure_structure()
    bins = get_inventory()
    
    print(f"📊 Grupos P1: {len(bins['SUICIDE'])} en Suicide, {len(bins['PROMO'])} en Promo")
    
    dia = 1
    # Seguir distribuyendo mientras haya videos en cualquiera de los bins
    while any(bins["SUICIDE"].values()) or any(bins["PROMO"].values()):
        folder_dia = os.path.join(output_root, f"Dia_{dia}")
        sub_s = os.path.join(folder_dia, "suicide")
        sub_p = os.path.join(folder_dia, "promo")
        
        os.makedirs(sub_s, exist_ok=True)
        os.makedirs(sub_p, exist_ok=True)

        # Selección balanceada diaria
        dia_suicide = pick_balanced(bins["SUICIDE"], PREF_SUICIDE)
        dia_promo = pick_balanced(bins["PROMO"], PREF_PROMO)
        
        # Relleno de emergencia si falta stock para llegar al DAILY_GOAL
        total_actual = len(dia_suicide) + len(dia_promo)
        if total_actual < DAILY_GOAL and (any(bins["SUICIDE"].values()) or any(bins["PROMO"].values())):
            gap = DAILY_GOAL - total_actual
            dia_suicide += pick_balanced(bins["SUICIDE"], gap // 2)
            dia_promo += pick_balanced(bins["PROMO"], gap - (gap // 2))

        def move_files(files, category, target_path):
            for f in files:
                src = os.path.join(source_root, category.lower(), f)
                dst = os.path.join(target_path, f) # MANTIENE NOMBRE ORIGINAL
                shutil.move(src, dst)

        move_files(dia_suicide, "SUICIDE", sub_s)
        move_files(dia_promo, "PROMO", sub_p)

        print(f"✅ Dia_{dia:02d}: {len(dia_suicide) + len(dia_promo)} videos organizados con nombre persistente.")
        dia += 1

if __name__ == "__main__":
    distribute()
    print("\n--- ✅ ORGANIZACIÓN DETERMINISTA COMPLETADA ---")