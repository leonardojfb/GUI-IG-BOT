from __future__ import annotations

from typing import Any

from vault.lineage import VaultLineage
from vault.signatures import VaultSignatures


class VaultReuseAudit:
    def __init__(self, db):
        self.db = db

    @property
    def conn(self):
        return self.db.conn

    def candidates_for_asset(
        self,
        asset_id: int,
        *,
        signature_kinds: list[str] | None = None,
        require_usage: bool = True,
    ) -> list[dict[str, Any]]:
        current = int(asset_id)
        signatures = self._matching_signatures(current, signature_kinds)
        if not signatures:
            return []

        candidates: dict[int, dict[str, Any]] = {}
        signature_service = VaultSignatures(self.db)
        for signature in signatures:
            matches = signature_service.find_assets_by_signature(
                signature["signature_kind"],
                signature["signature_value"],
                algorithm=signature["algorithm"],
                exclude_asset_id=current,
            )
            for match in matches:
                candidate = candidates.setdefault(
                    int(match["asset_id"]),
                    {
                        "asset_id": int(match["asset_id"]),
                        "sha256": match["sha256"],
                        "media_type": match["media_type"],
                        "size_bytes": match["size_bytes"],
                        "display_name": match["display_name"],
                        "matched_signatures": [],
                    },
                )
                candidate["matched_signatures"].append(
                    {
                        "signature_kind": signature["signature_kind"],
                        "algorithm": signature["algorithm"],
                        "signature_value": signature["signature_value"],
                    }
                )

        lineage = VaultLineage(self.db)
        enriched = []
        for candidate in candidates.values():
            usages = lineage.usages_for_asset(candidate["asset_id"])
            if require_usage and not usages:
                continue
            candidate["matched_signatures"].sort(
                key=lambda row: (row["signature_kind"], row["algorithm"], row["signature_value"])
            )
            candidate["usages"] = usages
            candidate["usage_count"] = len(usages)
            enriched.append(candidate)
        enriched.sort(key=lambda row: (-row["usage_count"], row["asset_id"]))
        return enriched

    def _matching_signatures(
        self,
        asset_id: int,
        signature_kinds: list[str] | None,
    ) -> list[dict[str, Any]]:
        rows = VaultSignatures(self.db).signatures_for_asset(asset_id)
        if not signature_kinds:
            return rows
        allowed = {str(kind).strip() for kind in signature_kinds if str(kind).strip()}
        return [row for row in rows if row["signature_kind"] in allowed]
