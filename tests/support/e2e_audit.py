import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path


CAPTION_LABELS = {
    "ED_A": "CAPTION_ED_A_UNIQUE",
    "TA_B": "CAPTION_TA_B_UNIQUE",
    "FO_C": "CAPTION_FO_C_UNIQUE",
}


def extract_tanda_from_calendar_name(name: str) -> str | None:
    match = re.search(r"__TANDA_([^_]+_[ABC])__", name)
    return match.group(1) if match else None


def normalize_caption(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(str(value).split())


def expected_caption_for_tanda(tanda: str) -> str | None:
    return CAPTION_LABELS.get(tanda)


def _finding(code, status, message, **extra):
    row = {"code": code, "status": status, "message": message}
    row.update(extra)
    return row


def audit_filesystem(manifest, videos_root, calendar_root, require_calendar_files=True):
    findings = []
    outputs = manifest["outputs"]
    outputs_by_tanda = defaultdict(list)
    output_by_hash = {}
    for item in outputs:
        outputs_by_tanda[item["tanda"]].append(item)
        output_by_hash[item["output_hash"]] = item

    for tanda in manifest["matrix"]["tandas"]:
        count = len(outputs_by_tanda[tanda])
        if count != 3:
            findings.append(_finding("OUTPUT_COUNT", "FAIL", f"{tanda} has {count} outputs", tanda=tanda))

    calendar_files = [p for p in Path(calendar_root).rglob("*") if p.is_file() and p.suffix.lower() in {".mp4", ".mov"}]
    calendar_hashes = [manifest["sha256"](p) for p in calendar_files]
    dupes = [h for h, n in Counter(calendar_hashes).items() if n > 1]
    if dupes:
        findings.append(_finding("FILE_DUPLICATE", "FAIL", "duplicated calendar hash", hashes=dupes))

    by_tanda = defaultdict(list)
    for path in calendar_files:
        tanda = extract_tanda_from_calendar_name(path.name)
        by_tanda[tanda].append(path)
        if not tanda:
            findings.append(_finding("TANDA_MISSING", "FAIL", "calendar file has no TANDA marker", file=str(path)))
            continue
        expected_category = manifest["matrix"]["tandas"][tanda]["category"]
        account = path.parent.name
        account_info = manifest["accounts_by_username"].get(account)
        if not account_info:
            findings.append(_finding("ACCOUNT_UNKNOWN", "FAIL", "calendar account not in manifest", file=str(path), account_actual=account))
            continue
        if account_info["category"] != expected_category:
            findings.append(
                _finding(
                    "CATEGORY_MIX",
                    "FAIL",
                    "calendar file landed in wrong category account",
                    file=str(path),
                    tanda=tanda,
                    category_expected=expected_category,
                    account_actual=account,
                    category_actual=account_info["category"],
                    va_actual=account_info["va"],
                )
            )
        source_candidates = [o for o in outputs_by_tanda[tanda] if path.name.startswith(Path(o["output"]).stem)]
        if not source_candidates:
            findings.append(
                _finding(
                    "TANDA_MIX",
                    "FAIL",
                    "calendar filename claims a tanda but its source output belongs to another tanda",
                    file=str(path),
                    tanda=tanda,
                    account_actual=account,
                    va_actual=account_info["va"],
                )
            )
            continue
        calendar_hash = manifest["sha256"](path)
        source_path = Path(source_candidates[0]["output"])
        source_bytes = source_path.read_bytes()
        calendar_bytes = path.read_bytes()
        metadata_suffix = calendar_bytes[len(source_bytes):]
        expected_mutation = re.fullmatch(rb"\n# ID_[A-Za-z0-9]{16}", metadata_suffix)
        if calendar_bytes.startswith(source_bytes) and expected_mutation:
            continue
        findings.append(
            _finding(
                "CALENDAR_CONTENT_CHANGED",
                "FAIL",
                "calendar file is not the processed output plus Logistica metadata marker",
                file=str(path),
                tanda=tanda,
                source_hash=source_candidates[0].get("source_hash"),
                output_hash=source_candidates[0]["output_hash"],
                calendar_hash=calendar_hash,
                account_actual=account,
                va_actual=account_info["va"],
            )
        )

    if require_calendar_files:
        for tanda in manifest["matrix"]["tandas"]:
            if len(by_tanda[tanda]) != 3:
                findings.append(_finding("FILE_MISSING", "FAIL", f"{tanda} has {len(by_tanda[tanda])} distributed files", tanda=tanda))

    return findings


def audit_manifest_calendar(manifest):
    findings = []
    entries = manifest.get("calendar_entries", [])
    accounts_by_username = manifest["accounts_by_username"]

    seen_usernames = Counter(entry.get("username") for entry in entries)
    for username, count in seen_usernames.items():
        if count != 1:
            findings.append(_finding("MANIFEST_DUPLICATE_ACCOUNT", "FAIL", "manifest has duplicate account plan", account_actual=username, count=count))

    expected_usernames = set(accounts_by_username)
    actual_usernames = set(seen_usernames)
    for username in sorted(expected_usernames - actual_usernames):
        findings.append(_finding("MANIFEST_ACCOUNT_MISSING", "FAIL", "manifest lacks account plan", account_actual=username))
    for username in sorted(actual_usernames - expected_usernames):
        findings.append(_finding("MANIFEST_ACCOUNT_UNKNOWN", "FAIL", "manifest has unknown account", account_actual=username))

    for entry in entries:
        username = entry.get("username")
        account = accounts_by_username.get(username, {})
        tanda = entry.get("tanda")
        expected_category = manifest["matrix"]["tandas"].get(tanda, {}).get("category")
        if expected_category and account.get("category") != expected_category:
            findings.append(
                _finding(
                    "CATEGORY_MIX",
                    "FAIL",
                    "manifest entry targets an account from another category",
                    tanda=tanda,
                    account_actual=username,
                    category_expected=expected_category,
                    category_actual=account.get("category"),
                    va_actual=account.get("va"),
                )
            )
        if not Path(entry.get("source_path", "")).is_file():
            findings.append(
                _finding(
                    "MANIFEST_SOURCE_MISSING",
                    "FAIL",
                    "manifest source file does not exist",
                    file=entry.get("source_path", ""),
                    tanda=tanda,
                    account_actual=username,
                    va_actual=account.get("va"),
                )
            )
        filename_tanda = extract_tanda_from_calendar_name(entry.get("telegram_filename", ""))
        if filename_tanda != tanda:
            findings.append(
                _finding(
                    "TANDA_MIX",
                    "FAIL",
                    "manifest telegram filename tanda marker differs from entry",
                    file=entry.get("telegram_filename", ""),
                    tanda=tanda,
                    account_actual=username,
                    va_actual=account.get("va"),
                )
            )
    return findings


def audit_database(manifest, db_path):
    import sqlite3

    findings = []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT username, account_type, assigned_va FROM virtual_accounts")
        accounts_by_username = {row["username"]: dict(row) for row in cur.fetchall()}
        for expected in manifest["matrix"]["accounts"]:
            actual = accounts_by_username.get(expected["username"], {})
            if actual.get("account_type") != expected["category"] or actual.get("assigned_va") != expected["va"]:
                findings.append(
                    _finding(
                        "ACCOUNT_VA_MIX",
                        "FAIL",
                        "database account category or VA differs from the campaign matrix",
                        account_actual=expected["username"],
                        category_expected=expected["category"],
                        category_actual=actual.get("account_type"),
                        va_actual=actual.get("assigned_va"),
                        va_expected=expected["va"],
                    )
                )
        cur.execute("SELECT tanda_name, captions_file_path FROM batch_tandas")
        captions_by_tanda = {row["tanda_name"]: row["captions_file_path"] for row in cur.fetchall()}
        for tanda, info in manifest["matrix"]["tandas"].items():
            expected = info.get("caption")
            actual = captions_by_tanda.get(tanda)
            if expected and (not actual or Path(actual).name != expected):
                findings.append(_finding("CAPTION_DB_MISSING", "FAIL", "caption path missing in batch_tandas", tanda=tanda, caption_expected=expected, caption_actual=actual))
            if not expected and actual:
                findings.append(_finding("CAPTION_DB_UNEXPECTED", "FAIL", "unexpected caption path in batch_tandas", tanda=tanda, caption_actual=actual))

        cur.execute("SELECT tanda_name, source_name, output_name, video_hash FROM forge_video_registry")
        forge_rows = [dict(row) for row in cur.fetchall()]
        for tanda in [t for t, i in manifest["matrix"]["tandas"].items() if i["stage"] == "forge"]:
            rows = [r for r in forge_rows if r["tanda_name"] == tanda]
            if len(rows) != 3:
                findings.append(_finding("FORGE_REGISTRY_MISSING", "FAIL", "forge registry does not have three rows", tanda=tanda, count=len(rows)))
            for row in rows:
                if not row.get("source_name") or not row.get("output_name") or not row.get("video_hash"):
                    findings.append(_finding("FORGE_TRACE_MISSING", "FAIL", "forge row lacks trace fields", tanda=tanda, row=row))
                parts = Path(row["output_name"]).stem.split("__")
                if len(parts) < 3:
                    findings.append(_finding("FORGE_P1P2_MISSING", "FAIL", "forge output name lacks full P1/P2 trace", tanda=tanda, output=row["output_name"]))
    finally:
        conn.close()
    return findings


def audit_telegram(manifest, events, label):
    findings = []
    video_events = [e for e in events if e.get("event") == "video"]
    seen_paths = Counter(e["video_path"] for e in video_events)
    entries_by_source = {
        str(entry.get("source_path")): entry
        for entry in manifest.get("calendar_entries", [])
    }
    for path, count in seen_paths.items():
        if count != 1:
            findings.append(_finding("TELEGRAM_DUPLICATE_SEND", "FAIL", "telegram sent a file more than once", file=path, count=count, run=label))

    for event in video_events:
        path = Path(event["video_path"])
        username = event["username"]
        account = manifest["accounts_by_username"].get(username, {})
        entry = entries_by_source.get(str(path))
        tanda = entry.get("tanda") if entry else extract_tanda_from_calendar_name(path.name)
        expected_chat = manifest["va_chat_by_name"].get(account.get("va"))
        if event["chat_id"] != expected_chat or username not in str(event["topic_id"]):
            findings.append(
                _finding(
                    "TELEGRAM_CHAT_TOPIC_MIX",
                    "FAIL",
                    "telegram destination does not match account VA/topic",
                    file=str(path),
                    tanda=tanda,
                    account_actual=username,
                    va_actual=account.get("va"),
                    chat_expected=expected_chat,
                    chat_actual=event["chat_id"],
                    topic_actual=event["topic_id"],
                    run=label,
                )
            )

        expected_label = expected_caption_for_tanda(tanda)
        actual = normalize_caption(event.get("caption"))
        actual_label = None
        for marker in CAPTION_LABELS.values():
            if actual and marker in actual:
                actual_label = marker
                break

        if expected_label and actual_label != expected_label:
            findings.append(
                _finding(
                    "CAPTION_LOST",
                    "FAIL",
                    "expected tanda caption missing or replaced",
                    file=str(path),
                    tanda=tanda,
                    account_actual=username,
                    va_actual=account.get("va"),
                    caption_expected=expected_label,
                    caption_actual=actual,
                    run=label,
                )
            )
        if not expected_label and actual_label:
            findings.append(
                _finding(
                    "CAPTION_UNEXPECTED",
                    "FAIL",
                    "caption applied to tanda without caption",
                    file=str(path),
                    tanda=tanda,
                    account_actual=username,
                    va_actual=account.get("va"),
                    caption_expected=None,
                    caption_actual=actual,
                    run=label,
                )
            )
        if actual_label and expected_label and actual_label != expected_label:
            findings.append(
                _finding(
                    "CAPTION_WRONG_TANDA",
                    "FAIL",
                    "caption belongs to a different tanda",
                    file=str(path),
                    tanda=tanda,
                    account_actual=username,
                    va_actual=account.get("va"),
                    caption_expected=expected_label,
                    caption_actual=actual,
                    run=label,
                )
            )
        if actual_label and not expected_label:
            findings.append(
                _finding(
                    "CAPTION_WRONG_TANDA",
                    "FAIL",
                    "caption belongs to a different tanda",
                    file=str(path),
                    tanda=tanda,
                    account_actual=username,
                    va_actual=account.get("va"),
                    caption_expected=None,
                    caption_actual=actual,
                    run=label,
                )
            )
    return findings


def render_audit_report(findings, output_path, summary):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_path.with_suffix(".json")
    json_path.write_text(json.dumps({"summary": summary, "findings": findings}, indent=2), encoding="utf-8")

    lines = [
        f"# E2E audit {summary['run_id']}",
        "",
        f"- processed outputs: {summary['actual']['processed_outputs']} / {summary['expected']['processed_outputs']}",
        f"- distributed files: {summary['actual']['distributed_files']} / {summary['expected']['distributed_files']}",
        f"- manifest entries: {summary['actual']['manifest_entries']} / {summary['expected']['manifest_entries']}",
        f"- telegram sends: {summary['actual']['telegram_sends']} / {summary['expected']['telegram_sends']}",
        "",
        "| status | code | tanda | account | VA | caption expected | caption actual | file |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for finding in findings:
        lines.append(
            "| {status} | {code} | {tanda} | {account} | {va} | {ce} | {ca} | {file} |".format(
                status=finding.get("status", ""),
                code=finding.get("code", ""),
                tanda=finding.get("tanda", ""),
                account=finding.get("account_actual", ""),
                va=finding.get("va_actual", ""),
                ce=str(finding.get("caption_expected", "")),
                ca=str(finding.get("caption_actual", ""))[:80].replace("\n", " "),
                file=finding.get("file", ""),
            )
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(json_path), str(output_path)
