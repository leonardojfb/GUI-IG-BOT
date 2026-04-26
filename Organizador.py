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
from database import DatabaseManager
import datetime
import math

import math

import math

def preview_distribution_tanda(tanda_name, category_dest, daily_quota, use_fillup, days_to_organize="MAX"):
    """
    Genera un reporte detallado de distribución, detallando VAs y Fill-up por cuenta.
    """
    db = DatabaseManager()
    # Filtrar cuentas por categoría (account_type en V6)
    all_accs = db.get_all_accounts()
    accounts = [a for a in all_accs if a['account_type'].upper() == category_dest.upper()]
    
    if not accounts:
        db.close()
        return f"❌ ERROR: No hay cuentas asignadas a la categoría: {category_dest}"

    # Ubicación de videos en la tanda
    tanda_path = os.path.join(source_root, tanda_name)
    if not os.path.exists(tanda_path):
        db.close()
        return f"❌ ERROR: No se encuentra la carpeta de la tanda: {tanda_name}"

    videos = [f for f in os.listdir(tanda_path) if f.lower().endswith(('.mp4', '.mov'))]
    total_videos = len(videos)
    
    # --- CÁLCULOS LOGÍSTICOS ---
    num_cuentas = len(accounts)
    vids_dia_grupo = num_cuentas * daily_quota
    dias_alcance_real = total_videos / vids_dia_grupo if vids_dia_grupo > 0 else 0

    # Lógica de Días "MAX": Redondeo hacia arriba para completar el último día
    if str(days_to_organize).upper() == "MAX":
        target_days = math.ceil(dias_alcance_real)
    else:
        try: target_days = int(days_to_organize)
        except: target_days = math.floor(dias_alcance_real)

    total_necesario = target_days * vids_dia_grupo
    vids_faltantes_total = max(0, total_necesario - total_videos)

    # --- CONSTRUCCIÓN DEL REPORTE ---
    resumen =  f"╔════════════════════════════════════════════════════════════════════╗\n"
    resumen += f"║   🎬 REPORTE ESTRATÉGICO DE DISTRIBUCIÓN: {tanda_name:<16} ║\n"
    resumen += f"╚════════════════════════════════════════════════════════════════════╝\n\n"
    
    resumen += f"📈 RESUMEN DE INVENTARIO:\n"
    resumen += f"  ├─ Categoría Destino:  {category_dest}\n"
    resumen += f"  ├─ Videos Disponibles: {total_videos}\n"
    resumen += f"  ├─ Consumo del Grupo:  {vids_dia_grupo} videos/día\n"
    resumen += f"  └─ Alcance Natural:    {dias_alcance_real:.2f} días\n\n"

    resumen += f"🗓️ PLANIFICACIÓN (Modo: {'MÁXIMO' if days_to_organize == 'MAX' else 'FIJO'}):\n"
    resumen += f"  ├─ Objetivo:           {target_days} días completos\n"
    resumen += f"  ├─ Necesidad Total:    {total_necesario} videos\n"
    if use_fillup:
        resumen += f"  ├─ ⚡ FILL-UP:         ACTIVO (Generará {vids_faltantes_total} videos extras)\n"
    resumen += f"  └─ Estado Final:       Todas las cuentas sincronizadas hasta el Día {target_days}\n\n"

    resumen += f"👥 DETALLE POR CUENTA Y ASISTENTE (VA):\n"
    resumen += f"{'CUENTA':<18} | {'VA ASIGNADO':<15} | {'REAL':<6} | {'FILL-UP'}\n"
    resumen += f"{'-'*68}\n"

    vids_stock_restante = total_videos
    for acc in accounts:
        user = f"@{acc['username']}"
        va = acc.get('assigned_va', '⚠️ SIN VA')
        
        # Reparto equitativo del stock real
        meta_acc = target_days * daily_quota
        vids_reales = min(meta_acc, vids_stock_restante // (num_cuentas - accounts.index(acc)))
        vids_stock_restante -= vids_reales
        
        # Cálculo de fill-up por cuenta
        necesita_fill = meta_acc - vids_reales
        fill_str = f"➕ {necesita_fill} vids" if necesita_fill > 0 else "✅ OK"
        
        resumen += f"{user[:18]:<18} | {va[:15]:<15} | {vids_reales:<6} | {fill_str}\n"

    resumen += f"\n{'='*68}\n"
    resumen += f"💡 EL CONTENIDO ALCANZA PARA QUE TODO EL EQUIPO PUBLIQUE POR {target_days} DÍAS.\n"
    
    db.close()
    return resumen
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
import random
import string

def change_video_metadata(file_path):
    """
    Cambia el hash del archivo y limpia metadatos básicos 
    añadiendo un pequeño comentario aleatorio al final del archivo.
    """
    try:
        # Generamos una cadena aleatoria pequeña
        random_str = "".join(random.choices(string.ascii_letters + string.digits, k=16))
        with open(file_path, "ab") as f:
            # Escribimos al final del archivo (no rompe el video, pero cambia el MD5/Hash)
            f.write(f"\n# ID_{random_str}".encode())
        return True
    except Exception as e:
        print(f"⚠️ Error limpiando metadatos en {file_path}: {e}")
        return False

# MODIFICADO: Solo rastreamos P1 globalmente
global_used_p1 = {} 

def is_p1_collision_global(day, p1):
    """Verifica si el clip de inicio P1 ya se usó hoy en OTRA cuenta."""
    return p1 in global_used_p1.get(day, set())

def mark_p1_used_global(day, p1):
    """Registra que este P1 ya no puede usarse por hoy en otras cuentas."""
    if day not in global_used_p1: global_used_p1[day] = set()
    global_used_p1[day].add(p1)

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
# ==========================================
# CONEXIÓN CON LA GUI V6 (VISTA PREVIA Y DISTRIBUCIÓN)
# ==========================================

import math
import datetime

def distribute_tanda(tanda_name, category_dest, daily_quota, use_fillup, days_to_organize="MAX"):
    global global_used_p1
    global_used_p1 = {} # Reset de colisiones diarias
    
    db = DatabaseManager()
    all_accs = db.get_all_accounts()
    accounts = [a for a in all_accs if a['account_type'].upper() == category_dest.upper()]
    
    if not accounts:
        db.close()
        return "❌ Error: No hay cuentas para esta categoría."

    tanda_path = os.path.join(source_root, tanda_name)
    videos_originales = [f for f in os.listdir(tanda_path) if f.lower().endswith(('.mp4', '.mov'))]
    random.shuffle(videos_originales)
    
    # Cálculo de días (Mismo que antes)
    num_cuentas = len(accounts)
    vids_dia_total = num_cuentas * daily_quota
    if str(days_to_organize).upper() == "MAX":
        target_days = math.ceil(len(videos_originales) / vids_dia_total) if vids_dia_total > 0 else 1
    else:
        try: target_days = int(days_to_organize)
        except: target_days = 1

    total_movidos = 0
    os.makedirs(output_root, exist_ok=True)
    
    for day in range(1, target_days + 1):
        day_label = f"Dia_{day}"
        for acc in accounts:
            acc_id = acc['id']
            acc_name = acc['username']
            acc_history = get_account_used_combinations(acc_id) # Historial de esta cuenta específica
            
            target_dir = os.path.join(output_root, day_label, acc_name)
            os.makedirs(target_dir, exist_ok=True)
            
            videos_hoy = 0
            while videos_hoy < daily_quota:
                vid_name = None
                
                # ESTRATEGIA 1: Buscar video en la tanda que no choque GLOBALMENTE hoy (solo P1)
                for i, v in enumerate(videos_originales):
                    p1, p2 = parse_combination_from_filename(v)
                    if not is_p1_collision_global(day, p1):
                        vid_name = videos_originales.pop(i)
                        mark_p1_used_global(day, p1)
                        break
                
                # ESTRATEGIA 2: Si no hay en stock o hay choques, forzar FILL-UP con metadatos nuevos
                if not vid_name and use_fillup:
                    # Buscamos en la tanda CUALQUIER video cuyo P1 no haya sido usado por ESTA cuenta nunca
                    # y que no haya sido usado GLOBALMENTE hoy.
                    videos_tanda = [f for f in os.listdir(tanda_path) if f.lower().endswith(('.mp4', '.mov'))]
                    random.shuffle(videos_tanda)
                    
                    for v_alt in videos_tanda:
                        p1_alt, p2_alt = parse_combination_from_filename(v_alt)
                        # Condición: P1 no usado por la cuenta nunca Y P1 no usado por nadie hoy
                        if (p1_alt, p2_alt) not in acc_history and not is_p1_collision_global(day, p1_alt):
                            vid_name = v_alt
                            mark_p1_used_global(day, p1_alt)
                            break

                if vid_name:
                    src = os.path.join(tanda_path, vid_name)
                    dst = os.path.join(target_dir, vid_name)
                    shutil.copy2(src, dst)
                    
                    # CAMBIO DE METADATA: Hacemos el video "único" físicamente
                    change_video_metadata(dst)
                    
                    # Registro en DB
                    p1, p2 = parse_combination_from_filename(vid_name)
                    db.add_video_to_history(acc_id, dst, p1, p2, "Auto-Generated", day)
                    
                    videos_hoy += 1
                    total_movidos += 1
                else:
                    # Si llega aquí, es que realmente se acabaron los P1 únicos para hoy
                    break 

    db.close()
    return f"🚀 Logística terminada. {total_movidos} videos procesados (Metadata actualizada en duplicados)."
    """Ejecución real de la distribución, moviendo archivos y guardando en DB."""
    try:
        db = DatabaseManager()
        accounts = db.get_accounts_by_category(dest_category)
        if not accounts: return "No hay cuentas."

        tanda_dir = os.path.join(base_dir, "videos_finales", tanda_name)
        if not os.path.exists(tanda_dir): return "Carpeta de tanda no encontrada."
            
        videos_disponibles = [f for f in os.listdir(tanda_dir) if f.lower().endswith(('.mp4', '.mov'))]
        if not videos_disponibles: return "No hay videos en la tanda."

        global_used_p1_real = {}
        global_used_p2_real = {}
        total_asignados = 0
        os.makedirs(output_root, exist_ok=True)

        for account in accounts:
            acc_id = account['id']
            acc_name = account['username']
            used_local = get_account_used_combinations(acc_id)
            video_idx = 0
            
            for dia in range(1, 31): 
                if dia not in global_used_p1_real:
                    global_used_p1_real[dia] = set()
                    global_used_p2_real[dia] = set()

                dia_dir = os.path.join(output_root, f"Dia_{dia}", acc_name)
                os.makedirs(dia_dir, exist_ok=True)
                videos_hoy = 0
                intentos = 0
                
                while videos_hoy < daily_quota and intentos < len(videos_disponibles) * 2:
                    filename = videos_disponibles[video_idx % len(videos_disponibles)]
                    p1_id, p2_id = parse_combination_from_filename(filename)
                    if not p1_id: p1_id, p2_id = (filename, "UNK")
                    
                    choque_local = (p1_id, p2_id) in used_local
                    choque_global = (p1_id in global_used_p1_real[dia]) or (p2_id in global_used_p2_real[dia])

                    if not choque_global and (fillup or not choque_local):
                        # ¡APROBADO! Mover archivo
                        src_path = os.path.join(tanda_dir, filename)
                        dest_path = os.path.join(dia_dir, filename)
                        shutil.copy2(src_path, dest_path)
                        
                        # Bloquear variables globalmente y localmente
                        global_used_p1_real[dia].add(p1_id)
                        global_used_p2_real[dia].add(p2_id)
                        used_local.add((p1_id, p2_id))
                        
                        # Guardar historial real en DB
                        db.add_video_to_history(acc_id, dest_path, p1_id, p2_id, "Caption TBD", dia)
                        
                        videos_hoy += 1
                        total_asignados += 1
                    
                    video_idx += 1
                    intentos += 1

        db.close()
        return f"✅ Distribución completada. {total_asignados} videos asignados a la categoría {dest_category} siguiendo el algoritmo anti-choque global."
    except Exception as e:
        return f"Error crítico durante la distribución: {str(e)}"
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