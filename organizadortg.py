import os
import requests
import time
import json
import random
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y CREDENCIALES ---
TOKEN = "8787705820:AAGIeKGzhxHZgUmbbH9G9EgK5Y7M11J-MWM"
CHAT_ID = "-1003749971714" 
STATE_FILE = "telegram_state_v11.json"
HISTORY_FILE = "fingerprint_history.json" # La "memoria" del sistema
ADMIN_TOPIC_NAME = "Admin"

base_dir = os.path.dirname(os.path.abspath(__file__))
input_root = os.path.join(base_dir, "CALENDARIO_POSTEO")

# --- 2. GESTIÓN DE PERSISTENCIA (Fingerprint) ---
def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

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

# --- 3. FUNCIONES DE TELEGRAM ---
def call_tg(method, data):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    try: return requests.post(url, json=data).json()
    except: return {"ok": False}

def get_or_create_topic(acc_name, tag_emoji, state, is_admin=False):
    full_name = acc_name if is_admin else f"{acc_name} {tag_emoji}"
    if acc_name in state: return state[acc_name]
    res = call_tg("createForumTopic", {'chat_id': CHAT_ID, 'name': full_name})
    if res.get("ok"):
        state[acc_name] = res["result"]["message_thread_id"]
        return state[acc_name]
    return None

# --- 4. SELECTOR CON FILTRO HISTÓRICO Y UNICIDAD DIARIA ---
def pick_smart_batch(pool, count, acc_name, history):
    """
    1. Filtra videos que la cuenta YA subió (Fingerprint).
    2. Asegura que en los 4 de hoy no se repita P1 ni P2.
    """
    if acc_name not in history:
        history[acc_name] = []
        
    # Filtrar pool global para esta cuenta específica
    eligible_videos = [v for v in pool if v['path'] not in history[acc_name]]
    
    batch = []
    used_p1, used_p2 = set(), set()
    random.shuffle(eligible_videos) # Variación en cada corrida
    
    for video in eligible_videos:
        if len(batch) >= count: break
        
        # Validación de partes para el lote de hoy
        if video['p1'] not in used_p1 and video['p2'] not in used_p2:
            batch.append(video)
            used_p1.add(video['p1'])
            used_p2.add(video['p2'])
            # Marcar como subido en esta cuenta
            history[acc_name].append(video['path'])
            
    return batch

# --- 5. EJECUCIÓN MAESTRA (i5-11th Gen Optimizado) ---
print(f"🚀 EJECUTANDO OMNIBOT V11: MODO PERSISTENCIA TOTAL...")

topics_state = load_json(os.path.join(base_dir, STATE_FILE))

SCHEDULE = {
    0: ["8:00 AM", "1:00 PM", "7:00 PM", "9:00 AM"], 1: ["8:00 AM", "12:00 PM", "7:00 PM", "9:00 AM"],
    2: ["9:00 AM", "1:00 PM", "9:00 PM", "10:00 AM"], 3: ["8:00 AM", "1:00 PM", "7:00 PM", "9:30 AM"],
    4: ["9:00 AM", "1:00 PM", "8:00 PM", "10:00 AM"], 5: ["11:00 AM", "3:00 PM", "8:00 PM", "12:00 PM"],
    6: ["12:00 PM", "4:00 PM", "9:00 PM", "1:00 PM"]
}

fecha_envio = datetime(2026, 4, 21) 
carpetas_dia = sorted([d for d in os.listdir(input_root) if d.lower().startswith("dia_")])

# Escaneo de Stock Global
global_pool_promo, global_pool_suicide = [], []
for d_folder in carpetas_dia:
    def scan(cat):
        p = os.path.join(input_root, d_folder, cat)
        res = []
        if os.path.exists(p):
            for f in os.listdir(p):
                if f.lower().endswith(('.mp4', '.mov')):
                    parts = f.replace(".mp4", "").split("__")
                    if len(parts) >= 3:
                        res.append({'path': os.path.join(p, f), 'p1': parts[1], 'p2': parts[2]})
        return res
    global_pool_promo += scan("promo")
    global_pool_suicide += scan("suicide")

global_sent = 0

for dia_folder in carpetas_dia:
    dia_str = fecha_envio.strftime('%d/%m/%y')
    tiempos = SCHEDULE[fecha_envio.weekday()]
    
    for tag, file_acc, pool in [("📢 PROMO", "accounts_promo.txt", global_pool_promo), 
                                 ("💀 SUICIDE", "accounts_suicide.txt", global_pool_suicide)]:
        
        acc_list = [l.strip() for l in open(os.path.join(base_dir, file_acc), 'r', encoding='utf-8') if l.strip()]
        
        for acc in acc_list:
            t_id = get_or_create_topic(acc, tag, topics_state)
            if not t_id: continue

            # Selección inteligente basada en el historial de ESTA cuenta
            lote = pick_smart_batch(pool, 4, acc, history_db)
            
            for i, vid in enumerate(lote):
                hora = tiempos[i]
                formato = "Reel" if i < 3 else "Story"
                
                # Mensaje 1: Detalles técnicos
                meta = f"{tag}\n📅 Día: {dia_str}\n⏰ Hora: {hora}\n📊 Formato: {formato}"
                call_tg("sendMessage", {'chat_id': CHAT_ID, 'text': meta, 'message_thread_id': t_id})
                
                # Mensaje 2: Video + Caption Único
                cap = shuffle_hashtags(random.choice(captions_pool))
                with open(vid['path'], 'rb') as fv:
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendVideo", 
                                  data={'chat_id': CHAT_ID, 'caption': cap, 'message_thread_id': t_id},
                                  files={'video': fv})
                global_sent += 1
                time.sleep(1.2)

    fecha_envio += timedelta(days=1)

# --- 6. GUARDAR ESTADO Y REPORTAR ---
save_json(os.path.join(base_dir, HISTORY_FILE), history_db)
save_json(os.path.join(base_dir, STATE_FILE), topics_state)

admin_id = get_or_create_topic(ADMIN_TOPIC_NAME, "", topics_state, is_admin=True)
if admin_id:
    resumen = (f"📋 *REPORTE V11: FINGERPRINT ACTIVO*\n---\n"
               f"✅ Enviados en esta corrida: {global_sent}\n"
               f"💾 Cuentas rastreadas: {len(history_db)}\n"
               f"🔄 Las variaciones son únicas por cuenta.")
    call_tg("sendMessage", {'chat_id': CHAT_ID, 'text': resumen, 'message_thread_id': admin_id, 'parse_mode': 'Markdown'})

print(f"✨ PROCESO TERMINADO. Fingerprint actualizado para {len(history_db)} cuentas.")