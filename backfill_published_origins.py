"""Backfill Origin token on existing Airtable publication records.

Read-only by default. Use --apply after reviewing the reported match count.
Only records with an unambiguous SHA-256 -> persisted transform origin match
are updated; unmatched records are left unchanged.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

from airtable_sync import PUBLISHED_VIDEOS_TABLE, _airtable_headers, load_airtable_config
from database import DatabaseManager, normalize_video_transform_source_identity


ROOT = Path(__file__).resolve().parent


def write_report(path: Path, report: dict) -> None:
    """Keep the last progress checkpoint if Windows briefly locks the report."""
    data = json.dumps(report, ensure_ascii=False, indent=2)
    for attempt in range(5):
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as stream:
                temp_name = stream.name
                stream.write(data)
            os.replace(temp_name, path)
            return
        except OSError:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)
            if attempt == 4:
                raise
            time.sleep(0.25 * (attempt + 1))


def origin_token(identity: str) -> str:
    digest = hashlib.blake2s(str(identity).encode("utf-8"), digest_size=12).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def fetch_records(config) -> tuple[str, dict, list[dict]]:
    url = "https://api.airtable.com/v0/{}/{}".format(
        quote(config.base_id, safe=""), quote(PUBLISHED_VIDEOS_TABLE, safe="")
    )
    headers = _airtable_headers(config)
    records: list[dict] = []
    offset = None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        response = requests.get(url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        records.extend(payload.get("records") or [])
        offset = payload.get("offset")
        if not offset:
            return url, headers, records


def build_origin_map(manifest_path: Path, db: DatabaseManager) -> tuple[dict, set[str]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_hash: dict[str, tuple[str, str]] = {}
    ambiguous: set[str] = set()
    for entry in payload.get("entries", []):
        path = Path(entry.get("source_path") or "")
        identity = str(entry.get("origin_identity") or "").strip()
        if not identity:
            identity = db.get_video_transform_source_identity(str(path)) or ""
        if not identity or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        value = (identity, origin_token(identity))
        if digest in by_hash and by_hash[digest] != value:
            ambiguous.add(digest)
        else:
            by_hash[digest] = value
    return by_hash, ambiguous


def verified_log_origin(db: DatabaseManager, filename: str, digest: str, hash_cache: dict) -> str | None:
    """Resolve a legacy upload only when its exact saved file matches the SHA."""
    if not filename or not re.fullmatch(r"[0-9a-f]{64}", str(digest or "")):
        return None
    rows = db.conn.execute(
        "SELECT output_path, process_kind, source_identity FROM video_transform_logs "
        "WHERE output_filename=? AND process_kind IN ('forge', 'forge_trial')",
        (filename,),
    ).fetchall()
    identities = set()
    for output_path, process_kind, source_identity in rows:
        identity = normalize_video_transform_source_identity(process_kind, source_identity)
        path = Path(output_path)
        if not identity or not path.is_file():
            continue
        if output_path not in hash_cache:
            hasher = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(chunk)
            hash_cache[output_path] = hasher.hexdigest()
        if hash_cache[output_path] == digest:
            identities.add(identity)
    return next(iter(identities)) if len(identities) == 1 else None


def unique_forge_log_origin(db: DatabaseManager, filename: str) -> str | None:
    """Use persisted provenance only if every Forge log with this exact name agrees."""
    if not filename or not re.search(r"__c\d+\.(?:mp4|mov)$", filename, re.IGNORECASE):
        return None
    rows = db.conn.execute(
        "SELECT process_kind, source_identity FROM video_transform_logs "
        "WHERE output_filename=? AND process_kind IN ('forge', 'forge_trial')",
        (filename,),
    ).fetchall()
    identities = {
        normalize_video_transform_source_identity(kind, identity)
        for kind, identity in rows
    }
    if None in identities:
        return None
    return next(iter(identities)) if len(identities) == 1 else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--manifest", type=Path, default=ROOT / "calendar_manifest.json")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    config = load_airtable_config()
    url, headers, records = fetch_records(config)
    db = DatabaseManager()
    try:
        by_hash, ambiguous = build_origin_map(args.manifest, db)
        hash_cache = {}
        updates = []
        log_verified_matches = 0
        provenance_only_matches = 0
        for record in records:
            fields = record.get("fields") or {}
            digest = fields.get("SHA-256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                continue
            mapped = by_hash.get(digest) if digest not in ambiguous else None
            if mapped and fields.get("Origin token") == mapped[1]:
                continue
            verified_identity = verified_log_origin(
                db, str(fields.get("Archivo original") or ""), digest, hash_cache,
            ) if not mapped else None
            if verified_identity:
                log_verified_matches += 1
            provenance_identity = (
                unique_forge_log_origin(db, str(fields.get("Archivo original") or ""))
                if not mapped and not verified_identity else None
            )
            if provenance_identity:
                provenance_only_matches += 1
            identity = mapped[0] if mapped else verified_identity or provenance_identity
            if not identity:
                continue
            token = origin_token(identity)
            if fields.get("Origin token") == token:
                continue
            updates.append({
                "id": record["id"], "sha256": digest,
                "origin_identity": identity, "origin_token": token,
            })
    finally:
        db.close()

    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "airtable_records": len(records),
        "origin_map_hashes": len(by_hash),
        "ambiguous_hashes": len(ambiguous),
        "log_verified_matches": log_verified_matches,
        "provenance_only_matches": provenance_only_matches,
        "planned_updates": len(updates),
        "applied_updates": 0,
        "updates": updates,
    }
    report_path = args.report or ROOT / (
        "published_origin_backfill_" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"
    )
    write_report(report_path, report)
    print(json.dumps({k: report[k] for k in report if k != "updates"}, ensure_ascii=False))

    if not args.apply or not updates:
        return 0

    backup_path = ROOT / (
        "published_origin_records_backup_" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"
    )
    backup_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"backup": str(backup_path)}, ensure_ascii=False))

    applied = 0
    for start in range(0, len(updates), 10):
        chunk = updates[start:start + 10]
        payload = {
            "records": [
                {"id": item["id"], "fields": {"Origin token": item["origin_token"]}}
                for item in chunk
            ]
        }
        response = requests.patch(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        applied += len(chunk)
        report["applied_updates"] = applied
        write_report(report_path, report)

    print(json.dumps({"applied_updates": applied, "report": str(report_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
