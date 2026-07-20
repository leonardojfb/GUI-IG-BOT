"""Genera una plantilla LIMPIA y VACÍA de la base de datos (organizador.default.db).

Solo esquema + migraciones, sin datos. Se empaqueta en el instalador para clientes
nuevos; nunca contiene datos reales del desarrollador. `launcher.py` la copia a
`organizador.db` únicamente si el cliente aún no tiene una (ver _ensure_database),
así que jamás pisa la base de un cliente existente.

Uso:
    python make_default_db.py [ruta_destino]

Sin argumento crea ./organizador.default.db junto a este script.
"""
import os
import sys

import database

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def build_template(target: str) -> str:
    # Apuntar el DatabaseManager a la plantilla, NO a la DB real del usuario.
    database.DB_PATH = target
    if os.path.exists(target):
        os.remove(target)
    # Instanciar crea el archivo y aplica SCHEMA + migraciones no destructivas.
    manager = database.DatabaseManager()
    manager.conn.close()
    return target


if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(APP_DIR, "organizador.default.db")
    path = build_template(dest)
    print(f"Plantilla creada: {path}")
