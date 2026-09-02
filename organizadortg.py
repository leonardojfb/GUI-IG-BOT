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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calendar_manifest import load_entries, manifest_path, remove_entries_for_accounts
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


def _ffmpeg_tool_command(tool_name):
    executable_name = f"{tool_name}.exe" if os.name == "nt" else tool_name
    bundled = Path(__file__).resolve().parent / "tools" / "ffmpeg" / "bin" / executable_name
    if bundled.is_file():
        return str(bundled)
    return tool_name


def _ffmpeg_tool_exists(tool_name):
    command = _ffmpeg_tool_command(tool_name)
    return Path(command).is_file() or shutil.which(command) is not None

def _compress_video_for_tg(video_path: str, target_bytes: int = TG_COMPRESS_TARGET_BYTES) -> str | None:
    """Comprime el video con ffmpeg para que quede bajo TG_MAX_BYTES.
    Devuelve la ruta del archivo temporal comprimido, o None si falla."""
    try:
        if not _ffmpeg_tool_exists("ffmpeg") or not _ffmpeg_tool_exists("ffprobe"):
            print("⚠️  FFmpeg/FFprobe no encontrados. No se puede comprimir el video.")
            return None

        size_bytes = os.path.getsize(video_path)
        # Obtener duración con ffprobe
        probe = subprocess.run(
            [_ffmpeg_tool_command("ffprobe"), "-v", "error", "-show_entries", "format=duration",
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
        encoder_attempts = [
            ("GPU NVIDIA (h264_nvenc)", ["-vcodec", "h264_nvenc", "-preset", "p4"]),
            ("CPU (libx264)", ["-vcodec", "libx264", "-preset", "fast"]),
        ]
        last_stderr = ""

        print(f"🗜️  Comprimiendo video ({size_bytes/1024/1024:.1f}MB → objetivo <{target_bytes/1024/1024:.0f}MB, bitrate {target_kbps}kbps)...")
        for label, codec_args in encoder_attempts:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.close()
            result = subprocess.run(
                [_ffmpeg_tool_command("ffmpeg"), "-y", "-i", video_path,
                 "-b:v", f"{target_kbps}k", "-b:a", "128k"]
                + codec_args
                + ["-acodec", "aac", tmp.name],
                capture_output=True, text=True, creationflags=_NO_WINDOW
            )
            if result.returncode == 0:
                compressed_size = os.path.getsize(tmp.name)
                print(f"✅ Comprimido con {label}: {compressed_size/1024/1024:.1f}MB")
                return tmp.name
            last_stderr = result.stderr or ""
            print(f"⚠️ {label} falló, probando siguiente encoder...")
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

        print(f"❌ ffmpeg falló:\n{last_stderr[-500:]}")
        return None
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
PUBLISH_CALLBACK_DATA = "pub"

base_dir = os.path.dirname(os.path.abspath(__file__))
input_root = os.path.join(base_dir, "CALENDARIO_POSTEO")
trial_input_root = os.path.join(base_dir, "CALENDARIO_TRIALS")

db = DatabaseManager()


def _publish_button_markup(caption=None):
    buttons = [{"text": "✅ Publicado", "callback_data": PUBLISH_CALLBACK_DATA}]
    if caption:
        buttons.append({"text": "📋 Copiar caption", "copy_text": {"text": str(caption)}})
    return {"inline_keyboard": [buttons]}


def normalize_telegram_chat_id(value):
    text = str(value or "").strip()
    match = re.search(r"-?\d+", text)
    return match.group(0) if match else text


def _calendar_manifest_file():
    return manifest_path(base_dir)


def _manifest_exists():
    return os.path.exists(_calendar_manifest_file())


def _scan_manifest_calendar_structure(manifest_file=None):
    accounts = get_accounts_with_va_info()
    account_type_map = {
        acc["username"]: acc.get("account_type", "").strip().lower()
        for acc in accounts
    }
    rows = []
    for entry in load_entries(manifest_file or _calendar_manifest_file(), require_source=True):
        day_number = int(entry.get("day") or 0)
        rows.append({
            "path": entry["source_path"],
            "filename": entry["telegram_filename"],
            "category": account_type_map.get(entry["username"], entry.get("tanda") or "unknown"),
            "tanda": entry.get("tanda") or "",
            "day": f"Dia_{day_number}",
            "slot": int(entry.get("slot") or 0),
            "username": entry["username"],
            "delivery_kind": entry.get("delivery_kind", "normal"),
            "account_id": entry.get("account_id"),
            "transform_log_id": entry.get("transform_log_id"),
        })
    rows.sort(key=lambda row: (int(str(row["day"]).split("_")[1]), row.get("slot", 0), row["username"], row["filename"]))
    return rows


def _count_account_videos_in_root(account_name, calendar_root):
    total = 0
    if not os.path.isdir(calendar_root):
        return total
    for day_folder in os.listdir(calendar_root):
        if not day_folder.lower().startswith("dia_"):
            continue
        account_folder = os.path.join(calendar_root, day_folder, account_name)
        if not os.path.isdir(account_folder):
            continue
        total += sum(
            1 for filename in os.listdir(account_folder)
            if filename.lower().endswith((".mp4", ".mov"))
        )
    return total


def count_account_calendar_videos_by_kind(account_name, normal_root=None, trial_root=None):
    account_name = _safe_calendar_account_name(account_name)
    if not account_name:
        return {"normal": 0, "trial": 0}
    if normal_root is None and trial_root is None and _manifest_exists():
        counts = {"normal": 0, "trial": 0}
        for row in _scan_manifest_calendar_structure(_calendar_manifest_file()):
            if row["username"] != account_name:
                continue
            kind = row.get("delivery_kind", "normal")
            if kind in counts:
                counts[kind] += 1
        return counts
    normal_root = normal_root or input_root
    trial_root = trial_root or trial_input_root
    return {
        "normal": _count_account_videos_in_root(account_name, normal_root),
        "trial": _count_account_videos_in_root(account_name, trial_root),
    }


def count_account_calendar_videos(account_name, roots=None):
    account_name = _safe_calendar_account_name(account_name)
    if not account_name:
        return 0
    if roots is None and _manifest_exists():
        return sum(
            1 for row in _scan_manifest_calendar_structure(_calendar_manifest_file())
            if row["username"] == account_name
        )
    roots = roots or (input_root, trial_input_root)
    total = 0
    for calendar_root in roots:
        total += _count_account_videos_in_root(account_name, calendar_root)
    return total


def format_account_calendar_video_label(counts):
    normal = int(counts.get("normal", 0) or 0)
    trial = int(counts.get("trial", 0) or 0)
    total = normal + trial
    if trial and normal:
        return f"{total} videos ({normal} normales, {trial} TRIALS)"
    if trial:
        return f"{trial} videos TRIALS"
    return f"{normal} videos"


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

    if calendar_root is None and _manifest_exists():
        summary["deleted_files"] = remove_entries_for_accounts(_calendar_manifest_file(), set(targets))
        return summary

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
    path = os.fspath(path)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            backup = f"{path}.corrupt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                os.replace(path, backup)
                print(f"⚠️ Estado JSON corrupto movido a {backup}: {exc}")
            except OSError as backup_exc:
                print(f"⚠️ Estado JSON corrupto en {path}; no se pudo respaldar: {backup_exc}")
            return {}
    return {}

def save_json(path, data):
    path = os.fspath(path)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    temp_path = os.path.join(directory, f".{os.path.basename(path)}.{threading.get_ident()}.tmp")
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            f.write("\n")
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass

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
                if row['tg_group_id']: tg_group_id = normalize_telegram_chat_id(row['tg_group_id'])
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
                description = str(res.get("description", ""))
                if method == "deleteForumTopic" and "TOPIC_ID_INVALID" in description:
                    print("ℹ️ Se intento borrar un topic que ya no existe; continúo con la limpieza.")
                    return res
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
            payload = {
                'chat_id': chat_id,
                'message_thread_id': t_id,
                'disable_content_type_detection': 'true',
                'reply_markup': json.dumps(_publish_button_markup(caption), ensure_ascii=False),
            }
            if caption:
                payload['caption'] = caption
            document_name = os.path.basename(os.fspath(video_path)) or os.path.basename(os.fspath(active_path))
            with open(active_path, 'rb') as fv:
                r = requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendDocument",
                    data=payload,
                    files={'document': (document_name, fv, 'application/octet-stream')}
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
                print(f"⏳ Telegram rate limit (sendDocument @{username}), esperando {retry_after}s...")
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

    manifest_file = _calendar_manifest_file()
    if os.path.exists(manifest_file):
        all_videos = _scan_manifest_calendar_structure(manifest_file)
        print(f"Escaneo manifiesto completado: {len(all_videos)} videos encontrados.")
        return all_videos

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

def execute_telegram_plan(start_date, selected_accounts=None, controller=None, reset_topics=False, express_mode=False, db_manager=None):
    if db_manager is not None:
        global db
        previous_db = db
        db = db_manager
        try:
            return execute_telegram_plan(
                start_date,
                selected_accounts,
                controller,
                reset_topics=reset_topics,
                express_mode=express_mode,
            )
        finally:
            db = previous_db

    caption_pools = load_tanda_caption_pools()
    trial_caption_maps = load_trial_caption_maps()
    normal_individual_caption_maps = load_normal_individual_caption_maps()

    accounts = get_accounts_with_va_info()
    all_videos = scan_calendar_structure()

    if not all_videos: return "❌ No se encontraron videos en CALENDARIO_POSTEO. Revisa que las carpetas se llamen 'Dia_X'."

    topics_state = load_json(os.path.join(base_dir, STATE_FILE))
    from collections import defaultdict
    day_account_videos = defaultdict(lambda: defaultdict(list))
    account_delivery_kinds = defaultdict(set)
    for vid in all_videos:
        day_account_videos[vid['day']][vid['username']].append(vid)
        account_delivery_kinds[vid['username']].add(vid.get("delivery_kind", "normal"))

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
        for delivery_kind in sorted(account_delivery_kinds[username], key=lambda kind: kind != "normal"):
            topic_kwargs = {"delivery_kind": delivery_kind} if delivery_kind == "trial" else {}
            t_id = get_or_create_topic(chat_id, username, tag, topics_state, **topic_kwargs)
            topic_label = "TRIAL" if delivery_kind == "trial" else tag
            if t_id:
                print(f"✅ Topic listo: @{username} [{topic_label}] → thread {t_id}")
            else:
                print(f"❌ No se pudo crear topic para @{username} [{topic_label}] en chat {chat_id}")
    save_json(os.path.join(base_dir, STATE_FILE), topics_state)
    print(f"── Topics listos. Iniciando envíos ──\n")

    global_sent = 0
    caption_indexes = {}
    fecha_envio = start_date

    sorted_days = sorted(day_account_videos.keys(), key=lambda x: int(x.split('_')[1]))

    state_lock = threading.Lock()
    accounts_by_username = {account["username"]: account for account in accounts}
    jobs_by_chat = defaultdict(list)

    for dia in sorted_days:
        dia_str = fecha_envio.strftime('%Y-%m-%d')
        day_of_week = fecha_envio.weekday()

        for username, videos in day_account_videos[dia].items():
            if selected_accounts and username not in selected_accounts:
                continue

            acc_info = accounts_by_username.get(username)
            if not acc_info:
                print(f"⚠️ Saltando @{username}: No está en la DB.")
                continue

            chat_id = acc_info['tg_group_id']
            tag = _account_tag(acc_info)
            va_name = acc_info.get('assigned_va', 'Sin Asignar')
            category = (acc_info.get('account_type') or 'general').strip().lower()
            va_tz = acc_info.get('va_timezone', 'America/Argentina/Buenos_Aires')
            tiempos = get_slots_for_set(va_name, category, day_of_week, db)

            has_normal_videos = any(vid.get("delivery_kind", "normal") == "normal" for vid in videos)
            t_id = get_or_create_topic(chat_id, username, tag, topics_state) if has_normal_videos else None
            if has_normal_videos and not t_id:
                print(f"❌ Topic no encontrado para @{username} — saltando.")
                continue

            for i, vid in enumerate(videos):
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

                jobs_by_chat[chat_id].append({
                    "chat_id": chat_id,
                    "username": username,
                    "tag": tag,
                    "delivery_kind": delivery_kind,
                    "topic_id": video_topic_id,
                    "caption": cap,
                    "path": vid["path"],
                    "meta": meta,
                    "hora_et": hora_et,
                    "dia_str": dia_str,
                })

        fecha_envio += timedelta(days=1)

    def send_metadata(job):
        if express_mode:
            return job["topic_id"]
        msg_res = call_tg("sendMessage", {
            'chat_id': job["chat_id"],
            'text': job["meta"],
            'message_thread_id': job["topic_id"],
        }, silent=True)
        if msg_res.get("ok"):
            return job["topic_id"]
        desc = str(msg_res.get("description", ""))
        if "thread not found" not in desc:
            print(f"⚠️ Error en Telegram API (sendMessage) para @{job['username']}: {msg_res}")
            return job["topic_id"]
        print(f"⚠️ Topic expirado para @{job['username']}, recreando...")
        with state_lock:
            topic_id = get_or_create_topic(
                job["chat_id"], job["username"], job["tag"], topics_state,
                force_recreate=True, delivery_kind=job["delivery_kind"],
            )
            save_json(os.path.join(base_dir, STATE_FILE), topics_state)
        if not topic_id:
            print(f"❌ No se pudo recrear topic para @{job['username']} — saltando cuenta.")
            return None
        retry_res = call_tg("sendMessage", {
            'chat_id': job["chat_id"],
            'text': job["meta"],
            'message_thread_id': topic_id,
        })
        if not retry_res.get("ok"):
            print(f"❌ Falló el reintento de metadata para @{job['username']} [{job['hora_et']}] — saltando video.")
            return None
        return topic_id

    def send_chat_jobs(jobs):
        sent = 0
        aborted = False
        for job in jobs:
            if controller and controller.stopped:
                aborted = True
                break
            if controller:
                controller.paused.wait()
            print(f"📤 Enviando a @{job['username']} [{job['tag']}] (Día {job['dia_str']} - {job['hora_et']} ET)...")
            try:
                topic_id = send_metadata(job)
                if not topic_id:
                    continue
                ok, _topic_id = _send_video_to_topic(
                    job["chat_id"], topic_id, job["caption"], job["path"],
                    topics_state, job["username"], job["tag"],
                )
                if ok:
                    sent += 1
                with state_lock:
                    save_json(os.path.join(base_dir, STATE_FILE), topics_state)
                time.sleep(2)
            except Exception as e:
                print(f"❌ Error físico: {e}")
        return sent, aborted

    if jobs_by_chat:
        print(f"⚡ Envío paralelo por grupo activo: {len(jobs_by_chat)} grupo(s).")
        with ThreadPoolExecutor(max_workers=len(jobs_by_chat)) as pool:
            futures = [pool.submit(send_chat_jobs, jobs) for jobs in jobs_by_chat.values()]
            for future in futures:
                sent, aborted = future.result()
                global_sent += sent
                if aborted:
                    save_json(os.path.join(base_dir, STATE_FILE), topics_state)
                    return f"🛑 Abortado. Enviados: {global_sent}"

    save_json(os.path.join(base_dir, STATE_FILE), topics_state)
    return f"✨ PROCESO TERMINADO. Se enviaron {global_sent} videos."

# --- 4. CONTROLADOR DE HILOS Y MOTOR DE EJECUCIÓN ---
class TelegramBotController:
    def __init__(self, start_date_str, selected_accounts=None, reset_topics=False, express_mode=False, db_manager=None):
        self.start_date_str = start_date_str
        self.selected_accounts = selected_accounts
        self.reset_topics = reset_topics
        self.express_mode = express_mode
        self.db_manager = db_manager
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
            execute_kwargs = {
                "reset_topics": self.reset_topics,
                "express_mode": self.express_mode,
            }
            if self.db_manager is not None:
                execute_kwargs["db_manager"] = self.db_manager
            result = execute_telegram_plan(
                start_date,
                self.selected_accounts,
                self,
                **execute_kwargs,
            )
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
