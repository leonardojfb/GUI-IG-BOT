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
        if va_name != 'Sin Asignar':
            cur = db.conn.cursor()
            cur.execute("SELECT tg_group_id FROM virtual_assistants WHERE name = ?", (va_name,))
            row = cur.fetchone()
            if row and row['tg_group_id']: tg_group_id = row['tg_group_id']
        result.append({
            'username': acc['username'], 'account_type': acc['account_type'],
            'assigned_va': va_name, 'tg_group_id': tg_group_id
        })
    return result

def call_tg(method, data):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    try: return requests.post(url, json=data).json()
    except: return {"ok": False}

def get_or_create_topic(chat_id, acc_name, tag_emoji, state, is_admin=False):
    full_name = acc_name if is_admin else f"{acc_name} {tag_emoji}"
    state_key = f"{chat_id}_{acc_name}"
    if state_key in state: return state[state_key]
    res = call_tg("createForumTopic", {'chat_id': chat_id, 'name': full_name})
    if res.get("ok"):
        state[state_key] = res["result"]["message_thread_id"]
        return state[state_key]
    return None

def scan_calendar_structure():
    if not os.path.exists(input_root): return []
    # Corregido: .lower() para que encuentre "Dia_" o "dia_"
    carpetas_dia = sorted([d for d in os.listdir(input_root) if d.lower().startswith("dia_")])
    all_videos = []
    for dia_folder in carpetas_dia:
        dia_path = os.path.join(input_root, dia_folder)
        for username_folder in os.listdir(dia_path):
            user_path = os.path.join(dia_path, username_folder)
            if not os.path.isdir(user_path): continue
            
            category = "promo"
            if "suicide" in username_folder.lower(): category = "suicide"
            
            for f in os.listdir(user_path):
                if f.lower().endswith(('.mp4', '.mov')):
                    all_videos.append({
                        'path': os.path.join(user_path, f),
                        'filename': f, 'category': category,
                        'day': dia_folder, 'username': username_folder
                    })
    print(f"🔎 Escaneo completado: {len(all_videos)} videos encontrados.") # Log para terminal
    return all_videos

def execute_telegram_plan(start_date, selected_accounts=None, controller=None):
    accounts = get_accounts_with_va_info()
    all_videos = scan_calendar_structure()
    
    if not all_videos: return "❌ No se encontraron videos en CALENDARIO_POSTEO. Revisa que las carpetas se llamen 'Dia_X'."

    topics_state = load_json(os.path.join(base_dir, STATE_FILE))
    from collections import defaultdict
    day_account_videos = defaultdict(lambda: defaultdict(list))
    for vid in all_videos: day_account_videos[vid['day']][vid['username']].append(vid)
    
    SCHEDULE = {
        0: ["8:00 AM", "1:00 PM", "7:00 PM", "9:00 AM"], 1: ["8:00 AM", "12:00 PM", "7:00 PM", "9:00 AM"],
        2: ["9:00 AM", "1:00 PM", "9:00 PM", "10:00 AM"], 3: ["8:00 AM", "1:00 PM", "7:00 PM", "9:30 AM"],
        4: ["9:00 AM", "1:00 PM", "8:00 PM", "10:00 AM"], 5: ["11:00 AM", "3:00 PM", "8:00 PM", "12:00 PM"],
        6: ["12:00 PM", "4:00 PM", "9:00 PM", "1:00 PM"]
    }
    
    global_sent = 0
    fecha_envio = start_date
    
    # Ordenar días numéricamente para no enviar el día 10 antes que el 2
    sorted_days = sorted(day_account_videos.keys(), key=lambda x: int(x.split('_')[1]))

    for dia in sorted_days:
        dia_str = fecha_envio.strftime('%Y-%m-%d')
        tiempos = SCHEDULE[fecha_envio.weekday()]
        
        for username, videos in day_account_videos[dia].items():
            if selected_accounts and username not in selected_accounts: continue 

            acc_info = next((a for a in accounts if a['username'] == username), None)
            if not acc_info: 
                print(f"⚠️ Saltando @{username}: No está en la DB.")
                continue
            
            chat_id = acc_info['tg_group_id']
            tag = "📢 PROMO" if videos[0]['category'] == "promo" else "💀 SUICIDE"
            
            t_id = get_or_create_topic(chat_id, username, tag, topics_state)
            if not t_id: 
                print(f"❌ Error creando Topic para @{username} en chat {chat_id}")
                continue
            
            for i, vid in enumerate(videos):
                if controller and controller.stopped: return f"🛑 Abortado. Enviados: {global_sent}"
                if controller: controller.paused.wait()
                
                hora = tiempos[i % len(tiempos)]
                meta = f"{tag}\n📅 Día: {dia_str}\n⏰ Hora: {hora}\n📊 Formato: Reel"
                
                print(f"📤 Enviando a @{username} (Día {dia_str} - {hora})...")
                call_tg("sendMessage", {'chat_id': chat_id, 'text': meta, 'message_thread_id': t_id})
                
                cap = shuffle_hashtags(random.choice(captions_pool))
                try:
                    with open(vid['path'], 'rb') as fv:
                        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendVideo", 
                                      data={'chat_id': chat_id, 'caption': cap, 'message_thread_id': t_id},
                                      files={'video': fv})
                        if r.status_code == 200: global_sent += 1
                        else: print(f"❌ Error API Telegram: {r.text}")
                    time.sleep(2) # Anti-flood
                except Exception as e: print(f"❌ Error físico: {e}")
                
        fecha_envio += timedelta(days=1)
    
    save_json(os.path.join(base_dir, STATE_FILE), topics_state)
    return f"✨ PROCESO TERMINADO. Se enviaron {global_sent} videos."

# --- 4. CONTROLADOR DE HILOS Y MOTOR DE EJECUCIÓN ---
class TelegramBotController:
    def __init__(self):
        self.paused = threading.Event()
        self.paused.set() 
        self.stopped = False
    def pause(self): self.paused.clear()
    def resume(self): self.paused.set()
    def stop(self): self.stopped = True

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