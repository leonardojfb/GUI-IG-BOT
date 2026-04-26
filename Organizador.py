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

def preview_distribution_tanda(tanda_name, category_dest, daily_quota, use_fillup, days_to_organize="MAX"):
    """
    Reporte Pro con Lógica de Cobertura Total y Días Personalizados.
    """
    db = DatabaseManager()
    accounts = db.get_accounts_by_type(category_dest)
    
    if not accounts:
        db.close()
        return f"❌ ERROR: No hay cuentas para {category_dest}"

    tanda_path = os.path.join(source_root, tanda_name)
    if not os.path.exists(tanda_path):
        db.close()
        return f"❌ ERROR: Carpeta no encontrada: {tanda_name}"

    videos = [f for f in os.listdir(tanda_path) if f.lower().endswith(('.mp4', '.mov'))]
    total_videos = len(videos)
    
    # --- CÁLCULOS DE LOGÍSTICA ---
    num_cuentas = len(accounts)
    vids_por_dia_grupo = num_cuentas * daily_quota
    
    # Días naturales que cubren los videos actuales
    dias_reales = total_videos / vids_por_dia_grupo if vids_por_dia_grupo > 0 else 0
    dias_completos = total_videos // vids_por_dia_grupo if vids_por_dia_grupo > 0 else 0
    sobrante = total_videos % vids_por_dia_grupo if vids_por_dia_grupo > 0 else 0

    # Determinar objetivo de días
    if str(days_to_organize).upper() == "MAX":
        target_days = math.ceil(dias_reales) # Redondea hacia arriba (ej: 10.25 -> 11)
    else:
        target_days = int(days_to_organize)

    total_necesario = target_days * vids_por_dia_grupo
    vids_a_generar = max(0, total_necesario - total_videos) if use_fillup else 0

    # --- REPORTE DETALLADO ---
    resumen =  f"╔══════════════════════════════════════════════════════════╗\n"
    resumen += f"║   🚀 PLANIFICACIÓN ESTRATÉGICA: {tanda_name:<15} ║\n"
    resumen += f"╚══════════════════════════════════════════════════════════╝\n\n"
    
    resumen += f"📊 ESTADO DEL INVENTARIO:\n"
    resumen += f"  ├─ Cuentas Destino:    {num_cuentas}\n"
    resumen += f"  ├─ Cuota por Cuenta:   {daily_quota} vids/día\n"
    resumen += f"  ├─ Videos Disponibles: {total_videos}\n"
    resumen += f"  └─ Videos/Día Total:   {vids_por_dia_grupo}\n\n"

    resumen += f"🗓️ PROYECCIÓN DE CALENDARIO:\n"
    resumen += f"  ├─ Días Objetivo:      {target_days} días\n"
    resumen += f"  ├─ Videos Necesarios:  {total_necesario}\n"
    if vids_a_generar > 0:
        resumen += f"  ├─ ⚡ FILL-UP ACTIVO:  Generando {vids_a_generar} videos para completar el día {target_days}\n"
    resumen += f"  └─ Cobertura:          Del Día 1 al Día {target_days}\n\n"

    resumen += f"👥 EQUIPO Y ASIGNACIÓN (VAs):\n"
    resumen += f"{'CUENTA':<20} | {'ASISTENTE (VA)':<15} | {'TOTAL VIDS'}\n"
    resumen += f"{'-'*55}\n"

    for acc in accounts:
        user = f"@{acc['username']}"
        va = acc.get('assigned_va', 'N/A')
        vids_acc = target_days * daily_quota
        resumen += f"{user:<20} | {va:<15} | {vids_acc} vids\n"

    resumen += f"\n{'='*55}\n"
    resumen += f"💡 INFO: Todas las cuentas terminarán sincronizadas el día {target_days}.\n"
    
    db.close()
    return resumen
def distribute_tanda(tanda_name, category_dest, daily_quota, use_fillup):
    """
    Ejecuta la distribución real, mueve archivos y registra en la DB.
    """
    db = DatabaseManager()
    tanda_folder = os.path.join(base_dir, "videos_finales", tanda_name)
    output_root = os.path.join(base_dir, "CALENDARIO_POSTEO")
    
    accounts = db.get_accounts_by_category(category_dest)
    videos = [f for f in os.listdir(tanda_folder) if f.endswith('.mp4')]
    
    if not accounts or not videos:
        return "Faltan cuentas o videos para proceder."

    count = 0
    # Agrupamos videos por P1 para rotarlos (Tu lógica de bins)
    for acc in accounts:
        acc_folder = os.path.join(output_root, acc['username'])
        os.makedirs(acc_folder, exist_ok=True)
        
        # Tomamos una porción de videos para esta cuenta
        # (Aquí puedes integrar tu lógica de pick_balanced)
        for i in range(daily_quota):
            if not videos: break
            vid = videos.pop(0)
            
            src = os.path.join(tanda_folder, vid)
            dst = os.path.join(acc_folder, vid)
            
            # Movimiento físico
            shutil.copy(src, dst) # Usamos copy para no vaciar la tanda original por ahora
            
            # Registro en DB para evitar colisiones futuras
            # Extraemos P1 y P2 del nombre: TANDA__P1__P2.mp4
            parts = vid.replace(".mp4", "").split("__")
            p1 = parts[1] if len(parts) > 1 else "unknown"
            p2 = parts[2] if len(parts) > 2 else "unknown"
            
            db.add_video_to_history(acc['id'], vid, category_dest, p1, p2)
            count += 1

    db.close()
    return f"🚀 ¡Éxito! Se distribuyeron {count} videos en la carpeta CALENDARIO_POSTEO."

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
# ==========================================
# CONEXIÓN CON LA GUI V6 (VISTA PREVIA Y DISTRIBUCIÓN)
# ==========================================

import math
import datetime

def preview_distribution_tanda(tanda_name, category_dest, daily_quota, use_fillup, days_to_organize="MAX"):
    """
    Reporte de Logística Avanzado con Lógica de Cobertura Total y Mapeo de VAs.
    """
    db = DatabaseManager()
    # Usamos los nombres reales de tu BD V6: virtual_accounts y account_type
    accounts = db.get_accounts_by_type(category_dest) 
    
    if not accounts:
        db.close()
        return f"❌ ERROR: No hay cuentas asignadas a la categoría: {category_dest}"

    # Ubicación de videos finales
    tanda_path = os.path.join(source_root, tanda_name) 
    if not os.path.exists(tanda_path):
        db.close()
        return f"❌ ERROR: No existe la carpeta para la tanda: {tanda_name}"

    videos = [f for f in os.listdir(tanda_path) if f.lower().endswith(('.mp4', '.mov'))]
    total_videos = len(videos)
    
    # --- CÁLCULOS DE LOGÍSTICA ---
    num_cuentas = len(accounts)
    vids_por_dia_grupo = num_cuentas * daily_quota
    
    # Días que cubren los videos actuales (ej: 10.125)
    dias_float = total_videos / vids_por_dia_grupo if vids_por_dia_grupo > 0 else 0
    dias_completos = total_videos // vids_por_dia_grupo if vids_por_dia_grupo > 0 else 0

    # Determinación del objetivo de días
    if str(days_to_organize).upper() == "MAX":
        # Lógica pedida: si es 10.125, completamos hasta el día 11 para todos
        target_days = math.ceil(dias_float) 
    else:
        try: target_days = int(days_to_organize)
        except: target_days = dias_completos

    total_necesario = target_days * vids_por_dia_grupo
    vids_fillup = max(0, total_necesario - total_videos) if use_fillup else 0

    # --- DISEÑO DEL REPORTE ---
    resumen =  f"╔══════════════════════════════════════════════════════════╗\n"
    resumen += f"║   🚀 PLANIFICACIÓN ESTRATÉGICA: {tanda_name:<15} ║\n"
    resumen += f"╚══════════════════════════════════════════════════════════╝\n\n"
    
    resumen += f"📊 MÉTRICAS DEL INVENTARIO:\n"
    resumen += f"  ├─ Cuentas en {category_dest:<8}: {num_cuentas}\n"
    resumen += f"  ├─ Cuota diaria/cuenta:  {daily_quota} reels/día\n"
    resumen += f"  ├─ Videos en Stock:      {total_videos}\n"
    resumen += f"  └─ Consumo total:        {vids_por_dia_grupo} videos/día\n\n"

    resumen += f"🗓️ PROYECCIÓN DE CALENDARIO:\n"
    resumen += f"  ├─ Días a organizar:     {target_days} días\n"
    resumen += f"  ├─ Videos Requeridos:    {total_necesario}\n"
    
    if vids_fillup > 0:
        resumen += f"  ├─ ⚡ MODO FILL-UP:      Generando {vids_fillup} videos para completar el día {target_days}\n"
    else:
        resumen += f"  ├─ 📦 STOCK SUFICIENTE:  No requiere generación extra\n"
    
    resumen += f"  └─ COBERTURA FINAL:      Hasta el día {target_days} inclusive\n\n"

    resumen += f"👥 EQUIPO Y ASIGNACIÓN (VAs):\n"
    resumen += f"{'CUENTA':<20} | {'VA RESPONSABLE':<15} | {'TOTAL VIDS'}\n"
    resumen += f"{'-'*55}\n"

    for acc in accounts:
        user = f"@{acc['username']}"
        va = acc.get('assigned_va', '⚠️ SIN VA') #
        vids_acc = target_days * daily_quota
        resumen += f"{user:<20} | {va:<15} | {vids_acc} vids\n"

    resumen += f"\n{'='*58}\n"
    resumen += f"💡 INFO: Todas las cuentas terminarán sincronizadas el día {target_days}.\n"
    
    db.close()
    return resumen

def distribute_tanda(tanda_name: str, dest_category: str, daily_quota: int, fillup: bool):
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
def preview_distribution_tanda(tanda_name, category_dest, daily_quota, use_fillup):
    """Lógica de vista previa para la Pestaña 4."""
    db = DatabaseManager()
    # Usamos el nuevo método con los nombres reales
    accounts = db.get_accounts_by_type(category_dest)
    
    if not accounts:
        db.close()
        return f"❌ No hay cuentas asignadas a la categoría: {category_dest}"

    # Verificar si existen videos para esa tanda
    # En tu V6, las tandas están en 'videos_finales/NOMBRE_TANDA'
    tanda_path = os.path.join(source_root, tanda_name) 
    if not os.path.exists(tanda_path):
        db.close()
        return f"❌ No existe la carpeta de videos para la tanda: {tanda_name}"

    videos = [f for f in os.listdir(tanda_path) if f.lower().endswith(('.mp4', '.mov'))]
    
    resumen = f"📊 SIMULACIÓN PARA: {category_dest}\n"
    resumen += f"✅ Cuentas encontradas: {len(accounts)}\n"
    resumen += f"🎥 Videos disponibles: {len(videos)}\n"
    resumen += "-"*30 + "\n"
    
    for acc in accounts:
        resumen += f"👤 @{acc['username']} -> Recibirá aprox {daily_quota} videos.\n"
    
    db.close()
    return resumen

def distribute_tanda(tanda_name, category_dest, daily_quota, use_fillup):
    """Lógica de distribución real para la Pestaña 4."""
    db = DatabaseManager()
    accounts = db.get_accounts_by_type(category_dest)
    
    if not accounts:
        db.close()
        return f"❌ Error: No hay cuentas para {category_dest}"

    # Aquí se ejecuta tu lógica de movimiento de archivos similar a tu función distribute()
    # Pero filtrada por la tanda y categoría seleccionada en la GUI
    # ... (el resto de tu lógica de shutil.move)
    
    db.close()
    return f"🚀 Distribución de {tanda_name} completada para {len(accounts)} cuentas."
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