from __future__ import annotations

from pathlib import Path
from typing import Any

from vault.lineage import VaultLineage


def register_transform_output(db, storage, transform_log_id: int) -> dict[str, Any]:
    cur = db.conn.cursor()
    cur.execute(
        """
        SELECT id, process_kind, source_path, output_path,
               source_vault_asset_id, output_vault_asset_id
        FROM video_transform_logs
        WHERE id = ?
        """,
        (int(transform_log_id),),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(f"No existe transform log: {transform_log_id}")
    result = storage.import_managed(row["output_path"])
    source_asset_id = row["source_vault_asset_id"]
    if source_asset_id is None and row["source_path"] and Path(row["source_path"]).is_file():
        source_asset_id = storage.register_external(row["source_path"])["asset_id"]
    cur.execute(
        """
        UPDATE video_transform_logs
        SET source_vault_asset_id = COALESCE(source_vault_asset_id, ?),
            output_vault_asset_id = ?
        WHERE id = ?
        """,
        (source_asset_id, result["asset_id"], int(transform_log_id)),
    )
    if source_asset_id is not None and int(source_asset_id) != int(result["asset_id"]):
        VaultLineage(db).record_derivation(
            result["asset_id"],
            [int(source_asset_id)],
            row["process_kind"] or "transform",
            {"transform_log_id": int(transform_log_id)},
        )
    db.conn.commit()
    return {**result, "source_asset_id": source_asset_id}


def register_transform_output_if_possible(db, storage, transform_log_id: int) -> dict[str, Any]:
    try:
        result = register_transform_output(db, storage, transform_log_id)
    except Exception as exc:
        return {
            "status": "error",
            "transform_log_id": int(transform_log_id),
            "error": str(exc),
        }
    return {
        "status": "ok",
        "transform_log_id": int(transform_log_id),
        **result,
    }
