import os
import shutil
import sys
import random
from collections import defaultdict
from database import DatabaseManager

# --- CONFIGURACIÓN DE RUTAS ---
base_dir = os.path.dirname(os.path.abspath(__file__))
source_root = os.path.join(base_dir, "videos_finales")
output_root = os.path.join(base_dir, "CALENDARIO_POSTEO")

# Parámetros de distribución diaria
DAILY_GOAL = 46
FILL_UP_ENABLED = True


def get_distribution_config():
    """Obtiene la configuración de distribución desde la base de datos."""
    try:
        db = DatabaseManager()
        video_types = db.get_video_types()
        
        if not video_types:
            db.close()
            return {'SUICIDE': 22, 'PROMO': 24}
        
        config = {}
        total_types = len(video_types)
        
        if total_types > 0:
            base_count = DAILY_GOAL // total_types
            remainder = DAILY_GOAL % total_types
            
            for i, vt in enumerate(video_types):
                category = vt['type_name'].upper()
                config[category] = base_count + (1 if i < remainder else 0)
        
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
        
        categories = {}
        for vt in video_types:
            if vt.get('is_active', 1):
                categories[vt['type_name'].upper()] = vt['type_name'].lower()
        
        return categories if categories else {'SUICIDE': 'suicide', 'PROMO': 'promo'}
    except Exception as e:
        print(f"⚠️ Error consultando DB, usando categorías por defecto: {e}")
        return {'SUICIDE': 'suicide', 'PROMO': 'promo'}


def ensure_structure():
    """Verifica que existan las carpetas necesarias."""
    if not os.path.exists(source_root):
        print(f"❌ ERROR: No se encuentra la carpeta raíz de videos: {source_root}")
        sys.exit()
    if not os.path.exists(output_root):
        os.makedirs(output_root)


def parse_combination_from_filename(filename: str) -> tuple:
    """
    Extrae la combinación P1+P2 del nombre de archivo.
    Formato esperado: CATEGORIA__P1ID__P2ID.mp4
    """
    try:
        name = os.path.splitext(filename)[0]
        parts = name.split("__")
        if len(parts) >= 3:
            return (parts[1], parts[2])
    except Exception:
        pass
    return (None, None)


def get_inventory():
    """Escanea las subcarpetas de origen y agrupa por P1ID."""
    categories = get_categories_from_db()
    inventory = {cat: defaultdict(list) for cat in categories.keys()}
    
    for cat_key, cat_folder in categories.items():
        cat_path = os.path.join(source_root, cat_folder)
        if not os.path.exists(cat_path):
            continue
        
        files = [
            f for f in os.listdir(cat_path)
            if f.lower().endswith(('.mp4', '.mov'))
        ]
        
        for f in files:
            try:
                parts = f.split("__")
                p1_id = parts[1]
                inventory[cat_key][p1_id].append(f)
            except IndexError:
                print(f"⚠️ Archivo con formato inválido: {f}")
                inventory[cat_key]["unknown"].append(f)
    
    for cat in inventory:
        for p1 in inventory[cat]:
            random.shuffle(inventory[cat][p1])
            
    return inventory


def get_all_used_combinations() -> set:
    """
    Obtiene todas las combinaciones P1+P2 ya publicadas
    desde fingerprint_history (global, todas las cuentas).
    """
    used = set()
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("SELECT video_path FROM fingerprint_history")
        rows = cursor.fetchall()
        db.close()
        
        for row in rows:
            video_path = row['video_path']
            if not video_path:
                continue
            filename = os.path.basename(video_path)
            p1, p2 = parse_combination_from_filename(filename)
            if p1 and p2:
                used.add((p1, p2))
    except Exception as e:
        print(f"⚠️ Error consultando fingerprint_history: {e}")
    
    return used


def get_account_used_combinations(account_id: int) -> set:
    """Obtener todas las combinaciones P1+P2 que una cuenta ya ha publicado."""
    used = set()
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT video_path FROM fingerprint_history WHERE account_id = ?",
            (account_id,)
        )
        rows = cursor.fetchall()
        db.close()
        
        for row in rows:
            video_path = row['video_path']
            if not video_path:
                continue
            filename = os.path.basename(video_path)
            p1, p2 = parse_combination_from_filename(filename)
            if p1 and p2:
                used.add((p1, p2))
    except Exception:
        pass
    
    return used


def check_collision(account_id: int, p1_id: str, p2_id: str) -> bool:
    """Verificar si una combinación P1+P2 ya fue publicada por esta cuenta."""
    used = get_account_used_combinations(account_id)
    return (p1_id, p2_id) in used


# ==========================================
# FUNCIONES ANTI-CHOQUE GLOBAL
# ==========================================
global_used_p1 = {}
global_used_p2 = {}


def is_p1_used_today(day_number: int, p1_id: str) -> bool:
    """Verificar si un P1 ya fue usado hoy (globalmente)."""
    if day_number not in global_used_p1:
        return False
    return p1_id in global_used_p1[day_number]


def is_p2_used_today(day_number: int, p2_id: str) -> bool:
    """Verificar si un P2 ya fue usado hoy (globalmente)."""
    if day_number not in global_used_p2:
        return False
    return p2_id in global_used_p2[day_number]


def mark_p1_used_today(day_number: int, p1_id: str):
    """Marcar un P1 como usado para hoy (globalmente)."""
    if day_number not in global_used_p1:
        global_used_p1[day_number] = set()
    global_used_p1[day_number].add(p1_id)


def mark_p2_used_today(day_number: int, p2_id: str):
    """Marcar un P2 como usado para hoy (globalmente)."""
    if day_number not in global_used_p2:
        global_used_p2[day_number] = set()
    global_used_p2[day_number].add(p2_id)


def generate_fill_up_combinations(
    category: str,
    tanda_name: str,
    needed: int,
    used_combinations: set = None,
    day_number: int = 1
) -> list:
    """
    Generar nuevas combinaciones cruzando P1 y P2 de la carpeta de la tanda.
    Se usa cuando no hay suficientes videos nuevos.
    Implementa Anti-Choque Global y por cuenta.
    """
    if used_combinations is None:
        used_combinations = set()
    
    tanda = None
    try:
        db = DatabaseManager()
        tanda = db.get_tanda_by_name(tanda_name)
        db.close()
    except Exception:
        pass
    
    if not tanda:
        return []
    
    p1_folder = tanda.get('p1_folder')
    p2_folder = tanda.get('p2_folder')
    
    p1_dir = os.path.join(base_dir, "inputs", p1_folder)
    p2_dir = os.path.join(base_dir, "inputs", p2_folder)
    
    if not os.path.exists(p1_dir) or not os.path.exists(p2_dir):
        return []
    
    p1_files = [
        f for f in os.listdir(p1_dir)
        if f.lower().endswith(('.mp4', '.mov'))
    ]
    p2_files = [
        f for f in os.listdir(p2_dir)
        if f.lower().endswith(('.mp4', '.mov'))
    ]
    
    if not p1_files or not p2_files:
        return []
    
    random.shuffle(p1_files)
    random.shuffle(p2_files)
    
    fill_ups = []
    attempts = 0
    max_attempts = needed * 10
    idx = 0
    
    while len(fill_ups) < needed and attempts < max_attempts:
        p1 = p1_files[idx % len(p1_files)]
        p2 = p2_files[idx % len(p2_files)]
        
        p1_id = os.path.splitext(p1)[0].replace(" ", "_")
        p2_id = os.path.splitext(p2)[0].replace(" ", "_")
        
        combo = (p1_id, p2_id)
        
        # Anti-Choque: Verificar que no exista globalmente
        if combo not in used_combinations:
            # Verificar Anti-Choque Global del día
            if is_p1_used_today(day_number, p1_id) or is_p2_used_today(day_number, p2_id):
                idx += 1
                attempts += 1
                continue
            
            name_out = f"{category}__{p1_id}__{p2_id}.mp4"
            fill_ups.append(name_out)
            used_combinations.add(combo)
            
            # Registrar en diccionarios globales del día
            mark_p1_used_today(day_number, p1_id)
            mark_p2_used_today(day_number, p2_id)
        
        idx += 1
        attempts += 1
    
    return fill_ups


def generate_fill_up_from_history(
    category: str,
    tanda_name: str,
    needed: int,
    account_id: int,
    day_number: int
) -> list:
    """
    Fill-Up desde historial: busca videos viejos que generen combinaciones
    P1+P2 que nunca hayan chocado en esa cuenta Y que tampoco choquen globalmente.
    """
    fill_ups = []
    
    try:
        db = DatabaseManager()
        
        # Obtener combinaciones ya usadas por esta cuenta
        account_used = get_account_used_combinations(account_id)
        
        # Obtener tanda
        tanda = db.get_tanda_by_name(tanda_name)
        if not tanda:
            db.close()
            return []
        
        p1_folder = tanda.get('p1_folder')
        p2_folder = tanda.get('p2_folder')
        
        p1_dir = os.path.join(base_dir, "inputs", p1_folder)
        p2_dir = os.path.join(base_dir, "inputs", p2_folder)
        
        if not os.path.exists(p1_dir) or not os.path.exists(p2_dir):
            db.close()
            return []
        
        p1_files = [f for f in os.listdir(p1_dir) if f.lower().endswith(('.mp4', '.mov'))]
        p2_files = [f for f in os.listdir(p2_dir) if f.lower().endswith(('.mp4', '.mov'))]
        
        if not p1_files or not p2_files:
            db.close()
            return []
        
        random.shuffle(p1_files)
        random.shuffle(p2_files)
        
        attempts = 0
        max_attempts = needed * 20
        idx = 0
        
        while len(fill_ups) < needed and attempts < max_attempts:
            p1 = p1_files[idx % len(p1_files)]
            p2 = p2_files[idx % len(p2_files)]
            
            p1_id = os.path.splitext(p1)[0].replace(" ", "_")
            p2_id = os.path.splitext(p2)[0].replace(" ", "_")
            
            combo = (p1_id, p2_id)
            
            # Verificar que no haya sido usada por esta cuenta
            if combo in account_used:
                idx += 1
                attempts += 1
                continue
            
            # Verificar Anti-Choque Global del día
            if is_p1_used_today(day_number, p1_id) or is_p2_used_today(day_number, p2_id):
                idx += 1
                attempts += 1
                continue
            
            # Combinación válida: no usada por la cuenta Y no choque global
            name_out = f"{category}__{p1_id}__{p2_id}.mp4"
            fill_ups.append(name_out)
            
            # Registrar en globales
            mark_p1_used_today(day_number, p1_id)
            mark_p2_used_today(day_number, p2_id)
            
            idx += 1
            attempts += 1
        
        db.close()
        
    except Exception as e:
        print(f"⚠️ Error en fill-up desde historial: {e}")
    
    return fill_ups


def pick_balanced_with_anti_collision(
    cat_bins, 
    count, 
    used_combinations: set,
    day_number: int
) -> list:
    """
    Selecciona videos rotando entre diferentes P1IDs para evitar repeticiones.
    Implementa Anti-Choque Global: verifica que P1 y P2 no estén usados hoy.
    """
    selected = []
    p1_keys = [k for k in cat_bins.keys() if cat_bins[k]]
    if not p1_keys:
        return selected
    
    random.shuffle(p1_keys)
    pointer = 0
    
    while len(selected) < count:
        available_keys = [k for k in p1_keys if cat_bins[k]]
        if not available_keys:
            break
        
        current_p1 = available_keys[pointer % len(available_keys)]
        if cat_bins[current_p1]:
            candidate = cat_bins[current_p1][0]
            p1_id, p2_id = parse_combination_from_filename(candidate)
            
            if p1_id and p2_id:
                # Verificar Anti-Choque Global del día
                if is_p1_used_today(day_number, p1_id) or is_p2_used_today(day_number, p2_id):
                    # Saltar este video y probar el siguiente
                    cat_bins[current_p1].pop(0)
                    if not cat_bins[current_p1]:
                        p1_keys.remove(current_p1)
                    pointer += 1
                    continue
                
                # Verificar que no esté en combinaciones ya usadas
                if (p1_id, p2_id) in used_combinations:
                    cat_bins[current_p1].pop(0)
                    if not cat_bins[current_p1]:
                        p1_keys.remove(current_p1)
                    pointer += 1
                    continue
                
                # Video válido: seleccionarlo y marcar P1/P2 como usados hoy
                selected.append(cat_bins[current_p1].pop(0))
                mark_p1_used_today(day_number, p1_id)
                mark_p2_used_today(day_number, p2_id)
        
        pointer += 1
    
    return selected


def pick_balanced(cat_bins, count, used_combinations: set = None):
    """
    Selecciona videos rotando entre diferentes P1IDs para evitar repeticiones.
    Omite combinaciones que ya existen en used_combinations.
    """
    if used_combinations is None:
        used_combinations = set()
    
    selected = []
    p1_keys = [k for k in cat_bins.keys() if cat_bins[k]]
    if not p1_keys:
        return selected
    
    random.shuffle(p1_keys)
    pointer = 0
    
    while len(selected) < count:
        available_keys = [k for k in p1_keys if cat_bins[k]]
        if not available_keys:
            break
        
        current_p1 = available_keys[pointer % len(available_keys)]
        if cat_bins[current_p1]:
            candidate = cat_bins[current_p1][0]
            p1_id, p2_id = parse_combination_from_filename(candidate)
            
            if p1_id and p2_id and (p1_id, p2_id) in used_combinations:
                cat_bins[current_p1].pop(0)
                if not cat_bins[current_p1]:
                    p1_keys.remove(current_p1)
                pointer += 1
                continue
            
            selected.append(cat_bins[current_p1].pop(0))
        
        pointer += 1
    
    return selected


def distribute(daily_goal: int = None, fill_up: bool = None):
    """
    Distribución por días con Fill-up y Anti-Choque.
    
    Args:
        daily_goal: Meta diaria de videos (default: DAILY_GOAL)
        fill_up: Habilitar generación dinámica de combinaciones (default: FILL_UP_ENABLED)
    """
    global DAILY_GOAL, FILL_UP_ENABLED, global_used_p1, global_used_p2
    
    # Inicializar diccionarios globales Anti-Choque
    global_used_p1 = {}
    global_used_p2 = {}
    
    if daily_goal is not None:
        DAILY_GOAL = daily_goal
    if fill_up is not None:
        FILL_UP_ENABLED = fill_up
    
    ensure_structure()
    bins = get_inventory()
    
    distribution_config = get_distribution_config()
    categories = get_categories_from_db()
    
    tanda_activa = None
    try:
        db = DatabaseManager()
        todas_tandas = db.get_tandas()  # get_all_tandas()
        tanda_activa = todas_tandas[0] if todas_tandas else None
        db.close()
    except Exception as e:
        print(f"⚠️ Error obteniendo tanda: {e}")
        tanda_activa = None
    
    used_combinations = get_all_used_combinations()
    
    config_str = ", ".join([f"{k}:{v}" for k, v in distribution_config.items()])
    print(f"📊 Configuración: Meta={DAILY_GOAL}, Fill-up={FILL_UP_ENABLED}")
    print(f"📊 Distribución: {config_str}")
    if tanda_activa:
        print(f"📊 Tanda activa: {tanda_activa['tanda_name']}")
    
    grupos_info = ", ".join([f"{k}:{len(bins[k])}" for k in bins.keys()])
    print(f"📊 Grupos P1: {grupos_info}")
    
    dia = 1
    while any(bins[cat].values() for cat in bins):
        folder_dia = os.path.join(output_root, f"Dia_{dia}")
        
        for cat_key, cat_folder in categories.items():
            sub_path = os.path.join(folder_dia, cat_folder)
            os.makedirs(sub_path, exist_ok=True)
        
        daily_selected = {}
        
        # Seleccionar videos con Anti-Choque Global
        for cat_key, count in distribution_config.items():
            if cat_key in bins:
                daily_selected[cat_key] = pick_balanced_with_anti_collision(
                    bins[cat_key],
                    count,
                    used_combinations,
                    dia  # Pasar número de día para control global
                )
        
        # Fill-Up: si no hay suficientes videos, generar dinámicamente
        if FILL_UP_ENABLED and tanda_activa:
            total_actual = sum(len(v) for v in daily_selected.values())
            if total_actual < DAILY_GOAL:
                gap = DAILY_GOAL - total_actual
                print(f"🔄 Fill-up: Generando {gap} videos dinámicos para el día {dia}...")
                
                main_cat = list(distribution_config.keys())[0]
                
                # Fill-up normal desde tanda
                fill_ups = generate_fill_up_combinations(
                    main_cat,
                    tanda_activa['tanda_name'],
                    gap,
                    used_combinations,
                    dia
                )
                
                if fill_ups:
                    daily_selected[main_cat] = daily_selected.get(main_cat, []) + fill_ups
                
                # Si aún falta, intentar Fill-up desde historial
                if sum(len(v) for v in daily_selected.values()) < DAILY_GOAL:
                    remaining_gap = DAILY_GOAL - sum(len(v) for v in daily_selected.values())
                    print(f"🔄 Fill-up desde historial: Buscando {remaining_gap} combinaciones alternativas...")
                    
                    # Obtener account_id para fill-up desde historial
                    try:
                        db = DatabaseManager()
                        accounts = db.get_all_accounts()
                        if accounts:
                            account_id = accounts[0]['id']
                            hist_fill = generate_fill_up_from_history(
                                main_cat,
                                tanda_activa['tanda_name'],
                                remaining_gap,
                                account_id,
                                dia
                            )
                            if hist_fill:
                                daily_selected[main_cat] = daily_selected.get(main_cat, []) + hist_fill
                        db.close()
                    except Exception as e:
                        print(f"⚠️ Error en fill-up desde historial: {e}")
        
        def move_files(files, category, target_path):
            for f in files:
                src = os.path.join(source_root, category.lower(), f)
                dst = os.path.join(target_path, f)
                if os.path.exists(src):
                    shutil.move(src, dst)
        
        for cat_key, cat_folder in categories.items():
            if cat_key in daily_selected:
                target_path = os.path.join(folder_dia, cat_folder)
                move_files(daily_selected[cat_key], cat_key, target_path)
        
        total_dia = sum(len(v) for v in daily_selected.values())
        
        # Mostrar qué P1/P2 se usaron hoy
        p1_hoy = global_used_p1.get(dia, set())
        p2_hoy = global_used_p2.get(dia, set())
        
        print(
            f"✅ Dia_{dia:02d}: {total_dia} videos organizados "
            f"(P1 usados: {len(p1_hoy)}, P2 usados: {len(p2_hoy)})"
        )
        dia += 1
        
        # Safety: máximo 31 días
        if dia > 31:
            print("⚠️ Límite de 31 días alcanzado. Deteniendo.")
            break


if __name__ == "__main__":
    print("🔍 --- INICIANDO ORGANIZACIÓN CON ANTI-CHOQUE GLOBAL ---")
    
    # Parámetros por defecto
    distribute(
        tanda_name=None,        # Usará la tanda activa
        target_category=None,   # Usará todas las categorías
        daily_goal=46,          # Meta diaria
        fillup=True             # Fill-up habilitado
    )
    
    print("\n--- ✅ ORGANIZACIÓN CON ANTI-CHOQUE GLOBAL COMPLETADA ---")