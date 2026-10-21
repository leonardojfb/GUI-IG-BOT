import os
import shutil
import sys
import random
import string
import math
import json
import re
from collections import defaultdict
from calendar_manifest import build_entry, manifest_path, replace_entries
from database import DatabaseManager
from console_encoding import ensure_stdout_utf8

ensure_stdout_utf8()

# --- CONFIGURACIÓN DE RUTAS ---
base_dir = os.path.dirname(os.path.abspath(__file__))
source_root = os.path.join(base_dir, "videos_finales")
output_root = os.path.join(base_dir, "CALENDARIO_POSTEO")


def _tanda_video_inventory(tanda_path, extensions=(".mp4", ".mov")):
    """Return only published Forge copies; incomplete iPhone batches fail closed."""
    status_path = os.path.join(tanda_path, "forge_batch_status.json")
    videos = [name for name in os.listdir(tanda_path)
              if name.lower().endswith(extensions)]
    if not os.path.isfile(status_path):
        return videos, None
    try:
        with open(status_path, encoding="utf-8") as status_file:
            status = json.load(status_file)
        pending_names = {
            item["output_name"] for item in status["pending"]
            if isinstance(item, dict) and item.get("output_name")
        }
        if status.get("state") == "processing":
            published = sorted(name for name in videos if name in pending_names)
            if published:
                pending_count = len(pending_names - set(published))
                return published, (
                    f"Tanda Forge parcial: usando {len(published)} copias publicadas; "
                    f"{pending_count} pendientes."
                )
        validated = set(status["validated"])
        if not validated or not validated.issubset(set(videos)):
            return [], "Inventario Forge inválido: faltan copias validadas."
        if status.get("state") == "incomplete":
            pending_count = len(pending_names)
            return [name for name in videos if name in validated], (
                f"Tanda Forge parcial: usando {len(validated)} copias validadas; "
                f"{pending_count} pendientes."
            )
        if status.get("state") != "complete":
            return [], "Tanda Forge incompleta: reintenta las copias pendientes antes de Logística."
        return [name for name in videos if name in validated], None
    except (OSError, ValueError, KeyError, TypeError):
        return [], "Estado Forge ilegible: no se puede distribuir esta tanda."


def _is_partial_inventory_notice(message):
    return isinstance(message, str) and message.startswith("Tanda Forge parcial:")


def _origin_key_from_filename(filename: str) -> str:
    """Return the original video identity shared by its Forge copy variants."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = stem.split("__TANDA_", 1)[0]
    stem = re.sub(r"__c\d+$", "", stem, flags=re.IGNORECASE)
    p1, p2 = parse_combination_from_filename(stem)
    if p1 and p2:
        return f"{p1}__{p2}"
    return p1 or stem


def _minimum_days_for_origins(videos, daily_quota: int) -> int:
    origins_by_p1 = defaultdict(set)
    for filename in videos:
        origin = _origin_key_from_filename(filename)
        p1, _p2 = parse_combination_from_filename(filename)
        origins_by_p1[p1 or origin].add(origin)
    origin_count = len({origin for origins in origins_by_p1.values() for origin in origins})
    same_p1_limit = max((len(origins) for origins in origins_by_p1.values()), default=0)
    return max(math.ceil(origin_count / daily_quota), same_p1_limit)


# Parámetros de distribución diaria
DAILY_GOAL = 46
FILL_UP_ENABLED = True


def build_calendar_video_filename(video_filename, tanda_name, account_id, day, slot, collision_suffix=None):
    base, ext = os.path.splitext(video_filename)
    tanda_tag = str(tanda_name or "").strip().replace(" ", "_")
    suffix = f"__{collision_suffix}" if collision_suffix is not None else ""
    return f"{base}__TANDA_{tanda_tag}__ACC{account_id}__D{day}__S{slot}{suffix}{ext}"


def preview_distribution_tanda(tanda_name, category_dest, daily_quota, use_fillup, days_to_organize="MAX"):
    """
    Reporta el inventario de orígenes que recibirá cada cuenta, sin duplicarlos.
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

    videos, inventory_notice = _tanda_video_inventory(tanda_path)
    if inventory_notice and not _is_partial_inventory_notice(inventory_notice):
        db.close()
        return f"❌ {inventory_notice}"
    num_cuentas = len(accounts)
    if daily_quota < 1:
        db.close()
        return "❌ ERROR: La cuota diaria debe ser al menos 1."

    origins = {_origin_key_from_filename(video) for video in videos}
    total_origins = len(origins)
    required_days = _minimum_days_for_origins(videos, daily_quota)
    if str(days_to_organize).upper() == "MAX":
        target_days = required_days
    else:
        try:
            target_days = int(days_to_organize)
        except (TypeError, ValueError):
            db.close()
            return "❌ ERROR: Los días a organizar deben ser un número o MAX."
        if target_days < 1 and total_origins:
            db.close()
            return "❌ ERROR: Los días a organizar deben ser al menos 1."

    resumen =  f"╔════════════════════════════════════════════════════════════════════╗\n"
    resumen += f"║   🎬 REPORTE ESTRATÉGICO DE DISTRIBUCIÓN: {tanda_name:<16} ║\n"
    resumen += f"╚════════════════════════════════════════════════════════════════════╝\n\n"
    
    resumen += f"📈 RESUMEN DE INVENTARIO:\n"
    resumen += f"  ├─ Categoría Destino:  {category_dest}\n"
    resumen += f"  ├─ Archivos Forge disponibles: {len(videos)}\n"
    resumen += f"  ├─ Orígenes únicos en la tanda: {total_origins}\n"
    resumen += f"  ├─ Cuentas destino: {num_cuentas}\n"
    resumen += f"  ├─ Tanda completa por cuenta: {total_origins} videos\n"
    resumen += f"  └─ Total a distribuir: {total_origins * num_cuentas} videos\n\n"

    resumen += f"🗓️ PLANIFICACIÓN (Modo: {'MÁXIMO' if days_to_organize == 'MAX' else 'FIJO'}):\n"
    resumen += f"  ├─ Días mínimos para completar la tanda: {required_days}\n"
    resumen += f"  ├─ Días solicitados: {target_days}\n"
    resumen += f"  └─ Cuota diaria por cuenta: {daily_quota}\n\n"

    resumen += f"👥 DETALLE POR CUENTA Y ASISTENTE (VA):\n"
    resumen += f"{'CUENTA':<18} | {'VA ASIGNADO':<15} | {'VIDEOS':<8} | {'ESTADO'}\n"
    resumen += f"{'-'*68}\n"

    for acc in accounts:
        user = f"@{acc['username']}"
        va = acc.get('assigned_va', '⚠️ SIN VA')
        fits = required_days <= target_days
        status = "✅ tanda completa" if fits else "⚠️ faltan días"
        resumen += f"{user[:18]:<18} | {va[:15]:<15} | {total_origins:<8} | {status}\n"

    resumen += f"\n{'='*68}\n"
    if required_days > target_days:
        resumen += (
            f"⚠️ Faltan {required_days - target_days} día(s) para repartir la tanda completa "
            "sin repetir un origen en la cuenta.\n"
        )
    else:
        resumen += (
            "💡 Cada cuenta recibe cada origen una vez; las copias Forge se rotan entre cuentas "
            "y se mantienen las reglas anti-colisión.\n"
        )
    if use_fillup:
        resumen += "ℹ️ Fill-up no repite orígenes dentro de una cuenta.\n"

    if inventory_notice:
        resumen = f"⚠️ {inventory_notice}\n\n" + resumen
    
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
    Extrae el origen P1+P2, quitando el sufijo de copia que agrega Forge.
    """
    name = os.path.splitext(os.path.basename(filename))[0].split("__TANDA_", 1)[0]
    name = re.sub(r"__c\d+$", "", name, flags=re.IGNORECASE)
    parts = name.split("__")
    if len(parts) >= 3:
        return (parts[1], parts[2])
    if name:
        return (name, None)
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
            if p1:
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
            if p1:
                used.add((p1, p2))
    except Exception:
        pass

    return used


def get_account_used_combinations_for_tandas(account_id: int, tanda_names) -> set:
    """Combinaciones P1+P2 que una cuenta ya recibió, pero solo de estas tandas.

    A diferencia de get_account_used_combinations (todo el historial, cualquier
    tanda), esta variante filtra por el tag `__TANDA_<nombre>__` que Logistica
    graba en cada archivo calendarizado. Es intencional: el nombre de salida de
    Forge (`source__cNN`) parsea al mismo (p1, p2) que la tanda de Edicion/Tandas
    de la que salio su fuente, aunque sean tandas distintas con carpetas
    distintas. Comparar contra *todo* el historial bloquearia una tanda nueva
    solo porque coincide en p1/p2 con una fuente ya usada en otra tanda; acotar
    a estas tandas evita ese falso choque y sigue bloqueando lo que se pidio:
    que una cuenta no reciba el mismo video dos veces si la MISMA tanda se
    vuelve a distribuir en una corrida separada.
    """
    used = set()
    tags = {str(name or "").strip().replace(" ", "_") for name in tanda_names if name}
    if not tags:
        return used
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT video_path, p1_source, p2_source, assigned_caption
            FROM fingerprint_history
            WHERE account_id = ?
            """,
            (account_id,)
        )
        rows = cursor.fetchall()
        db.close()

        for row in rows:
            video_path = row["video_path"] or ""
            assigned_caption = row["assigned_caption"] or ""
            tagged_path_match = any(f"__TANDA_{tag}__" in os.path.basename(video_path) for tag in tags)
            caption_match = any(assigned_caption == f"Auto-Generated / {tag}" for tag in tags)
            if not tagged_path_match and not caption_match:
                continue
            p1 = row["p1_source"]
            p2 = row["p2_source"]
            if not p1:
                p1, p2 = parse_combination_from_filename(os.path.basename(video_path))
            if p1:
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

def pick_random_video_for_account_day_slot(videos_pool, used_p1_today_account, used_p1_this_slot):
    """
    Elige video con aleatoriedad real.

    Regla dura:
    - No repetir PT1 en la misma cuenta el mismo día.

    Regla blanda:
    - Evitar repetir PT1 en el mismo slot/hora entre cuentas.
    """

    candidates = videos_pool[:]
    random.shuffle(candidates)

    # Nivel 1: ideal, no repite PT1 en cuenta/día ni en slot global
    for v in candidates:
        p1, p2 = parse_combination_from_filename(v)

        if not p1:
            continue

        if p1 in used_p1_today_account:
            continue

        if p1 in used_p1_this_slot:
            continue

        return v

    # Nivel 2: si no hay alternativa, permite choque en slot,
    # pero NUNCA repite PT1 en la misma cuenta/día
    for v in candidates:
        p1, p2 = parse_combination_from_filename(v)

        if not p1:
            continue

        if p1 in used_p1_today_account:
            continue

        return v

    return None
def pick_random_video_item_for_account_day_slot(
    video_items_pool,
    used_p1_today_account,
    used_p1_this_slot,
    p1_usage_day=None,
    p1_usage_global=None,
    used_combos_account=None,
):
    """
    Selecciona video conservando el orden rotativo salvo que otro candidato
    evite una colisión en el mismo slot.

    Reglas duras:
    - No repetir PT1 en la misma cuenta el mismo día.
    - No repetir la misma combinación PT1+PT2 en la misma cuenta (nunca, entre todos los días).

    Regla blanda:
    - Evitar PT1 ya usado en el mismo slot, conservando el orden rotativo como
      criterio estable cuando no hay una alternativa que reduzca el choque.
    """

    if p1_usage_day is None:
        p1_usage_day = {}
    if p1_usage_global is None:
        p1_usage_global = {}
    if used_combos_account is None:
        used_combos_account = set()

    candidates = []

    for item in video_items_pool:
        p1, p2 = parse_combination_from_filename(item["filename"])

        if not p1:
            continue

        # REGLA DURA 1: no repetir PT1 en la misma cuenta hoy
        if p1 in used_p1_today_account:
            continue

        # REGLA DURA 2: no repetir combinación PT1+PT2 en la misma cuenta (nunca)
        if (p1, p2) in used_combos_account:
            continue

        collides_in_slot = p1 in used_p1_this_slot
        candidates.append((collides_in_slot, item))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]
def distribute_tanda(tanda_name, category_dest, daily_quota, use_fillup, days_to_organize="MAX", tanda_name_2=None):
    db = DatabaseManager()

    all_accs = db.get_all_accounts()
    accounts = [
        a for a in all_accs
        if a["account_type"].upper() == category_dest.upper()
    ]
    accounts.sort(key=lambda account: account["username"].casefold())

    if not accounts:
        db.close()
        return "❌ Error: No hay cuentas para esta categoría."

    tanda_names = [tanda_name]

    if tanda_name_2 and str(tanda_name_2).strip():
        tanda_names.append(tanda_name_2)

    video_items = []
    partial_notices = []

    for tn in tanda_names:
        tanda_path = os.path.join(source_root, tn)

        if not os.path.exists(tanda_path):
            db.close()
            return f"❌ Error: No existe la tanda: {tanda_path}"

        videos, inventory_notice = _tanda_video_inventory(tanda_path)
        if inventory_notice and not _is_partial_inventory_notice(inventory_notice):
            db.close()
            return f"❌ {inventory_notice}"
        if inventory_notice:
            partial_notices.append(f"{tn}: {inventory_notice}")
        for f in videos:
            video_items.append({
                "filename": f,
                "tanda": tn,
                "path": os.path.join(tanda_path, f)
            })

    if not video_items:
        db.close()
        return "❌ Error: No hay videos en las tandas seleccionadas."

    if daily_quota < 1:
        db.close()
        return "❌ Error: La cuota diaria debe ser al menos 1."

    origin_groups = defaultdict(list)
    for item in video_items:
        item["origin"] = _origin_key_from_filename(item["filename"])
        origin_groups[item["origin"]].append(item)
    for variants in origin_groups.values():
        variants.sort(key=lambda item: item["filename"].casefold())
    ordered_origins = sorted(origin_groups)

    origins_per_account = len(origin_groups)
    origins_by_p1 = defaultdict(set)
    for origin, variants in origin_groups.items():
        p1, _p2 = parse_combination_from_filename(variants[0]["filename"])
        origins_by_p1[p1 or origin].add(origin)
    required_days = max(
        math.ceil(origins_per_account / daily_quota),
        max((len(origins) for origins in origins_by_p1.values()), default=0),
    )
    if str(days_to_organize).upper() == "MAX":
        target_days = required_days
    else:
        try:
            target_days = int(days_to_organize)
        except (TypeError, ValueError):
            db.close()
            return "❌ Error: Los días a organizar deben ser un número o MAX."
        if target_days < 1 and origins_per_account:
            db.close()
            return "❌ Error: Los días a organizar deben ser al menos 1."
    if target_days < required_days:
        db.close()
        return (
            f"❌ La tanda tiene {origins_per_account} orígenes por cuenta y la cuota es "
            f"{daily_quota} por día. Se necesitan al menos {required_days} días para "
            "entregarla completa sin repetir orígenes."
        )

    total_movidos = 0
    manifest_entries = []
    affected_usernames = {acc["username"] for acc in accounts}
    logical_filenames = set()

    p1_usage_global = {}

    # Reparte una variante de cada origen a cada cuenta. Si hay suficientes copias
    # Forge, cada cuenta recibe una variante distinta del mismo origen.
    account_lifetime_combos = defaultdict(set)  # acc_id -> set of (p1, p2)
    for acc in accounts:
        account_lifetime_combos[acc["id"]] |= get_account_used_combinations_for_tandas(
            acc["id"], tanda_names
        )

    account_video_pools = {}
    variant_cursor = defaultdict(int)
    for account_index, acc in enumerate(accounts):
        acc_id = acc["id"]
        account_pool = []
        rotation = account_index % len(ordered_origins)
        account_origins = ordered_origins[rotation:] + ordered_origins[:rotation]
        for origin_key in account_origins:
            variants = origin_groups[origin_key]
            eligible = []
            for item in variants:
                p1, p2 = parse_combination_from_filename(item["filename"])
                if p1 and (p1, p2) in account_lifetime_combos[acc_id]:
                    continue
                eligible.append(item)
            if not eligible:
                continue
            cursor = variant_cursor[origin_key]
            account_pool.append(eligible[cursor % len(eligible)])
            variant_cursor[origin_key] = cursor + 1
        account_video_pools[acc_id] = account_pool

    try:
        for day in range(1, target_days + 1):
            day_label = f"Dia_{day}"

            used_p1_by_account_today = {}

            used_p1_by_slot = {
                slot: set()
                for slot in range(1, daily_quota + 1)
            }
            p1_usage_day = {}

            for slot in range(1, daily_quota + 1):
                for acc in accounts:
                    acc_id = acc["id"]
                    acc_name = acc["username"]

                    day_key = (acc_id, day)

                    if day_key not in used_p1_by_account_today:
                        used_p1_by_account_today[day_key] = set()

                    account_pool = account_video_pools[acc_id]
                    vid_item = pick_random_video_item_for_account_day_slot(
                        account_pool,
                        used_p1_by_account_today[day_key],
                        used_p1_by_slot[slot],
                        p1_usage_day,
                        p1_usage_global,
                        account_lifetime_combos[acc_id],
                    )

                    if vid_item:
                        account_pool.remove(vid_item)

                    if not vid_item:
                        print(f"⚠️ Sin video válido para {acc_name} / Día {day} / Slot {slot}")
                        continue

                    src = vid_item["path"]
                    vid_name = vid_item["filename"]

                    unique_name = build_calendar_video_filename(
                        vid_name, vid_item["tanda"], acc_id, day, slot
                    )

                    if unique_name in logical_filenames:
                        unique_name = build_calendar_video_filename(
                            vid_name,
                            vid_item["tanda"],
                            acc_id,
                            day,
                            slot,
                            collision_suffix=random.randint(1000, 9999),
                        )
                    logical_filenames.add(unique_name)

                    p1, p2 = parse_combination_from_filename(vid_name)

                    if p1:
                        used_p1_by_account_today[day_key].add(p1)
                        used_p1_by_slot[slot].add(p1)
                        p1_usage_day[p1] = p1_usage_day.get(p1, 0) + 1
                        p1_usage_global[p1] = p1_usage_global.get(p1, 0) + 1
                    if p1:
                        account_lifetime_combos[acc_id].add((p1, p2))

                    manifest_entries.append(
                        build_entry(
                            username=acc_name,
                            account_id=acc_id,
                            delivery_kind="normal",
                            day=day,
                            slot=slot,
                            tanda=vid_item["tanda"],
                            source_path=src,
                            telegram_filename=unique_name,
                            transform_log_id=db.get_video_transform_log_id(src),
                            origin_identity=db.get_video_transform_source_identity(src),
                        )
                    )
                    db.add_video_to_history(
                        acc_id,
                        src,
                        p1,
                        p2,
                        f"Auto-Generated / {vid_item['tanda']}",
                        day
                    )

                    total_movidos += 1
        if affected_usernames:
            replace_entries(
                manifest_path(base_dir),
                manifest_entries,
                affected_usernames,
                "normal",
                tanda_names=set(tanda_names),
            )
    finally:
        db.close()

    partial_message = (
        "\n" + "\n".join(f"⚠️ {notice}" for notice in partial_notices)
        if partial_notices else ""
    )
    return (
        f"✅ Logística terminada.\n"
        f"{total_movidos} videos procesados.\n"
        f"{origins_per_account} orígenes únicos por cuenta; variantes Forge rotadas entre cuentas.\n"
        f"Tandas usadas: {', '.join(tanda_names)}\n"
        f"Categoría destino: {category_dest}\n"
        f"Reglas aplicadas: no repetir origen por cuenta, no repetir P1 por cuenta/día "
        "y minimizar choques de P1 en el mismo horario."
        + ("\nFill-up omitido para no repetir orígenes por cuenta." if use_fillup else "")
        + f"{partial_message}"
    )
if __name__ == "__main__":
    print("--- INICIANDO ORGANIZACION CON ANTI-CHOQUE GLOBAL ---")

    distribute(daily_goal=46, fill_up=True)

    print("\n--- ORGANIZACION CON ANTI-CHOQUE GLOBAL COMPLETADA ---")
