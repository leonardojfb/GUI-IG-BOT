from __future__ import annotations

from pathlib import Path
from typing import Any


class VaultThumbnailer:
    def __init__(self, storage, cache_root: str | Path):
        self.storage = storage
        self.cache_root = Path(cache_root)

    def ensure_thumbnail(self, asset_id: int, size: tuple[int, int] = (240, 135)) -> dict[str, Any]:
        asset = self._asset(asset_id)
        location = self._primary_location(asset_id)
        if location is None:
            return self._empty("missing", asset_id, "")
        source_path = location["path"]
        if asset["media_type"] != "image":
            return self._empty("unsupported", asset_id, source_path)
        target = self._thumbnail_path(asset["sha256"], size)
        if target.exists():
            return self._ok(asset, source_path, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import Image

            with Image.open(source_path) as image:
                preview = image.convert("RGB")
                preview.thumbnail(size, Image.Resampling.LANCZOS)
                preview.save(target, format="JPEG", quality=85, optimize=True)
        except Exception as exc:
            if target.exists():
                target.unlink()
            result = self._empty("error", asset, source_path)
            result["error"] = str(exc)
            return result
        return self._ok(asset, source_path, target)

    def _asset(self, asset_id: int) -> dict[str, Any]:
        cur = self.storage.conn.cursor()
        cur.execute("SELECT * FROM vault_assets WHERE id = ?", (int(asset_id),))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Asset Vault no encontrado: {asset_id}")
        return dict(row)

    def _primary_location(self, asset_id: int) -> dict[str, Any] | None:
        locations = self.storage.locations_for_asset(asset_id)
        if not locations:
            return None
        for row in locations:
            if row.get("status") == "ok" and Path(row["path"]).exists():
                return row
        return locations[0]

    def _thumbnail_path(self, sha256: str, size: tuple[int, int]) -> Path:
        width, height = int(size[0]), int(size[1])
        return self.cache_root / sha256[:2] / f"{sha256}_{width}x{height}.jpg"

    @staticmethod
    def _empty(status: str, asset: dict[str, Any] | int, source_path: str) -> dict[str, Any]:
        if isinstance(asset, dict):
            asset_id = asset["id"]
            display_name = asset["display_name"]
        else:
            asset_id = int(asset)
            display_name = ""
        return {
            "status": status,
            "asset_id": int(asset_id),
            "display_name": display_name,
            "source_path": source_path,
            "path": "",
            "width": 0,
            "height": 0,
        }

    def _ok(self, asset: dict[str, Any], source_path: str, path: Path) -> dict[str, Any]:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
        return {
            "status": "ok",
            "asset_id": int(asset["id"]),
            "display_name": asset["display_name"],
            "source_path": source_path,
            "path": str(path),
            "width": width,
            "height": height,
        }
