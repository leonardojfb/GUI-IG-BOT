from __future__ import annotations

from typing import Any


def register_transform_output(db, storage, transform_log_id: int) -> dict[str, Any]:
    cur = db.conn.cursor()
    cur.execute(
        """
        SELECT id, output_path, output_vault_asset_id
        FROM video_transform_logs
        WHERE id = ?
        """,
        (int(transform_log_id),),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(f"No existe transform log: {transform_log_id}")
    result = storage.import_managed(row["output_path"])
    cur.execute(
        """
        UPDATE video_transform_logs
        SET output_vault_asset_id = ?
        WHERE id = ?
        """,
        (result["asset_id"], int(transform_log_id)),
    )
    db.conn.commit()
    return result


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
