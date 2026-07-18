import os
import random
import shutil
import sqlite3
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CALENDAR_ROOT = os.path.join(BASE_DIR, "CALENDARIO_POSTEO")
DB_PATH = os.path.join(BASE_DIR, "organizador.db")
TEMP_DIR = os.path.join(BASE_DIR, "_RESHUFFLE_TEMP")

VIDEO_EXTS = (".mp4", ".mov")


def parse_p1(filename):
    name = os.path.splitext(filename)[0]
    parts = name.split("__")
    if len(parts) >= 3:
        return parts[1]
    return None


def day_number(day_folder):
    return int(day_folder.split("_")[1])


def scan_slots():
    slots = []
    videos = []

    for day_folder in sorted(os.listdir(CALENDAR_ROOT), key=lambda x: day_number(x) if x.lower().startswith("dia_") else 9999):
        if not day_folder.lower().startswith("dia_"):
            continue

        day_num = day_number(day_folder)

        # NO tocar Dia_1
        if day_num == 1:
            continue

        day_path = os.path.join(CALENDAR_ROOT, day_folder)

        if not os.path.isdir(day_path):
            continue

        for account in os.listdir(day_path):
            account_path = os.path.join(day_path, account)

            if not os.path.isdir(account_path):
                continue

            files = [
                f for f in os.listdir(account_path)
                if f.lower().endswith(VIDEO_EXTS)
            ]

            # Cada archivo existente representa un slot que hay que rellenar
            for idx, f in enumerate(files, start=1):
                old_path = os.path.join(account_path, f)

                slots.append({
                    "day_folder": day_folder,
                    "day_num": day_num,
                    "account": account,
                    "account_path": account_path,
                    "slot": idx,
                })

                videos.append({
                    "filename": f,
                    "old_path": old_path,
                    "p1": parse_p1(f),
                })

    return slots, videos


def pick_video(videos_pool, used_p1_account_day, used_p1_slot):
    random.shuffle(videos_pool)

    # Nivel 1: ideal, no repite PT1 en cuenta/día ni en slot global
    for v in videos_pool:
        p1 = v["p1"]

        if not p1:
            continue

        if p1 in used_p1_account_day:
            continue

        if p1 in used_p1_slot:
            continue

        return v

    # Nivel 2: permite choque en slot, pero NO repite PT1 en cuenta/día
    for v in videos_pool:
        p1 = v["p1"]

        if not p1:
            continue

        if p1 in used_p1_account_day:
            continue

        return v

    return None


def update_db_paths(path_map):
    if not os.path.exists(DB_PATH):
        print("⚠️ No existe organizador.db, se saltó actualización DB.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    updated = 0

    try:
        for old_path, new_path in path_map.items():
            cur.execute("""
                UPDATE fingerprint_history
                SET video_path = ?
                WHERE video_path = ?
            """, (new_path, old_path))

            updated += cur.rowcount

        conn.commit()
        print(f"✅ DB actualizada. Rutas modificadas: {updated}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error actualizando DB: {e}")

    finally:
        conn.close()


def reshuffle():
    slots, videos = scan_slots()

    if not slots or not videos:
        print("❌ No hay videos/slots para reordenar desde Dia_2 en adelante.")
        return

    print(f"🎲 Slots detectados: {len(slots)}")
    print(f"🎬 Videos detectados: {len(videos)}")
    print("🔒 Dia_1 queda intacto.")

    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)

    os.makedirs(TEMP_DIR, exist_ok=True)

    # Mover todos los videos Dia_2+ a temp
    temp_videos = []

    for i, v in enumerate(videos):
        ext = os.path.splitext(v["filename"])[1]
        temp_name = f"temp_{i}{ext}"
        temp_path = os.path.join(TEMP_DIR, temp_name)

        shutil.move(v["old_path"], temp_path)

        temp_videos.append({
            **v,
            "temp_path": temp_path,
        })

    videos_pool = temp_videos[:]
    random.shuffle(videos_pool)

    used_p1_by_account_day = defaultdict(set)
    used_p1_by_day_slot = defaultdict(set)
    path_map = {}

    # Ordenar por día/slot, pero randomizar cuentas dentro de cada slot
    grouped_slots = defaultdict(list)

    for s in slots:
        grouped_slots[(s["day_num"], s["slot"])].append(s)

    for key in sorted(grouped_slots.keys()):
        day_num, slot_num = key
        slot_group = grouped_slots[key]
        random.shuffle(slot_group)

        for s in slot_group:
            account_day_key = (s["account"], day_num)
            day_slot_key = (day_num, slot_num)

            chosen = pick_video(
                videos_pool,
                used_p1_by_account_day[account_day_key],
                used_p1_by_day_slot[day_slot_key]
            )

            if not chosen:
                print(f"⚠️ No hay video válido para {s['account']} / Dia_{day_num} / Slot {slot_num}")
                continue

            videos_pool.remove(chosen)

            old_path = chosen["old_path"]
            new_path = os.path.join(s["account_path"], chosen["filename"])

            # Evitar overwrite si casualmente ya existe algo
            if os.path.exists(new_path):
                base, ext = os.path.splitext(chosen["filename"])
                new_path = os.path.join(
                    s["account_path"],
                    f"{base}__RESHUFFLED_D{day_num}_S{slot_num}{ext}"
                )

            shutil.move(chosen["temp_path"], new_path)

            used_p1_by_account_day[account_day_key].add(chosen["p1"])
            used_p1_by_day_slot[day_slot_key].add(chosen["p1"])

            path_map[old_path] = new_path

    # Si queda algún video sin colocar, devolverlo a una carpeta de revisión
    leftovers_dir = os.path.join(BASE_DIR, "_RESHUFFLE_LEFTOVERS")
    os.makedirs(leftovers_dir, exist_ok=True)

    for v in videos_pool:
        if os.path.exists(v["temp_path"]):
            shutil.move(v["temp_path"], os.path.join(leftovers_dir, v["filename"]))

    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)

    update_db_paths(path_map)

    print("✅ Shuffle terminado.")
    print("✅ Dia_1 no fue tocado.")
    print("✅ Regla respetada: no repetir PT1 en la misma cuenta el mismo día.")
    print("✅ Se intentó reducir choques de PT1 en el mismo slot entre cuentas.")

    if videos_pool:
        print(f"⚠️ Videos sin recolocar: {len(videos_pool)}. Revisa _RESHUFFLE_LEFTOVERS")


if __name__ == "__main__":
    confirm = input("⚠️ Esto reordenará Dia_2 en adelante. Dia_1 queda intacto. Escribe YES: ")

    if confirm == "YES":
        reshuffle()
    else:
        print("Cancelado.")