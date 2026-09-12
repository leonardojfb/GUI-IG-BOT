from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def hash_file(path: str | os.PathLike) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_type_for_path(path: str | os.PathLike) -> str:
    ext = Path(path).suffix.lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in IMAGE_EXTS:
        return "image"
    return "file"


class VaultStorage:
    def __init__(self, db, vault_root: str | os.PathLike):
        self.db = db
        self.vault_root = Path(vault_root)

    @property
    def conn(self):
        return self.db.conn

    def import_managed(self, source_path: str | os.PathLike) -> dict[str, Any]:
        source = Path(source_path)
        if not source.is_file():
            raise FileNotFoundError(str(source))
        before_hash = hash_file(source)
        size_bytes = source.stat().st_size
        destination = self._managed_path(before_hash, source.name)
        destination.parent.mkdir(parents=True, exist_ok=True)

        temp_name = ""
        if not destination.exists():
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=str(destination.parent),
            )
            os.close(fd)
            try:
                shutil.copyfile(source, temp_name)
                after_hash = hash_file(source)
                temp_hash = hash_file(temp_name)
                if before_hash != after_hash or temp_hash != before_hash:
                    raise ValueError("El archivo cambio durante la copia")
                os.replace(temp_name, destination)
            finally:
                if temp_name and os.path.exists(temp_name):
                    os.unlink(temp_name)
        else:
            if hash_file(destination) != before_hash:
                raise ValueError("El archivo gestionado existente no coincide con su hash")

        asset_id = self._upsert_asset(before_hash, media_type_for_path(source), size_bytes, source.name)
        location_id = self._upsert_location(asset_id, destination, managed=True, status="ok")
        return self._result(asset_id, location_id, destination, before_hash, managed=True)

    def register_external(self, source_path: str | os.PathLike) -> dict[str, Any]:
        source = Path(source_path)
        if not source.is_file():
            raise FileNotFoundError(str(source))
        sha256 = hash_file(source)
        asset_id = self._upsert_asset(sha256, media_type_for_path(source), source.stat().st_size, source.name)
        location_id = self._upsert_location(asset_id, source, managed=False, status="ok")
        return self._result(asset_id, location_id, source, sha256, managed=False)

    def verify_location(self, location_id: int) -> dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT l.*, a.sha256
            FROM vault_locations l
            JOIN vault_assets a ON a.id = l.asset_id
            WHERE l.id = ?
            """,
            (int(location_id),),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Ubicacion Vault no encontrada: {location_id}")
        path = Path(row["path"])
        if not path.exists():
            status = "missing"
            actual_hash = ""
        else:
            actual_hash = hash_file(path)
            status = "ok" if actual_hash == row["sha256"] else "hash_mismatch"
        cur.execute(
            """
            UPDATE vault_locations
            SET status = ?, last_verified_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, int(location_id)),
        )
        self.conn.commit()
        return {
            "location_id": int(location_id),
            "asset_id": row["asset_id"],
            "path": row["path"],
            "managed": bool(row["managed"]),
            "status": status,
            "sha256": row["sha256"],
            "actual_sha256": actual_hash,
        }

    def locations_for_asset(self, asset_id: int) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM vault_locations WHERE asset_id = ? ORDER BY managed DESC, id",
            (int(asset_id),),
        )
        return [dict(row) for row in cur.fetchall()]

    def list_assets(self) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM vault_assets ORDER BY id")
        return [dict(row) for row in cur.fetchall()]

    def _managed_path(self, sha256: str, original_name: str) -> Path:
        suffix = Path(original_name).suffix.lower()
        return self.vault_root / sha256[:2] / sha256[2:4] / f"{sha256}{suffix}"

    def _upsert_asset(self, sha256: str, media_type: str, size_bytes: int, display_name: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO vault_assets (sha256, media_type, size_bytes, display_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(sha256) DO UPDATE SET
                media_type = excluded.media_type,
                size_bytes = excluded.size_bytes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (sha256, media_type, int(size_bytes), display_name),
        )
        self.conn.commit()
        cur.execute("SELECT id FROM vault_assets WHERE sha256 = ?", (sha256,))
        return int(cur.fetchone()["id"])

    def _upsert_location(
        self,
        asset_id: int,
        path: Path,
        *,
        managed: bool,
        status: str,
    ) -> int:
        normalized = str(path)
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO vault_locations (asset_id, path, managed, status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                asset_id = excluded.asset_id,
                managed = excluded.managed,
                status = excluded.status
            """,
            (int(asset_id), normalized, int(managed), status),
        )
        self.conn.commit()
        cur.execute("SELECT id FROM vault_locations WHERE path = ?", (normalized,))
        return int(cur.fetchone()["id"])

    @staticmethod
    def _result(asset_id: int, location_id: int, path: Path, sha256: str, managed: bool) -> dict[str, Any]:
        return {
            "asset_id": int(asset_id),
            "location_id": int(location_id),
            "path": str(path),
            "sha256": sha256,
            "managed": managed,
        }
