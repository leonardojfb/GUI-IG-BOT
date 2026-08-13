import os
import subprocess
import json
import random
import re
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import DatabaseManager
from console_encoding import ensure_stdout_utf8
from render_performance import get_render_performance

ensure_stdout_utf8()

# --- CONFIGURACIÓN ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOLDER_INPUTS = os.path.join(BASE_DIR, "inputs")
FOLDER_OUTPUT_ROOT = os.path.join(BASE_DIR, "videos_finales")

RES_W, RES_H = 1080, 1920
FPS = "30"
LAT, LON = "+34.0522", "-118.2437"

# Windows: suppress the console window each ffmpeg/ffprobe child would otherwise
# pop (the GUI runs windowless). 0 on non-Windows, where the flag doesn't exist.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _ffmpeg_tool_command(tool_name):
    executable_name = f"{tool_name}.exe" if os.name == "nt" else tool_name
    bundled = Path(__file__).resolve().parent / "tools" / "ffmpeg" / "bin" / executable_name
    if bundled.is_file():
        return str(bundled)
    return tool_name


# ==================== SISTEMA DE CAPTIONS ====================
def load_captions_from_file(file_path: str) -> list:
    """Cargar captions desde archivo .txt"""
    if not os.path.exists(file_path):
        return []
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    pattern = r'\[\d{1,2}.*?\].*?:\s*(.*?)(?=\s*\[\d{1,2}|$)'
    blocks = re.findall(pattern, content, flags=re.DOTALL)
    return [b.strip() for b in blocks if b.strip()]


def process_caption_with_anti_collision(caption: str) -> str:
    """
    Algoritmo Anti-Choque de Texto:
    1. Separar texto base de hashtags
    2. Mezclar aleatoriamente el orden de los hashtags
    3. Seleccionar solo un subconjunto (70% aprox)
    4. Unir al texto base
    """
    hashtags = re.findall(r'#\w+', caption)
    if not hashtags:
        return caption
    
    text_no_hashes = re.sub(r'#\w+', '', caption).strip()
    random.shuffle(hashtags)
    num_to_keep = max(1, int(len(hashtags) * 0.7))
    selected_hashtags = hashtags[:num_to_keep]
    
    return f"{text_no_hashes}\n\n{' '.join(selected_hashtags)}"


def get_caption_for_video(tanda: dict) -> str:
    """Obtener un caption procesado para un video de la tanda"""
    captions_path = tanda.get('captions_file_path')
    
    if not captions_path or not os.path.exists(captions_path):
        return "¡Nuevo post! 🔥 #viral #trending"
    
    captions = load_captions_from_file(captions_path)
    if not captions:
        return "¡Nuevo post! 🔥 #viral #trending"
    
    base_caption = random.choice(captions)
    return process_caption_with_anti_collision(base_caption)


def get_audio(file_path):
    """Verifica si un archivo de video contiene stream de audio."""
    cmd = [
        _ffmpeg_tool_command('ffprobe'), '-v', 'error', '-select_streams', 'a',
        '-show_entries', 'stream=codec_type', '-of', 'json', file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=_NO_WINDOW)
        return len(json.loads(result.stdout).get('streams', [])) > 0
    except Exception:
        return False


def run_render():
    """Punto de entrada principal para el renderizado de videos."""
    db = DatabaseManager()

    tandas = db.get_all_tandas()

    if tandas:
        print(f"Modo Tandas: {len(tandas)} tanda(s) encontrada(s)")
        process_tandas(db, tandas)
    else:
        print("No hay Tandas activas.")

    db.close()


def process_tandas(db: DatabaseManager, tandas: list, performance=None):
    """Procesar videos usando Tandas activas haciendo un cruce total (Producto Cartesiano)."""
    performance = performance or get_render_performance()
    for tanda in tandas:
        tanda_name = tanda['tanda_name']
        p1_folder = tanda['p1_folder']
        p2_folder = tanda['p2_folder']
        
        print(f"\n📦 Procesando Tanda: {tanda_name}")
        
        p1_dir = os.path.join(FOLDER_INPUTS, p1_folder)
        p2_dir = os.path.join(FOLDER_INPUTS, p2_folder)
        out_dir = os.path.join(FOLDER_OUTPUT_ROOT, tanda_name)
        
        os.makedirs(out_dir, exist_ok=True)
        
        if not os.path.exists(p1_dir) or not os.path.exists(p2_dir):
            print(f"❌ Error: No se encuentran carpetas para tanda {tanda_name}")
            continue
        
        v1_list = [
            f for f in os.listdir(p1_dir)
            if f.lower().endswith(('.mp4', '.mov'))
        ]
        v2_list = [
            f for f in os.listdir(p2_dir)
            if f.lower().endswith(('.mp4', '.mov'))
        ]
        
        if not v1_list or not v2_list:
            print(f"⚠️ Tanda {tanda_name}: carpetas vacías")
            continue
        
        total_videos = len(v1_list) * len(v2_list)
        print(f"🔄 Modo Cruce Total: Generando {total_videos} combinaciones ({len(v1_list)} P1 x {len(v2_list)} P2)")

        # Pre-armar lista de pares pendientes (saltar ya renderizados)
        pending = []
        for v1 in v1_list:
            for v2 in v2_list:
                p1_id = os.path.splitext(v1)[0].replace(" ", "_")
                p2_id = os.path.splitext(v2)[0].replace(" ", "_")
                name_out = f"{tanda_name}__{p1_id}__{p2_id}.mp4"
                out_path = os.path.join(out_dir, name_out)
                if not os.path.exists(out_path):
                    pending.append((
                        os.path.join(p1_dir, v1),
                        os.path.join(p2_dir, v2),
                        out_path, tanda_name, p1_id, p2_id
                    ))

        if not pending:
            print("✅ Todos los videos ya están renderizados.")
            continue

        print(f"⏳ Pendientes: {len(pending)} — renderizando {performance.workers} en paralelo...")
        with ThreadPoolExecutor(max_workers=performance.workers) as pool:
            futures = {
                pool.submit(render_video_pair, *args, performance.ffmpeg_threads): args
                for args in pending
            }
            for fut in as_completed(futures):
                fut.result()  # re-lanza excepciones si las hay

def process_mix_rules(db: DatabaseManager, rules: list):
    """Procesar videos usando reglas de mezcla legacy."""
    for rule in rules:
        target_cat = rule['target_category']
        p1_dir = os.path.join(FOLDER_INPUTS, rule['p1_source'])
        p2_dir = os.path.join(FOLDER_INPUTS, rule['p2_source'])
        out_dir = os.path.join(FOLDER_OUTPUT_ROOT, target_cat)
        
        os.makedirs(out_dir, exist_ok=True)
        
        if not os.path.exists(p1_dir) or not os.path.exists(p2_dir):
            print(f"❌ Error: No se encuentran carpetas para regla {target_cat}")
            continue
        
        v1_list = [
            f for f in os.listdir(p1_dir)
            if f.lower().endswith(('.mp4', '.mov'))
        ]
        v2_list = [
            f for f in os.listdir(p2_dir)
            if f.lower().endswith(('.mp4', '.mov'))
        ]
        
        if not v1_list or not v2_list:
            continue
        
        if rule['combination_order'] == 'random':
            random.shuffle(v1_list)
            random.shuffle(v2_list)
        else:
            v1_list.sort()
            v2_list.sort()
        
        limit = rule['max_videos']
        pairs = []
        for i in range(limit):
            v1 = v1_list[i % len(v1_list)]
            v2 = v2_list[i % len(v2_list)]
            pairs.append((v1, v2))
        
        for v1, v2 in pairs:
            path_v1 = os.path.join(p1_dir, v1)
            path_v2 = os.path.join(p2_dir, v2)
            
            p1_id = os.path.splitext(v1)[0].replace(" ", "_")
            p2_id = os.path.splitext(v2)[0].replace(" ", "_")
            
            name_out = f"{target_cat}__{p1_id}__{p2_id}.mp4"
            out_path = os.path.join(out_dir, name_out)
            
            if os.path.exists(out_path):
                continue
            
            render_video_pair(path_v1, path_v2, out_path, target_cat, p1_id, p2_id)


def render_video_pair(path_v1, path_v2, out_path, cat, p1_id, p2_id, ffmpeg_threads=None):
    """
    Renderiza un par de videos concatenados usando ffmpeg.
    Intenta GPU NVIDIA primero; si falla, usa CPU (libx264) automáticamente.
    """
    p1_audio = get_audio(path_v1)
    p2_audio = get_audio(path_v2)

    a1 = "[0:a]" if p1_audio else "[2:a]"
    a2 = "[1:a]" if p2_audio else "[2:a]"

    # Si ambos videos carecen de audio, usamos asplit para no reutilizar el mismo stream.
    if not p1_audio and not p2_audio:
        audio_filter = "[2:a]asplit[a0][a1];"
    else:
        audio_filter = f"{a1}aresample=44100[a0];{a2}aresample=44100[a1];"

    filter_complex = (
        f"[0:v]scale={RES_W}:{RES_H}:force_original_aspect_ratio=increase,"
        f"crop={RES_W}:{RES_H},setsar=1,fps={FPS},format=yuv420p[v0];"
        f"[1:v]scale={RES_W}:{RES_H}:force_original_aspect_ratio=increase,"
        f"crop={RES_W}:{RES_H},setsar=1,fps={FPS},format=yuv420p[v1];"
        f"{audio_filter}"
        f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]"
    )

    name_out = os.path.basename(out_path)

    encoders = [
        ('GPU NVIDIA (h264_nvenc)', ['-hwaccel', 'cuda'], ['-c:v', 'h264_nvenc', '-preset', 'p4', '-cq:v', '20']),
        ('Intel QSV (h264_qsv)',    [],                   ['-c:v', 'h264_qsv', '-global_quality', '23']),
        ('CPU (libx264 fast)',      [],                   ['-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-threads', str(ffmpeg_threads or 4)]),
    ]

    last_stderr = ""
    for label, hw_args, codec_args in encoders:
        print(f"🎬 Renderizando con {label}: {name_out}...")

        cmd = (
            [_ffmpeg_tool_command('ffmpeg'), '-y']
            + hw_args
            + ['-i', path_v1, '-i', path_v2,
               '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
               '-filter_complex', filter_complex,
               '-map', '[outv]', '-map', '[outa]']
            + codec_args
            + ['-metadata', 'make=Apple',
               '-metadata', 'model=iPhone 15 Pro',
               '-metadata', f'location={LAT}{LON}/',
               out_path]
        )

        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=_NO_WINDOW)

        if result.returncode == 0:
            print(f"✅ Video renderizado con exito ({label})")
            return

        if os.path.exists(out_path):
            os.remove(out_path)

        last_stderr = result.stderr
        print(f"⚠️ {label} fallo, probando siguiente encoder...")

    print(f"❌ ERROR: No se pudo renderizar {name_out} con ningun encoder.")
    print(last_stderr)
    stderr = (last_stderr or "")[-1800:]
    raise RuntimeError(
        f"FFmpeg no pudo combinar '{path_v1}' y '{path_v2}' en '{out_path}': "
        f"{stderr or 'sin detalle de stderr.'}"
    )


def render_tanda(tanda_name: str, performance=None) -> str:
    """Función puente llamada desde la Interfaz Gráfica (GUI) para procesar una tanda específica."""
    db = DatabaseManager()
    
    # Buscamos la tanda por su nombre
    tandas = db.get_all_tandas()
    tanda_activa = next((t for t in tandas if t['tanda_name'] == tanda_name), None)
    
    if not tanda_activa:
        db.close()
        raise Exception(f"No se encontró la tanda '{tanda_name}' en la base de datos.")
        
    try:
        print(f"🎬 Iniciando renderizado desde GUI para la tanda: {tanda_name}")
        # Reutilizamos tu motor de procesamiento que ya funciona perfecto
        process_tandas(db, [tanda_activa], performance)
        db.close()
        return f"✅ Tanda '{tanda_name}' procesada y renderizada con éxito."
    except Exception as e:
        db.close()
        raise Exception(f"Fallo durante el procesamiento (FFMPEG/Carpetas): {str(e)}")

if __name__ == "__main__":
    run_render()
