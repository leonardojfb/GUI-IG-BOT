from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vault.storage import hash_file, media_type_for_path


class VaultSignatures:
    def __init__(self, db):
        self.db = db
        self._ensure_schema()

    @property
    def conn(self):
        return self.db.conn

    def ensure_file_signatures(self, asset_id: int, path: str | Path) -> list[dict[str, Any]]:
        target = Path(path)
        if not target.is_file():
            raise FileNotFoundError(str(target))
        asset = self._require_asset(asset_id)
        payload = [
            ("sha256", hash_file(target), "sha256", {"source": "file"}),
            ("size_bytes", str(target.stat().st_size), "stat", {"source": "file"}),
            ("extension", target.suffix.lower(), "path", {"source": "file"}),
            ("media_type", media_type_for_path(target), "path", {"source": "file"}),
        ]
        if payload[0][1] != asset["sha256"]:
            raise ValueError("La firma sha256 no coincide con el asset Vault")
        for kind, value, algorithm, details in payload:
            self.record_signature(asset_id, kind, value, algorithm=algorithm, details=details)
        return self.signatures_for_asset(asset_id)

    def ensure_perceptual_signature(self, asset_id: int, path: str | Path) -> dict[str, Any]:
        target = Path(path)
        if target.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError("la firma perceptual requiere una imagen")
        self._require_asset(asset_id)
        from photo_forge import perceptual_signature

        value = perceptual_signature(target)
        return self.record_signature(
            asset_id, "perceptual_hash", value, algorithm="average_hash_8x8",
            details={"source": "photo_forge", "hash_size": 8},
        )

    def find_assets_by_perceptual_similarity(self, asset_id: int, *, max_distance: int = 4) -> list[dict[str, Any]]:
        if int(max_distance) < 0 or int(max_distance) > 64:
            raise ValueError("max_distance fuera de rango")
        current = next(
            (row for row in self.signatures_for_asset(asset_id)
             if row["signature_kind"] == "perceptual_hash" and row["algorithm"] == "average_hash_8x8"),
            None,
        )
        if current is None:
            raise ValueError("el asset no tiene firma perceptual")
        from photo_forge import perceptual_distance

        candidates = self.find_assets_by_signature(
            "perceptual_hash", current["signature_value"],
            algorithm="average_hash_8x8", exclude_asset_id=asset_id,
        )
        # Exact signatures are indexed by SQLite. Near matches are evaluated
        # against all stored perceptual signatures without changing the schema.
        cur = self.conn.cursor()
        cur.execute(
            "SELECT asset_id, signature_value FROM vault_asset_signatures WHERE signature_kind=? AND algorithm=? AND asset_id<>? ORDER BY asset_id",
            ("perceptual_hash", "average_hash_8x8", int(asset_id)),
        )
        by_asset = {row[0]: row[1] for row in cur.fetchall()}
        result = []
        for candidate in self.find_assets_by_signature("perceptual_hash", current["signature_value"], algorithm="average_hash_8x8", exclude_asset_id=asset_id):
            candidate["distance"] = 0
            result.append(candidate)
        exact_ids = {row["asset_id"] for row in result}
        for candidate_id, value in by_asset.items():
            if candidate_id in exact_ids:
                continue
            distance = perceptual_distance(current["signature_value"], value)
            if distance <= int(max_distance):
                rows = self.find_assets_by_signature("perceptual_hash", value, algorithm="average_hash_8x8", exclude_asset_id=asset_id)
                for candidate in rows:
                    candidate["distance"] = distance
                    result.append(candidate)
        return sorted(result, key=lambda row: (row["distance"], row["asset_id"]))

    def record_signature(
        self,
        asset_id: int,
        signature_kind: str,
        signature_value: str,
        *,
        algorithm: str = "literal",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        asset = int(asset_id)
        self._require_asset(asset)
        kind = self._required(signature_kind, "signature_kind")
        algo = self._required(algorithm, "algorithm")
        value = self._required(signature_value, "signature_value")
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO vault_asset_signatures
                (asset_id, signature_kind, algorithm, signature_value, details_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(asset_id, signature_kind, algorithm) DO UPDATE SET
                signature_value = excluded.signature_value,
                details_json = excluded.details_json,
                updated_at = CURRENT_TIMESTAMP
            WHERE vault_asset_signatures.signature_value <> excluded.signature_value
               OR vault_asset_signatures.details_json <> excluded.details_json
            """,
            (asset, kind, algo, value, self._json(details)),
        )
        self.conn.commit()
        cur.execute(
            """
            SELECT id, asset_id, signature_kind, algorithm, signature_value,
                   details_json, created_at, updated_at
            FROM vault_asset_signatures
            WHERE asset_id = ? AND signature_kind = ? AND algorithm = ?
            """,
            (asset, kind, algo),
        )
        return dict(cur.fetchone())

    def signatures_for_asset(self, asset_id: int) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, asset_id, signature_kind, algorithm, signature_value,
                   details_json, created_at, updated_at
            FROM vault_asset_signatures
            WHERE asset_id = ?
            ORDER BY signature_kind, algorithm
            """,
            (int(asset_id),),
        )
        return [dict(row) for row in cur.fetchall()]

    def find_assets_by_signature(
        self,
        signature_kind: str,
        signature_value: str,
        *,
        algorithm: str | None = None,
        exclude_asset_id: int | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [
            self._required(signature_kind, "signature_kind"),
            self._required(signature_value, "signature_value"),
        ]
        where = ["s.signature_kind = ?", "s.signature_value = ?"]
        if algorithm is not None:
            where.append("s.algorithm = ?")
            params.append(self._required(algorithm, "algorithm"))
        if exclude_asset_id is not None:
            where.append("s.asset_id <> ?")
            params.append(int(exclude_asset_id))
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT s.id AS signature_id, s.asset_id, s.signature_kind,
                   s.algorithm, s.signature_value, s.details_json,
                   a.sha256, a.media_type, a.size_bytes, a.display_name
            FROM vault_asset_signatures s
            JOIN vault_assets a ON a.id = s.asset_id
            WHERE {' AND '.join(where)}
            ORDER BY s.asset_id, s.signature_kind, s.algorithm
            """,
            params,
        )
        return [dict(row) for row in cur.fetchall()]

    def _require_asset(self, asset_id: int) -> dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM vault_assets WHERE id = ?", (int(asset_id),))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"No existe asset: {asset_id}")
        return dict(row)

    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS vault_asset_signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                signature_kind TEXT NOT NULL,
                algorithm TEXT NOT NULL DEFAULT 'literal',
                signature_value TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(asset_id, signature_kind, algorithm),
                FOREIGN KEY (asset_id) REFERENCES vault_assets(id)
            );
            CREATE INDEX IF NOT EXISTS idx_vault_asset_signatures_lookup
            ON vault_asset_signatures(signature_kind, signature_value);
            """
        )
        self.conn.commit()

    @staticmethod
    def _json(payload: dict[str, Any] | None) -> str:
        return json.dumps(payload or {}, sort_keys=True, ensure_ascii=False)

    @staticmethod
    def _required(value: str, field: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field} no puede estar vacio")
        return normalized
