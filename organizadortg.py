import os
import threading
import requests
import time
import json
import random
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import DatabaseManager
from trial_content import source_key_from_filename
from console_encoding import ensure_stdout_utf8

ensure_stdout_utf8()

TG_MAX_BYTES = 49 * 1024 * 1024  # 49MB para dejar margen
TG_COMPRESS_TARGET_BYTES = 45 * 1024 * 1024
TG_RECOMPRESS_TARGET_BYTES = 40 * 1024 * 1024

# Windows: suppress the console window each ffmpeg/ffprobe child would otherwise
# pop when the GUI runs windowless. 0 on non-Windows (flag doesn't exist there).
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

def _compress_video_for_tg(video_path: str, target_bytes: int = TG_COMPRESS_TARGET_BYTES) -> str | None:
    """Comprime el video con ffmpeg para que quede bajo TG_MAX_BYTES.
    Devuelve la ruta del archivo temporal comprimido, o None si falla."""
    try:
        import shutil
        if not shutil.which("ffmpeg"):
            print("⚠️  ffmpeg no encontrado en PATH. No se puede comprimir el video.")
            return None

        size_bytes = os.path.getsize(video_path)
        # Obtener duración con ffprobe
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, creationflags=_NO_WINDOW
        )
        if probe.returncode != 0 or not probe.stdout.strip():
            print("⚠️  No se pudo obtener duración del video con ffprobe.")
            return None

        duration = float(probe.stdout.strip())
        # Calcular bitrate objetivo en kbps para quedar bajo el límite
        target_bytes = min(target_bytes, TG_MAX_BYTES)
        target_kbps = int((target_bytes * 8) / duration / 1000 * 0.92)  # 8% de margen extra
        target_kbps = max(target_kbps, 300)  # mínimo 300kbps para calidad mínima aceptable

        suffix = os.path.splitext(video_path)[1] or ".mp4"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.close()

        print(f"🗜️  Comprimiendo video ({size_bytes/1024/1024:.1f}MB → objetivo <{target_bytes/1024/1024:.0f}MB, bitrate {target_kbps}kbps)...")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path,
             "-b:v", f"{target_kbps}k", "-b:a", "128k",
             "-vcodec", "libx264", "-acodec", "aac",
             "-preset", "fast", tmp.name],
            capture_output=True, text=True, creationflags=_NO_WINDOW
        )
        if result.returncode != 0:
            print(f"❌ ffmpeg falló:\n{result.stderr[-500:]}")
            os.unlink(tmp.name)
            return None

        compressed_size = os.path.getsize(tmp.name)
        print(f"✅ Comprimido: {compressed_size/1024/1024:.1f}MB")
        return tmp.name
    except Exception as e:
        print(f"❌ Error al comprimir video: {e}")
        return None

# --- 1. CONFIGURACIÓN Y CREDENCIALES ---
TOKEN = "8787705820:AAGIeKGzhxHZgUmbbH9G9EgK5Y7M11J-MWM"
DEFAULT_CHAT_ID = "-1003749971714"
STATE_FILE = "telegram_state_v11.json"
HISTORY_FILE = "fingerprint_history.json"
ADMIN_TOPIC_NAME = "Admin"
TRIAL_TOPIC_PREFIX = "TRIALS - "

base_dir = os.path.dirname(os.path.abspath(__file__))
input_root = os.path.join(base_dir, "CALENDARIO_POSTEO")
trial_input_root = os.path.join(base_dir, "CALENDARIO_TRIALS")

db = DatabaseManager()


def _windows_long_path(path):
    path = os.path.abspath(os.fspath(path))
    if os.name != "nt" or path.startswith("\\\\?\\"):
        return path
    if path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path


def _count_files_recursive(path):
    count = 0
    for _root, _dirs, files in os.walk(_windows_long_path(path)):
        count += len(files)
    return count


def _safe_calendar_account_name(account_name):
    account_name = str(account_name or "").strip()
    if not account_name:
        return ""
    if "/" in account_name or "\\" in account_name:
        return ""
    if Path(account_name).name != account_name:
        return ""
    return account_name


def delete_calendarizations_for_accounts(account_names, calendar_root=None):
    calendar_path = Path(calendar_root or input_root)
    targets = []
    seen = set()
    for account_name in account_names or []:
        safe_name = _safe_calendar_account_name(account_name)
        if safe_name and safe_name not in seen:
            targets.append(safe_name)
            seen.add(safe_name)

    summary = {
        "accounts": len(targets),
        "deleted_folders": 0,
        "deleted_files": 0,
        "missing_folders": 0,
        "failed": 0,
        "failures": [],
    }

    if not targets or not calendar_path.exists():
        return summary

    calendar_root_resolved = calendar_path.resolve()
    for day_dir in calendar_path.iterdir():
        if not day_dir.is_dir() or not day_dir.name.lower().startswith("dia_"):
            continue
        for account_name in targets:
            account_dir = day_dir / account_name
            if not account_dir.exists():
                summary["missing_folders"] += 1
                continue
            if not account_dir.is_dir():
                summary["failed"] += 1
                summary["failures"].append({
                    "account": account_name,
                    "path": str(account_dir),
                    "error": "calendar target is not a directory",
                })
                continue
            try:
                account_dir.resolve().relative_to(calendar_root_resolved)
                deleted_files = _count_files_recursive(account_dir)
                shutil.rmtree(_windows_long_path(account_dir))
                summary["deleted_folders"] += 1
                summary["deleted_files"] += deleted_files
            except Exception as exc:
                summary["failed"] += 1
                summary["failures"].append({
                    "account": account_name,
                    "path": str(account_dir),
                    "error": str(exc),
                })

    return summary

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


def get_slots_for_set(va_name: str, category: str, day_of_week: int, db_manager) -> list:
    """
    Devuelve los time slots configurados para un set (VA + categoría) en un día.
    Si no hay config en DB, cae al DEFAULT_SCHEDULE estratégico ET.
    """
    row = db_manager.get_schedule_config(va_name, category, day_of_week)
    if row:
        import json as _json
        return _json.loads(row["time_slots"])
    return DEFAULT_SCHEDULE[day_of_week]


# --- 1.6. TIMEZONE CONVERSION ---
TIMEZONE_LABELS = {
    "America/New_York":               ("ET",  "Nueva York"),
    "America/Argentina/Buenos_Aires": ("ART", "Buenos Aires"),
    "America/Chicago":                ("CT",  "Chicago"),
    "America/Los_Angeles":            ("PT",  "Los Ángeles"),
    "Europe/Madrid":                  ("CET", "Madrid"),
    "Europe/London":                  ("GMT", "Londres"),
}


def convert_et_to_va_tz(time_str: str, va_tz_str: str) -> tuple:
    """
    Convierte una hora ET (formato '8:00 AM' o '7:00 PM') al timezone de la VA.
    Devuelve dos strings listos para el mensaje:
        ("8:00 AM ET (Nueva York)", "9:00 AM ART (Buenos Aires)")

    Si va_tz_str es inválido, cae a Buenos Aires.
    """
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


# --- 2. GESTIÓN DE PERSISTENCIA ---
def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)

def load_clean_captions(path=None):
    if not path or not os.path.exists(path):
        return []
    content = open(path, 'r', encoding='utf-8', errors='ignore').read()
    pattern = r'\[\d{1,2}.*?\].*?:\s*(.*?)(?=\s*\[\d{1,2}|$)'
    blocks = re.findall(pattern, content, flags=re.DOTALL)
    captions = [b.strip() for b in blocks if b.strip()]
    if not captions:
        # Fallback: cada bloque separado por una línea en blanco es parte de un
        # caption. Un caption puede contener líneas en blanco internas; sus
        # hashtags suelen marcar el cierre del bloque.
        paragraphs = [block.strip() for block in re.split(r"\r?\n\s*\r?\n", content) if block.strip()]
        captions = []
        pending = []
        for paragraph in paragraphs:
            pending.append(paragraph)
            if re.search(r"#\w+", paragraph):
                captions.append("\n\n".join(pending))
                pending = []
        if pending:
            captions.append("\n\n".join(pending))
    return captions

def shuffle_hashtags(text):
    hashtags = re.findall(r'#\w+', text)
    if not hashtags: return text
    text_no_hashes = re.sub(r'#\w+', '', text).strip()
    random.shuffle(hashtags)
    return f"{text_no_hashes}\n\n{' '.join(hashtags)}"


def caption_for_video(pool, video_index):
    """Asigna captions en orden estable y vuelve a empezar si faltan captions."""
    if not pool:
        return None
    return shuffle_hashtags(pool[video_index % len(pool)])


def _tanda_tag(tanda_name):
    return str(tanda_name or "").strip().replace(" ", "_")


def extract_tanda_tag_from_calendar_filename(filename):
    """Extrae el tag de tanda que Logistica escribe en cada archivo calendarizado."""
    match = re.search(r"__TANDA_(.+?)__ACC\d+__D\d+__S\d+(?:__\d+)?(?:\.[^.]+)?$", os.path.basename(filename))
    return match.group(1) if match else None


def load_tanda_caption_pools(tandas=None):
    """Carga pools por tanda desde la asignacion persistida por Logistica."""
    tandas = db.get_all_tandas() if tandas is None else tandas
    pools = {}
    for tanda in tandas:
        name = tanda.get("tanda_name")
        pool = load_clean_captions(tanda.get("captions_file_path"))
        if name and pool:
            pools[_tanda_tag(name)] = pool
    return pools


def caption_for_calendar_video(filename, pools, caption_indexes):
    """Resuelve el caption por tanda; un archivo sin asignacion se envia sin caption."""
    tanda_tag = extract_tanda_tag_from_calendar_filename(filename)
    pool = pools.get(tanda_tag, []) if tanda_tag else []
    if not pool:
        return None
    index = caption_indexes.get(tanda_tag, 0)
    caption_indexes[tanda_tag] = index + 1
    return caption_for_video(pool, index)


def extract_source_key_from_calendar_filename(filename):
    """Recover the Forge source key from a calendarized Trial filename."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    source_name = re.sub(r"__TANDA_.+$", "", stem)
    return source_key_from_filename(source_name)


def caption_for_trial_calendar_video(filename, captions):
    """Return the saved Trial caption literally, never shuffled or rotated."""
    return captions.get(extract_source_key_from_calendar_filename(filename))


def load_trial_caption_maps():
    return {
        _tanda_tag(tanda): db.get_trial_source_captions(tanda)
        for tanda in db.get_trial_tandas()
    }


def caption_for_normal_individual_video(filename, captions):
    """Return a normal individual caption literally, by Forge source."""
    return captions.get(extract_source_key_from_calendar_filename(filename))


def load_normal_individual_caption_maps():
    return {
        _tanda_tag(tanda["tanda_name"]): captions
        for tanda in db.get_all_tandas()
        if (captions := db.get_normal_source_captions(tanda["tanda_name"]))
    }

history_db = load_json(os.path.join(base_dir, HISTORY_FILE))

# --- 3. BASE DE DATOS Y ENRUTAMIENTO ---
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
            'trials_active': bool(acc.get('trials_active')),
            'assigned_va': va_name, 'tg_group_id': tg_group_id,
            'va_timezone': va_timezone,
        })
    return result

def call_tg(method, data, silent=False):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    for attempt in range(4):
        try:
            res = requests.post(url, json=data).json()
            if not res.get("ok"):
                retry_after = res.get("parameters", {}).get("retry_after")
                if retry_after:
                    print(f"⏳ Telegram rate limit ({method}), esperando {retry_after}s...")
                    time.sleep(retry_after + 1)
                    continue
                if not silent:
                    print(f"⚠️ Error en Telegram API ({method}): {res}")
            return res
        except Exception as e:
            print(f"⚠️ Error de red al llamar a {method}: {e}")
            return {"ok": False}
    return {"ok": False}
def is_video_already_sent(video_path):
    """
    Revisa en fingerprint_history si este video ya fue marcado como enviado.
    Si no existe la columna telegram_status, no bloquea nada.
    """
    try:
        cur = db.conn.cursor()

        cur.execute("PRAGMA table_info(fingerprint_history)")
        columns = [row["name"] for row in cur.fetchall()]

        if "telegram_status" not in columns:
            return False

        cur.execute("""
            SELECT telegram_status
            FROM fingerprint_history
            WHERE video_path = ?
            LIMIT 1
        """, (video_path,))

        row = cur.fetchone()

        if not row:
            return False

        return str(row["telegram_status"]).lower() == "sent"

    except Exception as e:
        print(f"⚠️ No se pudo verificar estado Telegram: {e}")
        return False

def _is_trials_subaccount(account_name="", account_type=""):
    return "trial" in f"{account_name or ''} {account_type or ''}".lower()


def topic_state_key(chat_id, acc_name, delivery_kind="normal"):
    suffix = "_trials" if delivery_kind == "trial" else ""
    return f"{chat_id}_{acc_name}{suffix}"


def _topic_display_name(acc_name, tag_emoji, is_admin=False, delivery_kind="normal"):
    if is_admin:
        return acc_name
    full_name = f"{acc_name} {tag_emoji}"
    if (delivery_kind == "trial" or _is_trials_subaccount(acc_name, tag_emoji)) and not full_name.lower().startswith(TRIAL_TOPIC_PREFIX.lower()):
        return f"{TRIAL_TOPIC_PREFIX}{full_name}"
    return full_name


def get_or_create_topic(chat_id, acc_name, tag_emoji, state, is_admin=False, force_recreate=False, delivery_kind="normal"):
    full_name = _topic_display_name(acc_name, tag_emoji, is_admin=is_admin, delivery_kind=delivery_kind)
    state_key = topic_state_key(chat_id, acc_name, delivery_kind)
    if state_key in state and not force_recreate: return _topic_id_from_state_value(state[state_key])
    if force_recreate: state.pop(state_key, None)
    res = call_tg("createForumTopic", {'chat_id': chat_id, 'name': full_name})
    if res.get("ok"):
        topic_id = res["result"]["message_thread_id"]
        state[state_key] = {"id": topic_id, "name": full_name}
        return topic_id
    print(f"❌ createForumTopic falló | chat_id usado: '{chat_id}' | cuenta: {acc_name} | error: {res.get('description')}")
    return None

def _topic_state_chat_id(state_key):
    if not isinstance(state_key, str) or "_" not in state_key:
        return None
    return state_key.split("_", 1)[0]

def _topic_state_account_name(state_key):
    if not isinstance(state_key, str) or "_" not in state_key:
        return None
    return state_key.split("_", 1)[1]

def _normalize_account_name(name):
    return str(name or "").strip().lstrip("@").lower()

def _topic_id_from_state_value(value):
    if isinstance(value, dict):
        value = value.get("id") or value.get("message_thread_id") or value.get("topic_id")
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value

def _topic_name_from_state_value(value):
    if isinstance(value, dict):
        return str(value.get("name") or value.get("topic_name") or "")
    return ""

def _topic_has_trials_prefix(value):
    return _topic_name_from_state_value(value).strip().lower().startswith(TRIAL_TOPIC_PREFIX.lower())

def _delete_topic_result_status(res):
    if res.get("ok"):
        return "deleted"
    desc = str(res.get("description", "")).lower()
    not_found_markers = ("not found", "message thread not found", "topic not found", "topic_id_invalid")
    if any(marker in desc for marker in not_found_markers):
        return "missing"
    return "failed"

def _delete_known_topics_from_state(topics_state, should_delete):
    summary = {"deleted": 0, "missing": 0, "failed": 0, "failures": []}

    for state_key, topic_value in list(topics_state.items()):
        chat_id = _topic_state_chat_id(state_key)
        account_name = _topic_state_account_name(state_key)
        if not chat_id or not account_name or not should_delete(chat_id, account_name, topic_value):
            continue

        topic_id = _topic_id_from_state_value(topic_value)
        if topic_id is None:
            topics_state.pop(state_key, None)
            summary["missing"] += 1
            continue

        res = call_tg(
            "deleteForumTopic",
            {"chat_id": chat_id, "message_thread_id": topic_id},
        )
        status = _delete_topic_result_status(res)
        if status in ("deleted", "missing"):
            topics_state.pop(state_key, None)
            summary[status] += 1
        else:
            summary["failed"] += 1
            summary["failures"].append({
                "chat_id": chat_id,
                "topic_id": topic_id,
                "state_key": state_key,
                "error": res.get("description") or str(res),
            })

    return summary

def delete_known_topics_for_chats(chat_ids, topics_state):
    target_chat_ids = {str(chat_id) for chat_id in chat_ids if chat_id not in (None, "")}
    return _delete_known_topics_from_state(
        topics_state,
        lambda chat_id, _account_name, _topic_value: chat_id in target_chat_ids,
    )

def delete_known_topics_for_accounts(account_names, topics_state):
    target_accounts = {_normalize_account_name(name) for name in account_names if _normalize_account_name(name)}
    trial_targets = {_normalize_account_name(name) for name in account_names if _is_trials_subaccount(name)}

    def should_delete(_chat_id, account_name, topic_value):
        normalized_name = _normalize_account_name(account_name)
        if normalized_name not in target_accounts:
            return False
        if _topic_has_trials_prefix(topic_value) and normalized_name not in trial_targets:
            return False
        return True

    return _delete_known_topics_from_state(
        topics_state,
        should_delete,
    )

def _send_video_to_topic(chat_id, t_id, caption, video_path, topics_state, username, tag):
    readable_video_path = _windows_long_path(video_path)
    active_path = readable_video_path
    compressed_tmp = None

    # Si el archivo ya supera el límite, comprimir antes del primer intento
    video_size = os.path.getsize(readable_video_path)
    if video_size > TG_MAX_BYTES:
        print(f"⚠️  Video @{username} pesa {video_size/1024/1024:.1f}MB (> 49MB). Comprimiendo...")
        compressed_tmp = _compress_video_for_tg(readable_video_path, target_bytes=TG_COMPRESS_TARGET_BYTES)
        if compressed_tmp:
            active_path = compressed_tmp
        else:
            print(f"❌ No se pudo comprimir el video de @{username}. Saltando.")
            return False, t_id

    try:
        for attempt in range(5):
            payload = {'chat_id': chat_id, 'message_thread_id': t_id}
            if caption:
                payload['caption'] = caption
            with open(active_path, 'rb') as fv:
                r = requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendVideo",
                    data=payload,
                    files={'video': fv}
                )
            if r.status_code == 200:
                return True, t_id
            if r.status_code == 413:
                # El comprimido sigue siendo muy grande — intentar comprimir más agresivamente
                print(f"⚠️  Aún muy grande después de comprimir @{username}. Intentando compresión extra...")
                if compressed_tmp:
                    os.unlink(compressed_tmp)
                    compressed_tmp = None
                active_path = readable_video_path
                extra_tmp = _compress_video_for_tg(readable_video_path, target_bytes=TG_RECOMPRESS_TARGET_BYTES)
                if extra_tmp:
                    active_path = extra_tmp
                    compressed_tmp = extra_tmp
                    continue
                print(f"❌ Video de @{username} sigue excediendo el límite de Telegram (50MB). Saltando.")
                return False, t_id
            if r.status_code == 429:
                try:
                    retry_after = r.json().get("parameters", {}).get("retry_after", 15)
                except Exception:
                    retry_after = 15
                print(f"⏳ Telegram rate limit (sendVideo @{username}), esperando {retry_after}s...")
                time.sleep(retry_after + 1)
                continue
            if "thread not found" in r.text:
                print(f"⚠️ Topic expirado al enviar video @{username}, recreando...")
                t_id = get_or_create_topic(chat_id, username, tag, topics_state, force_recreate=True)
                if not t_id:
                    print(f"❌ No se pudo recrear topic para @{username}.")
                    return False, None
                continue
            print(f"❌ Error API Telegram: {r.text}")
            return False, t_id
        return False, t_id
    finally:
        if compressed_tmp and os.path.exists(compressed_tmp):
            os.unlink(compressed_tmp)

def scan_calendar_structure():
    print(f"📂 Escaneando calendario en: {input_root}")
    print(f"📄 Archivo organizadortg cargado: {__file__}")

    if not os.path.exists(input_root):
        print("❌ No existe CALENDARIO_POSTEO")
    accounts = get_accounts_with_va_info()
    account_type_map = {
        acc["username"]: acc["account_type"].strip().lower()
        for acc in accounts
    }

    all_videos = []

    for root, dirs, files in os.walk(input_root):
        rel = os.path.relpath(root, input_root)
        parts = rel.split(os.sep)

        # Esperado:
        # CALENDARIO_POSTEO/Dia_7/Thistatii/video.mp4
        if len(parts) < 2:
            continue

        dia_folder = parts[0]
        username_folder = parts[1]

        if not dia_folder.lower().startswith("dia_"):
            continue

        for f in files:
            if not f.lower().endswith((".mp4", ".mov")):
                continue

            video_path = os.path.join(root, f)

            category = account_type_map.get(username_folder)

            # Fallback por nombre de archivo
            if not category:
                if f.upper().startswith("SUICIDE__"):
                    category = "suicide"
                elif f.upper().startswith("PROMO__"):
                    category = "promo"
                else:
                    category = "unknown"

            all_videos.append({
                "path": video_path,
                "filename": f,
                "category": category,
                "day": dia_folder,
                "username": username_folder,
                "delivery_kind": "normal",
            })

    print(f"✅ Escaneo completado: {len(all_videos)} videos encontrados.")

    if len(all_videos) < 5:
        print("⚠️ Videos detectados:")
        for v in all_videos:
            print(v)

    all_videos.extend(scan_trial_calendar_structure(accounts))
    return all_videos

def scan_trial_calendar_structure(accounts):
    """Scan the isolated Trial root and reject inactive/missing accounts."""
    if not os.path.exists(trial_input_root):
        return []
    accounts_by_name = {account["username"]: account for account in accounts}
    all_videos = []
    for root, _dirs, files in os.walk(trial_input_root):
        parts = os.path.relpath(root, trial_input_root).split(os.sep)
        if len(parts) < 2 or not parts[0].lower().startswith("dia_"):
            continue
        username = parts[1]
        account = accounts_by_name.get(username)
        if not account or not account.get("trials_active"):
            continue
        for filename in files:
            if filename.lower().endswith((".mp4", ".mov")):
                all_videos.append({
                    "path": os.path.join(root, filename),
                    "filename": filename,
                    "category": account["account_type"].strip().lower(),
                    "day": parts[0],
                    "username": username,
                    "delivery_kind": "trial",
                })
    return all_videos


def _account_tag(acc_info):
    """Devuelve el tag (PROMO / SUICIDE / etc.) basado en account_type de la DB."""
    category = acc_info.get('account_type', '').strip().lower()
    if category == "promo":
        return "PROMO"
    if category == "suicide":
        return "SUICIDE"
    return category.upper() if category else "GENERAL"

def execute_telegram_plan(start_date, selected_accounts=None, controller=None, reset_topics=False):
    caption_pools = load_tanda_caption_pools()
    trial_caption_maps = load_trial_caption_maps()
    normal_individual_caption_maps = load_normal_individual_caption_maps()

    accounts = get_accounts_with_va_info()
    all_videos = scan_calendar_structure()

    if not all_videos: return "❌ No se encontraron videos en CALENDARIO_POSTEO. Revisa que las carpetas se llamen 'Dia_X'."

    topics_state = load_json(os.path.join(base_dir, STATE_FILE))
    from collections import defaultdict
    day_account_videos = defaultdict(lambda: defaultdict(list))
    for vid in all_videos: day_account_videos[vid['day']][vid['username']].append(vid)

    unique_usernames = sorted({vid['username'] for vid in all_videos})
    if reset_topics:
        target_account_names = set()
        for username in unique_usernames:
            if selected_accounts and username not in selected_accounts:
                continue
            acc_info = next((a for a in accounts if a['username'] == username), None)
            if acc_info and acc_info.get('tg_group_id'):
                target_account_names.add(username)

        if target_account_names:
            print(f"🧹 Borrando topics existentes para {len(target_account_names)} cuenta(s) seleccionadas...")
            reset_summary = delete_known_topics_for_accounts(target_account_names, topics_state)
            save_json(os.path.join(base_dir, STATE_FILE), topics_state)
            if reset_summary["failed"]:
                for failure in reset_summary["failures"]:
                    print(
                        f"❌ No se pudo borrar topic {failure['topic_id']} "
                        f"en chat {failure['chat_id']}: {failure['error']}"
                    )
                return (
                    f"❌ No se pudieron borrar {reset_summary['failed']} topics. "
                    "Revisa que el bot tenga permiso para administrar topics."
                )
            print(
                f"✅ Topics reseteados: {reset_summary['deleted']} borrados, "
                f"{reset_summary['missing']} ya no existian."
            )
        else:
            print("⚠️ Reset de topics solicitado, pero no hay cuentas Telegram seleccionadas para resetear.")

    # ── FASE 1: Pre-crear todos los topics antes de empezar a enviar ─────────
    print("🔧 Pre-creando topics de Telegram...")
    for username in unique_usernames:
        if selected_accounts and username not in selected_accounts:
            continue
        acc_info = next((a for a in accounts if a['username'] == username), None)
        if not acc_info:
            print(f"⚠️ @{username} no está en la DB — se omitirá.")
            continue
        chat_id = acc_info['tg_group_id']
        tag = _account_tag(acc_info)
        t_id = get_or_create_topic(chat_id, username, tag, topics_state)
        if t_id:
            print(f"✅ Topic listo: @{username} [{tag}] → thread {t_id}")
        else:
            print(f"❌ No se pudo crear topic para @{username} en chat {chat_id}")
    save_json(os.path.join(base_dir, STATE_FILE), topics_state)
    print(f"── Topics listos. Iniciando envíos ──\n")

    global_sent = 0
    caption_indexes = {}
    fecha_envio = start_date

    sorted_days = sorted(day_account_videos.keys(), key=lambda x: int(x.split('_')[1]))

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

                delivery_kind = vid.get("delivery_kind", "normal")
                video_topic_id = t_id if delivery_kind == "normal" else get_or_create_topic(
                    chat_id, username, tag, topics_state, delivery_kind="trial"
                )
                if not video_topic_id:
                    print(f"Topic Trial no encontrado para @{username}; se omite el video.")
                    continue

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
                msg_res = call_tg("sendMessage", {'chat_id': chat_id, 'text': meta, 'message_thread_id': video_topic_id}, silent=True)
                if not msg_res.get("ok"):
                    desc = str(msg_res.get("description", ""))
                    if "thread not found" in desc:
                        print(f"⚠️ Topic expirado para @{username}, recreando...")
                        video_topic_id = get_or_create_topic(
                            chat_id, username, tag, topics_state,
                            force_recreate=True, delivery_kind=delivery_kind,
                        )
                        save_json(os.path.join(base_dir, STATE_FILE), topics_state)
                        if not video_topic_id:
                            print(f"❌ No se pudo recrear topic para @{username} — saltando cuenta.")
                            break
                        retry_res = call_tg("sendMessage", {'chat_id': chat_id, 'text': meta, 'message_thread_id': video_topic_id})
                        if not retry_res.get("ok"):
                            print(f"❌ Falló el reintento de metadata para @{username} [{hora_et}] — saltando video.")
                            continue
                    else:
                        print(f"⚠️ Error en Telegram API (sendMessage) para @{username}: {msg_res}")

                if delivery_kind == "trial":
                    trial_map = trial_caption_maps.get(
                        extract_tanda_tag_from_calendar_filename(vid["filename"]), {}
                    )
                    cap = caption_for_trial_calendar_video(vid["filename"], trial_map)
                else:
                    normal_map = normal_individual_caption_maps.get(
                        extract_tanda_tag_from_calendar_filename(vid["filename"]), {}
                    )
                    cap = (
                        caption_for_normal_individual_video(vid["filename"], normal_map)
                        if normal_map else caption_for_calendar_video(vid['filename'], caption_pools, caption_indexes)
                    )
                try:
                    ok, video_topic_id = _send_video_to_topic(chat_id, video_topic_id, cap, vid['path'], topics_state, username, tag)
                    if ok:
                        global_sent += 1
                    if t_id:
                        save_json(os.path.join(base_dir, STATE_FILE), topics_state)
                    time.sleep(2)
                except Exception as e: print(f"❌ Error físico: {e}")

        fecha_envio += timedelta(days=1)

    save_json(os.path.join(base_dir, STATE_FILE), topics_state)
    return f"✨ PROCESO TERMINADO. Se enviaron {global_sent} videos."

# --- 4. CONTROLADOR DE HILOS Y MOTOR DE EJECUCIÓN ---
class TelegramBotController:
    def __init__(self, start_date_str, selected_accounts=None, reset_topics=False):
        self.start_date_str = start_date_str
        self.selected_accounts = selected_accounts
        self.reset_topics = reset_topics
        self._paused = threading.Event()
        self._paused.set()
        self._stopped = False
        self._running = False

    @property
    def is_paused(self): return not self._paused.is_set()
    @property
    def is_running(self): return self._running
    @property
    def stopped(self): return self._stopped
    @property
    def paused(self): return self._paused  # compatibilidad con execute_telegram_plan

    def start(self):
        self._running = True
        self._stopped = False
        try:
            start_date = datetime.strptime(self.start_date_str, "%Y-%m-%d")
            result = execute_telegram_plan(start_date, self.selected_accounts, self, reset_topics=self.reset_topics)
            print(result)
        finally:
            self._running = False

    def pause(self): self._paused.clear()
    def resume(self): self._paused.set()
    def stop(self): self._stopped = True

def preview_telegram_plan():
    all_videos = scan_calendar_structure()
    if not all_videos: return "❌ No se encontraron videos en CALENDARIO_POSTEO."
    
    from collections import defaultdict
    day_account_videos = defaultdict(lambda: defaultdict(list))
    for vid in all_videos: day_account_videos[vid['day']][vid['username']].append(vid)
    
    res = f"╔═════════════════════════════════════════════════════════════════╗\n"
    res += f"║   🚀 AUDITORÍA DE ENRUTAMIENTO TELEGRAM                         ║\n"
    res += f"╚═════════════════════════════════════════════════════════════════╝\n\n"
    
    for dia in sorted(day_account_videos.keys()):
        res += f"📅 {dia.upper()}:\n"
        for username, videos in day_account_videos[dia].items():
            res += f"  ├─ 👤 @{username[:15]:<15} | 🎬 {len(videos)} videos\n"
    return res

if __name__ == '__main__':
    print("Modo CLI desactivado. Ejecutar desde gui_unificada.py")
