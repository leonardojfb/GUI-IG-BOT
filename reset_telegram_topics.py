import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "organizador.db")


def reset_telegram_topics():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]

        print("📋 Tablas detectadas:", tables)

        possible_tables = [
            "telegram_topics",
            "telegram_threads",
            "topic_mapping",
            "account_topics",
            "telegram_accounts"
        ]

        deleted_any = False

        for table in possible_tables:
            if table in tables:
                cur.execute(f"DELETE FROM {table}")
                print(f"🗑️ Tabla limpiada: {table}")
                deleted_any = True

        # También buscar columnas sospechosas en otras tablas
        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cur.fetchall()]

            reset_cols = [
                c for c in columns
                if "thread" in c.lower()
                or "topic" in c.lower()
                or "message_thread" in c.lower()
            ]

            for col in reset_cols:
                cur.execute(f"UPDATE {table} SET {col} = NULL")
                print(f"♻️ Columna reseteada: {table}.{col}")
                deleted_any = True

        conn.commit()

        if deleted_any:
            print("✅ Topics/thread IDs reseteados.")
            print("✅ Ahora el bot debería crear topics nuevos.")
        else:
            print("⚠️ No encontré tablas/columnas de topics. Puede que estén en un JSON/cache.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")

    finally:
        conn.close()


if __name__ == "__main__":
    confirm = input("⚠️ Esto borrará/reseteará IDs de topics Telegram guardados. Escribe YES: ")

    if confirm.strip().upper() == "YES":
        reset_telegram_topics()
    else:
        print("Cancelado.")