import os
import shutil
import sys
import random
from collections import defaultdict

# Importar módulo de base de datos
from database import DatabaseManager

# --- CONFIGURACIÓN DE RUTAS ---
base_dir = os.path.dirname(os.path.abspath(__file__))
# Origen: Carpetas creadas por el nuevo videos.py
source_root = os.path.join(base_dir, "videos_finales")
output_root = os.path.join(base_dir, "CALENDARIO_POSTEO")

# Parámetros de distribución diaria (Ajustables según volumen)
DAILY_GOAL = 46
FILL_UP_ENABLED = True  # Por defecto activado


def get_distribution_config():
    """Obtiene la configuración de distribución desde la base de datos."""
    try:
        db = DatabaseManager()
        
        # Obtener todos los tipos de video activos
        video_types = db.get_video_types()
        
        if not video_types:
            # Fallback si no hay tipos en DB
            db.close()
            return {
                'SUICIDE': 22,
                'PROMO': 24
            }
        
        # Calcular distribución automática basada en los tipos registrados
        config = {}
        total_types = len(video_types)
        
        if total_types > 0:
            # Distribución equitativa
            base分配 = DAILY_GOAL // total_types
            remainder = DAILY_GOAL % total_types
            
            for i, vt in enumerate(video_types):
                category = vt['type_name'].upper()
                # Asignar distribución base más distribución extra si hay remainder
                config[category] = base分配 + (1 if i < remainder else 0)
        
        db.close()
        return config if config else {'SUICIDE': 22, 'PROMO': 24}
        
    except Exception as e:
        print(f"⚠️ Error consultando DB, usando configuración por defecto: {e}")
        return {'SUICIDE': 22, 'PROMO': 24}


def get_categories_from_db():
    """Obtiene las categorías dinámicas desde la base de datos."""
    try:
        db = DatabaseManager()
        video_types = db.get_video_types()
        db.close()
        
        # Retornar diccionario con categorías y sus tipos
        categories = {}
        for vt in video_types:
            if vt.get('is_active', 1):
                categories[vt['type_name'].upper()] = vt['type_name'].lower()
        
        return categories if categories else {'SUICIDE': 'suicide', 'PROMO': 'promo'}
    except Exception as e:
        print(f"⚠️ Error consultando DB, usando categorías por defecto: {e}")
        return {'SUICIDE': 'suicide', 'PROMO': 'promo'}


print("🔍 --- INICIANDO ORGANIZACIÓN POR ENTROPÍA (MODO PERSISTENTE) ---")

def ensure_structure():
    if not os.path.exists(source_root):
        print(f"❌ ERROR: No se encuentra la carpeta raíz de videos: {source_root}")
        sys.exit()
    if not os.path.exists(output_root): os.makedirs(output_root)

# --- 1. INDEXACIÓN Y CLASIFICACIÓN ---
def get_inventory():
    """Escanea las subcarpetas de origen y agrupa por P1ID."""
    # Obtener categorías dinámicas desde la base de datos
    categories = get_categories_from_db()
    
    # Inicializar inventario con las categorías de la DB
    inventory = {cat: defaultdict(list) for cat in categories.keys()}
    
    for cat_key, cat_folder in categories.items():
        cat_path = os.path.join(source_root, cat_folder)
        if not os.path.exists(cat_path): continue
        
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


# --- 2. ANTI-CHOQUE: Verificar combinaciones existentes ---
def get_account_used_combinations(account_id: int) -> set:
    """Obtener todas las combinaciones P1+P2 que una cuenta ya ha publicado"""
    try:
        db = DatabaseManager()
        combinations = db.get_account_video_combinations(account_id)
        db.close()
        
        # Convertir a set de tuplas para búsqueda rápida
        return set((c.get('p1_source'), c.get('p2_source')) for c in combinations)
    except:
        return set()


def check_collision(account_id: int, p1_id: str, p2_id: str) -> bool:
    """Verificar si una combinación P1+P2 ya fue publicada por esta cuenta"""
    used = get_account_used_combinations(account_id)
    return (p1_id, p2_id) in used


# --- 3. FILL-UP: Generar nuevas combinaciones dinámicamente ---
def generate_fill_up_combinations(category: str, tanda_name: str, needed: int) -> list:
    """
    Generar nuevas combinaciones cruzando P1 y P2 de la carpeta de la tanda.
    Se usa cuando no hay suficientes videos nuevos.
    """
    # Buscar carpetas P1 y P2 de la tanda
    tanda = None
    try:
        db = DatabaseManager()
        tanda = db.get_tanda_by_name(tanda_name)
        db.close()
    except:
        pass
    
    if not tanda:
        return []
    
    p1_folder = tanda.get('p1_folder')
    p2_folder = tanda.get('p2_folder')
    
    p1_dir = os.path.join(base_dir, "inputs", p1_folder)
    p2_dir = os.path.join(base_dir, "inputs", p2_folder)
    
    if not os.path.exists(p1_dir) or not os.path.exists(p2_dir):
        return []
    
    # Listar todos los P1 y P2 disponibles
    p1_files = [f for f in os.listdir(p1_dir) if f.lower().endswith(('.mp4', '.mov'))]
    p2_files = [f for f in os.listdir(p2_dir) if f.lower().endswith(('.mp4', '.mov'))]
    
    if not p1_files or not p2_files:
        return []
    
    # Generar combinaciones fill-up
    fill_ups = []
    random.shuffle(p1_files)
    random.shuffle(p2_files)
    
    for i in range(needed):
        p1 = p1_files[i % len(p1_files)]
        p2 = p2_files[i % len(p2_files)]
        
        p1_id = os.path.splitext(p1)[0].replace(" ", "_")
        p2_id = os.path.splitext(p2)[0].replace(" ", "_")
        
        name_out = f"{category}__{p1_id}__{p2_id}.mp4"
        fill_ups.append(name_out)
    
    return fill_ups


# --- 4. SELECTOR BALANCEADO (ROUND-ROBIN) ---
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


# --- 5. DISTRIBUCIÓN POR DÍAS ---
def distribute(daily_goal: int = None, fill_up: bool = None):
    """
    Distribución por días con Fill-up y Anti-Choque.
    
    Args:
        daily_goal: Meta diaria de videos (default: DAILY_GOAL)
        fill_up: Habilitar generación dinámica de combinaciones (default: FILL_UP_ENABLED)
    """
    global DAILY_GOAL, FILL_UP_ENABLED
    
    # Aplicar parámetros
    if daily_goal is not None:
        DAILY_GOAL = daily_goal
    if fill_up is not None:
        FILL_UP_ENABLED = fill_up
    
    ensure_structure()
    bins = get_inventory()
    
    # Obtener configuración dinámica desde la DB
    distribution_config = get_distribution_config()
    categories = get_categories_from_db()
    
    # Obtener tanda activa si existe
    tanda_activa = None
    try:
        db = DatabaseManager()
        tanda = db.get_tandas(active_only=True)
        db.close()
        tanda_activa = tanda[0] if tanda else None
    except:
        pass
    
    # Mostrar configuración actual
    config_str = ", ".join([f"{k}:{v}" for k, v in distribution_config.items()])
    print(f"📊 Configuración: Meta={DAILY_GOAL}, Fill-up={FILL_UP_ENABLED}")
    print(f"📊 Distribución: {config_str}")
    
    # Contar grupos por categoría
    grupos_info = ", ".join([f"{k}:{len(bins[k])}" for k in bins.keys()])
    print(f"📊 Grupos P1: {grupos_info}")
    
    dia = 1
    # Seguir distribuyendo mientras haya videos en cualquiera de los bins
    while any(bins[cat].values() for cat in bins):
        folder_dia = os.path.join(output_root, f"Dia_{dia}")
        
        # Crear subcarpetas dinámicamente según las categorías de la DB
        for cat_key, cat_folder in categories.items():
            sub_path = os.path.join(folder_dia, cat_folder)
            os.makedirs(sub_path, exist_ok=True)

        # Selección balanceada diaria usando configuración dinámica
        daily_selected = {}
        for cat_key, count in distribution_config.items():
            if cat_key in bins:
                daily_selected[cat_key] = pick_balanced(bins[cat_key], count)
        
        # Fill-up: generar nuevas combinaciones si no hay suficientes videos
        if FILL_UP_ENABLED and tanda_activa:
            total_actual = sum(len(v) for v in daily_selected.values())
            if total_actual < DAILY_GOAL:
                gap = DAILY_GOAL - total_actual
                print(f"🔄 Fill-up: Generando {gap} videos dinámicos...")
                
                # Generar combinaciones fill-up
                fill_ups = generate_fill_up_combinations(
                    tanda_activa['tanda_name'],
                    tanda_activa['tanda_name'],
                    gap
                )
                
                # Añadir fill-ups a la categoría principal
                if fill_ups:
                    main_cat = list(distribution_config.keys())[0]
                    daily_selected[main_cat] = daily_selected.get(main_cat, []) + fill_ups

        def move_files(files, category, target_path):
            for f in files:
                src = os.path.join(source_root, category.lower(), f)
                dst = os.path.join(target_path, f) # MANTIENE NOMBRE ORIGINAL
                if os.path.exists(src):
                    shutil.move(src, dst)

        # Mover archivos a sus carpetas correspondientes
        for cat_key, cat_folder in categories.items():
            if cat_key in daily_selected:
                target_path = os.path.join(folder_dia, cat_folder)
                move_files(daily_selected[cat_key], cat_key, target_path)

        total_dia = sum(len(v) for v in daily_selected.values())
        print(f"✅ Dia_{dia:02d}: {total_dia} videos organizados con nombre persistente.")
        dia += 1

if __name__ == "__main__":
    distribute()
    print("\n--- ✅ ORGANIZACIÓN DETERMINISTA COMPLETADA ---")