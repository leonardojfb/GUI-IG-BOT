"""Backfill account-scoped keys in Airtable's published-video table."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

from airtable_sync import PUBLISHED_VIDEOS_TABLE, _airtable_headers, load_airtable_config
from railway_telegram_publish_webhook.telegram_publish_webhook import account_id_from_filename


ROOT = Path(__file__).resolve().parent


def build_updates(records: list[dict]) -> tuple[list[dict], list[str]]:
    updates: list[dict] = []
    unresolved: list[str] = []
    for record in records:
        record_id = str(record.get("id") or "")
        fields = record.get("fields") or {}
        source_hash = fields.get("SHA-256")
        if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
            unresolved.append(record_id)
            continue
        evidence: set[str] = set()
        filename_account_id = account_id_from_filename(fields.get("Archivo original") or "")
        if filename_account_id:
            evidence.add(filename_account_id)
        persisted_account_id = str(fields.get("Account ID") or "").strip()
        if persisted_account_id:
            if not re.fullmatch(r"\d+", persisted_account_id) or any(
                candidate != persisted_account_id for candidate in evidence
            ):
                unresolved.append(record_id)
                continue
            account_id = persisted_account_id
        elif len(evidence) == 1:
            account_id = next(iter(evidence))
        else:
            unresolved.append(record_id)
            continue
        expected = {
            "Account ID": account_id,
            "Publication key": f"{account_id}:{source_hash}",
        }
        changed = {name: value for name, value in expected.items() if fields.get(name) != value}
        if changed:
            updates.append({"id": record_id, "fields": changed})
    return updates, unresolved


def fetch_records(config) -> tuple[str, dict[str, str], list[dict]]:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    config = load_airtable_config()
    url, headers, records = fetch_records(config)
    updates, unresolved = build_updates(records)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = args.report or ROOT / f"published_account_migration_{stamp}.json"
    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "airtable_records": len(records),
        "planned_updates": len(updates),
        "unresolved": unresolved,
        "applied_updates": 0,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**report, "unresolved": len(unresolved)}, ensure_ascii=False))
    if not args.apply or not updates:
        return 0

    backup_path = ROOT / f"published_account_records_backup_{stamp}.json"
    backup_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    applied = 0
    for start in range(0, len(updates), 10):
        chunk = updates[start:start + 10]
        response = requests.patch(
            url, headers=headers, json={"records": chunk}, timeout=20
        )
        response.raise_for_status()
        applied += len(chunk)
        report["applied_updates"] = applied
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "applied_updates": applied,
        "backup": str(backup_path),
        "report": str(report_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
