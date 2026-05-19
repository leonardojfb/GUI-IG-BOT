import os
import threading
import requests
import time
import json
import random
import re
from datetime import datetime, timedelta
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import DatabaseManager

# --- 1. CONFIGURACIÓN Y CREDENCIALES ---
TOKEN = "8787705820:AAGIeKGzhxHZgUmbbH9G9EgK5Y7M11J-MWM"
DEFAULT_CHAT_ID = "-1003749971714"
STATE_FILE = "telegram_state_v11.json"
HISTORY_FILE = "fingerprint_history.json"
ADMIN_TOPIC_NAME = "Admin"

base_dir = os.path.dirname(os.path.abspath(__file__))
input_root = os.path.join(base_dir, "CALENDARIO_POSTEO")

db = DatabaseManager()

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

def load_clean_captions():
    path = os.path.join(base_dir, "captions.txt")
    if not os.path.exists(path): return ["¡Nuevo post de Tatiana! 🔥"]
    content = open(path, 'r', encoding='utf-8', errors='ignore').read()
    pattern = r'\[\d{1,2}.*?\].*?:\s*(.*?)(?=\s*\[\d{1,2}|$)'
    blocks = re.findall(pattern, content, flags=re.DOTALL)
    return [b.strip() for b in blocks if b.strip()]

def shuffle_hashtags(text):
    hashtags = re.findall(r'#\w+', text)
    if not hashtags: return text
    text_no_hashes = re.sub(r'#\w+', '', text).strip()
    random.shuffle(hashtags)
    return f"{text_no_hashes}\n\n{' '.join(hashtags)}"

captions_pool = load_clean_captions()
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
            'assigned_va': va_name, 'tg_group_id': tg_group_id,
            'va_timezone': va_timezone,
        })
    return result

def call_tg(method, data, silent=False):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    try:
        res = requests.post(url, json=data).json()
        if not res.get("ok") and not silent:
            print(f"⚠️ Error en Telegram API ({method}): {res}")
        return res
    except Exception as e:
        print(f"⚠️ Error de red al llamar a {method}: {e}")
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
def get_or_create_topic(chat_id, acc_name, tag_emoji, state, is_admin=False, force_recreate=False):
    full_name = acc_name if is_admin else f"{acc_name} {tag_emoji}"
    state_key = f"{chat_id}_{acc_name}"
    if state_key in state and not force_recreate: return state[state_key]
    if force_recreate: state.pop(state_key, None)
    res = call_tg("createForumTopic", {'chat_id': chat_id, 'name': full_name})
    if res.get("ok"):
        state[state_key] = res["result"]["message_thread_id"]
        return state[state_key]
    return None

def _send_video_to_topic(chat_id, t_id, caption, video_path, topics_state, username, tag):
    for attempt in range(2):
        with open(video_path, 'rb') as fv:
            r = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendVideo",
                data={'chat_id': chat_id, 'caption': caption, 'message_thread_id': t_id},
                files={'video': fv}
            )
        if r.status_code == 200:
            return True, t_id
        if attempt == 0 and "thread not found" in r.text:
            print(f"⚠️ Topic expirado al enviar video @{username}, recreando...")
            t_id = get_or_create_topic(chat_id, username, tag, topics_state, force_recreate=True)
            if not t_id:
                print(f"❌ No se pudo recrear topic para @{username}.")
                return False, None
        else:
            print(f"❌ Error API Telegram: {r.text}")
            return False, t_id
    return False, t_id

def scan_calendar_structure():
    print(f"📂 Escaneando calendario en: {input_root}")
    print(f"📄 Archivo organizadortg cargado: {__file__}")

    if not os.path.exists(input_root):
        print("❌ No existe CALENDARIO_POSTEO")
        return []

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
                "username": username_folder
            })

    print(f"✅ Escaneo completado: {len(all_videos)} videos encontrados.")

    if len(all_videos) < 5:
        print("⚠️ Videos detectados:")
        for v in all_videos:
            print(v)

    return all_videos

def _account_tag(acc_info):
    """Devuelve el tag (PROMO / SUICIDE / etc.) basado en account_type de la DB."""
    category = acc_info.get('account_type', '').strip().lower()
    if category == "promo":
        return "PROMO"
    if category == "suicide":
        return "SUICIDE"
    return category.upper() if category else "GENERAL"

def execute_telegram_plan(start_date, selected_accounts=None, controller=None):
    accounts = get_accounts_with_va_info()
    all_videos = scan_calendar_structure()

    if not all_videos: return "❌ No se encontraron videos en CALENDARIO_POSTEO. Revisa que las carpetas se llamen 'Dia_X'."

    topics_state = load_json(os.path.join(base_dir, STATE_FILE))
    from collections import defaultdict
    day_account_videos = defaultdict(lambda: defaultdict(list))
    for vid in all_videos: day_account_videos[vid['day']][vid['username']].append(vid)

    # ── FASE 1: Pre-crear todos los topics antes de empezar a enviar ─────────
    print("🔧 Pre-creando topics de Telegram...")
    unique_usernames = sorted({vid['username'] for vid in all_videos})
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

    save_json(os.path.join(base_dir, STATE_FILE), topics_state)
    return f"✨ PROCESO TERMINADO. Se enviaron {global_sent} videos."

# --- 4. CONTROLADOR DE HILOS Y MOTOR DE EJECUCIÓN ---
class TelegramBotController:
    def __init__(self, start_date_str, selected_accounts=None):
        self.start_date_str = start_date_str
        self.selected_accounts = selected_accounts
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
            result = execute_telegram_plan(start_date, self.selected_accounts, self)
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