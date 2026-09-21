"""Optional user-owned workflow profiles, separate from immutable queue steps."""
from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from workflow_manual_steps import SUBTYPES


def ensure_profile_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS workflow_profiles (
            profile_id TEXT PRIMARY KEY,
            module_type TEXT NOT NULL,
            subtype TEXT NOT NULL,
            name TEXT NOT NULL,
            recipe_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (module_type, subtype, name)
        )"""
    )
    connection.commit()


def _scope(module_type: str, subtype: str) -> tuple[str, str]:
    module = str(module_type or "").strip().lower()
    variant = str(subtype or "").strip().lower()
    if module not in SUBTYPES:
        raise ValueError(f"modulo desconocido: {module or 'vacio'}")
    if variant not in SUBTYPES[module]:
        raise ValueError(f"subtipo invalido para {module}: {variant or 'vacio'}")
    return module, variant


def _decode(row: sqlite3.Row | tuple) -> dict[str, Any]:
    return {
        "profile_id": row[0],
        "module_type": row[1],
        "subtype": row[2],
        "name": row[3],
        "recipe": json.loads(row[4]),
        "created_at": row[5],
        "updated_at": row[6],
    }


def list_profiles(connection: sqlite3.Connection, module_type: str | None = None, subtype: str | None = None) -> list[dict[str, Any]]:
    ensure_profile_schema(connection)
    if module_type is None and subtype is None:
        rows = connection.execute(
            "SELECT profile_id, module_type, subtype, name, recipe_json, created_at, updated_at FROM workflow_profiles ORDER BY module_type, subtype, name"
        ).fetchall()
    else:
        module, variant = _scope(module_type, subtype)
        rows = connection.execute(
            "SELECT profile_id, module_type, subtype, name, recipe_json, created_at, updated_at FROM workflow_profiles WHERE module_type=? AND subtype=? ORDER BY name",
            (module, variant),
        ).fetchall()
    return [_decode(row) for row in rows]


def save_profile(connection: sqlite3.Connection, module_type: str, subtype: str, name: str, recipe: dict[str, Any]) -> dict[str, Any]:
    module, variant = _scope(module_type, subtype)
    title = str(name or "").strip()
    if not title:
        raise ValueError("el nombre del perfil es obligatorio")
    if not isinstance(recipe, dict) or not recipe:
        raise ValueError("recipe debe ser un objeto no vacio")
    ensure_profile_schema(connection)
    profile_id = f"profile-{uuid.uuid4().hex}"
    encoded = json.dumps(recipe, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    try:
        connection.execute(
            "INSERT INTO workflow_profiles(profile_id, module_type, subtype, name, recipe_json) VALUES (?, ?, ?, ?, ?)",
            (profile_id, module, variant, title, encoded),
        )
        connection.commit()
    except sqlite3.IntegrityError as exc:
        connection.rollback()
        raise ValueError(f"ya existe un perfil llamado '{title}' para {module}/{variant}") from exc
    return get_profile(connection, profile_id)


def get_profile(connection: sqlite3.Connection, profile_id: str) -> dict[str, Any]:
    ensure_profile_schema(connection)
    row = connection.execute(
        "SELECT profile_id, module_type, subtype, name, recipe_json, created_at, updated_at FROM workflow_profiles WHERE profile_id=?",
        (str(profile_id or ""),),
    ).fetchone()
    if row is None:
        raise KeyError(f"perfil desconocido: {profile_id}")
    return _decode(row)


def delete_profile(connection: sqlite3.Connection, profile_id: str) -> dict[str, Any]:
    profile = get_profile(connection, profile_id)
    connection.execute("DELETE FROM workflow_profiles WHERE profile_id=?", (profile["profile_id"],))
    connection.commit()
    return profile
