import os
import subprocess
import json
import sys

# --- CONFIGURACIÓN DE RUTAS ---
# Se utiliza la ruta del archivo para evitar conflictos en VS Code
base_dir = os.path.dirname(os.path.abspath(__file__))
folder_p1 = os.path.join(base_dir, "parte1")
folder_p2_root = os.path.join(base_dir, "parte2")
folder_output_root = os.path.join(base_dir, "videos_finales")

# Parámetros técnicos IG Reel (1080x1920)
RES_W, RES_H = 1080, 1920
FPS = "30"

# Metadata Spoofing: iPhone 15 Pro @ USA
LAT, LON = "+34.0522", "-118.2437"

def ensure_structure():
    """Crea la jerarquía de carpetas de salida de forma recursiva."""
    for cat in ["promo", "suicide"]:
        path = os.path.join(folder_output_root, cat)
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"📁 Subcarpeta creada: {path}")

def get_audio(file_path):
    """Verifica la existencia de pistas de audio para evitar errores de renderizado."""
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'a', 
        '-show_entries', 'stream=codec_type', '-of', 'json', file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        return len(data.get('streams', [])) > 0
    except:
        return False

def run_render():
    ensure_structure()
    
    # Carga de fondos (Parte 1)
    if not os.path.exists(folder_p1):
        print(f"❌ ERROR: No se encuentra la carpeta {folder_p1}")
        return

    v1_list = [f for f in os.listdir(folder_p1) if f.lower().endswith(('.mp4', '.mov', '.mkv'))]
    categories = ["promo", "suicide"]

    print(f"🚀 Renderizando en i5-12th Gen (Arquitectura Alder Lake)...")

    for cat in categories:
        p2_dir = os.path.join(folder_p2_root, cat)
        out_dir = os.path.join(folder_output_root, cat)
        
        if not os.path.exists(p2_dir):
            print(f"⚠️ Saltando {cat}: No existe la carpeta de origen en parte2.")
            continue

        v2_list = [f for f in os.listdir(p2_dir) if f.lower().endswith(('.mp4', '.mov', '.mkv'))]
        cat_tag = cat.upper()

        for v1 in v1_list:
            path_v1 = os.path.join(folder_p1, v1)
            p1_id = os.path.splitext(v1)[0].replace(" ", "_")
            p1_has_audio = get_audio(path_v1)
            
            for v2 in v2_list:
                path_v2 = os.path.join(p2_dir, v2)
                p2_id = os.path.splitext(v2)[0].replace(" ", "_")
                p2_has_audio = get_audio(path_v2)
                
                # --- ESTÁNDAR DE SALIDA: CATEGORIA__P1__P2 ---
                # Este formato permite al Orquestador evitar colisiones visuales
                name_out = f"{cat_tag}__{p1_id}__{p2_id}.mp4"
                out_path = os.path.join(out_dir, name_out)

                # Lógica de audio para clips mudos
                a1_src = "[0:a]" if p1_has_audio else "[2:a]"
                a2_src = "[1:a]" if p2_has_audio else "[2:a]"
                null_audio = "anullsrc=channel_layout=stereo:sample_rate=44100"

                filter_complex = (
                    f"[0:v]scale={RES_W}:{RES_H}:force_original_aspect_ratio=increase,crop={RES_W}:{RES_H},setsar=1,fps={FPS},format=yuv420p[v0];"
                    f"[1:v]scale={RES_W}:{RES_H}:force_original_aspect_ratio=increase,crop={RES_W}:{RES_H},setsar=1,fps={FPS},format=yuv420p[v1];"
                    f"{a1_src}aresample=44100[a0]; {a2_src}aresample=44100[a1];"
                    f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]"
                )

                cmd = [
                    'ffmpeg', '-y',
                    '-hwaccel', 'cuda',               # Aceleración NVIDIA
                    '-i', path_v1,                         
                    '-i', path_v2,                         
                    '-f', 'lavfi', '-i', null_audio, 
                    '-filter_complex', filter_complex,
                    '-map', '[outv]', '-map', '[outa]',
                    '-c:v', 'h264_nvenc', '-preset', 'p4', '-cq:v', '20', '-b:v', '0', 
                    '-c:a', 'aac', '-b:a', '128k',
                    '-metadata', 'make=Apple',                   
                    '-metadata', 'model=iPhone 15 Pro',          
                    '-metadata', f'location={LAT}{LON}/',        
                    '-metadata', 'handler_name=Core Media Video',
                    '-movflags', 'faststart',                    
                    out_path
                ]

                print(f"🎬 Generando: {name_out}", end="\r")
                subprocess.run(cmd, capture_output=True)

if __name__ == "__main__":
    run_render()
    print("\n--- ✅ PROCESO COMPLETADO: VIDEOS CATEGORIZADOS Y NOMBRADOS ---")