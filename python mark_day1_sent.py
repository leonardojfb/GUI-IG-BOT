import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "organizador.db")

DAY_TO_MARK = 1


def ensure_sent_column(cur):
    cur.execute("PRAGMA table_info(fingerprint_history)")
    columns = [row[1] for row in cur.fetchall()]

    if "telegram_status" not in columns:
        cur.execute("""
            ALTER TABLE fingerprint_history
            ADD COLUMN telegram_status TEXT DEFAULT 'pending'
        """)


def mark_day_as_sent():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        ensure_sent_column(cur)

        cur.execute("""
            UPDATE fingerprint_history
            SET telegram_status = 'sent'
            WHERE video_path LIKE ?
        """, (f"%Dia_{DAY_TO_MARK}%",))

        affected = cur.rowcount
        conn.commit()

        print(f"✅ Día {DAY_TO_MARK} marcado como enviado.")
        print(f"✅ Videos marcados: {affected}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")

    finally:
        conn.close()


if __name__ == "__main__":
    confirm = input(
        f"⚠️ Esto marcará como SENT todos los videos del Día {DAY_TO_MARK}. Escribe YES para continuar: "
    )

    if confirm == "YES":
        mark_day_as_sent()
    else:
        print("Cancelado.")