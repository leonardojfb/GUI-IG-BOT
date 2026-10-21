"""Safely clear account fields added by the invalid manifest-based migration."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from airtable_sync import load_airtable_config
from migrate_published_accounts import fetch_records


ROOT = Path(__file__).resolve().parent
SCOPE_FIELDS = ("Account ID", "Publication key")


def build_clears(before_records: list[dict], current_records: list[dict]) -> tuple[list[dict], list[str]]:
    before_by_id = {str(record.get("id") or ""): record.get("fields") or {} for record in before_records}
    clears: list[dict] = []
    skipped: list[str] = []
    for record in current_records:
        record_id = str(record.get("id") or "")
        before = before_by_id.get(record_id)
        if before is None or any(before.get(name) not in (None, "") for name in SCOPE_FIELDS):
            continue
        current = record.get("fields") or {}
        if not any(current.get(name) not in (None, "") for name in SCOPE_FIELDS):
            continue
        current_without_scope = {
            name: value for name, value in current.items() if name not in SCOPE_FIELDS
        }
        before_without_scope = {
            name: value for name, value in before.items() if name not in SCOPE_FIELDS
        }
        if current_without_scope != before_without_scope:
            skipped.append(record_id)
            continue
        clears.append({
            "id": record_id,
            "fields": {"Account ID": None, "Publication key": None},
        })
    return clears, skipped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    before_records = json.loads(args.backup.read_text(encoding="utf-8"))
    config = load_airtable_config()
    url, headers, current_records = fetch_records(config)
    clears, skipped = build_clears(before_records, current_records)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = args.report or ROOT / f"published_account_rollback_{stamp}.json"
    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "current_records": len(current_records),
        "planned_clears": len(clears),
        "skipped_changed_records": skipped,
        "applied_clears": 0,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**report, "skipped_changed_records": len(skipped)}, ensure_ascii=False))
    if not args.apply or not clears:
        return 0

    current_backup = ROOT / f"published_account_records_backup_before_rollback_{stamp}.json"
    current_backup.write_text(
        json.dumps(current_records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    applied = 0
    for start in range(0, len(clears), 10):
        chunk = clears[start:start + 10]
        response = requests.patch(url, headers=headers, json={"records": chunk}, timeout=20)
        response.raise_for_status()
        applied += len(chunk)
        report["applied_clears"] = applied
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "applied_clears": applied,
        "backup": str(current_backup),
        "report": str(report_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
