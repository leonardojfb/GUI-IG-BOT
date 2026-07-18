import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "organizador.db")


def reset_account_history():
    if not os.path.exists(DB_PATH):
        print(f"❌ No existe la base de datos: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) FROM fingerprint_history")
        total_history = cur.fetchone()[0]

        cur.execute("DELETE FROM fingerprint_history")

        cur.execute("""
            UPDATE virtual_accounts
            SET videos_posted = 0
        """)

        conn.commit()

        print("✅ Historial de videos borrado correctamente.")
        print(f"🗑️ Registros eliminados: {total_history}")
        print("✅ Cuentas, tandas, VAs y categorías se mantuvieron intactas.")
        print("✅ videos_posted fue reseteado a 0 en todas las cuentas.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error borrando historial: {e}")

    finally:
        conn.close()


if __name__ == "__main__":
    confirm = input(
        "⚠️ Esto borrará SOLO fingerprint_history y reseteará videos_posted. Escribe YES para continuar: "
    )

    if confirm == "YES":
        reset_account_history()
    else:
        print("❌ Cancelado.")