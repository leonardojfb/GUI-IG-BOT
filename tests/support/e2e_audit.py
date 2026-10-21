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


def audit_filesystem(manifest, videos_root, calendar_root):
    findings = []
    outputs = manifest["outputs"]
    outputs_by_tanda = defaultdict(list)
    output_paths_by_tanda = defaultdict(set)
    for item in outputs:
        outputs_by_tanda[item["tanda"]].append(item)
        output_paths_by_tanda[item["tanda"]].add(str(Path(item["output"]).resolve()))

    for tanda in manifest["matrix"]["tandas"]:
        count = len(outputs_by_tanda[tanda])
        if count != 3:
            findings.append(_finding("OUTPUT_COUNT", "FAIL", f"{tanda} has {count} outputs", tanda=tanda))

    calendar_manifest = Path(manifest["run_root"]) / "calendar_manifest.json"
    if not calendar_manifest.is_file():
        return [_finding("FILE_MISSING", "FAIL", "calendar manifest was not created")]
    entries = json.loads(calendar_manifest.read_text(encoding="utf-8")).get("entries", [])
    by_tanda = defaultdict(list)
    origins_by_tanda_account = defaultdict(list)
    seen_names = set()
    for entry in entries:
        tanda = entry.get("tanda")
        if tanda not in manifest["matrix"]["tandas"]:
            findings.append(_finding("TANDA_MISSING", "FAIL", "manifest entry has no known tanda", file=entry.get("telegram_filename")))
            continue
        expected_category = manifest["matrix"]["tandas"][tanda]["category"]
        account = entry.get("username")
        account_info = manifest["accounts_by_username"].get(account)
        if not account_info:
            findings.append(_finding("ACCOUNT_UNKNOWN", "FAIL", "calendar account not in manifest", file=entry.get("telegram_filename"), account_actual=account))
            continue
        if account_info["category"] != expected_category:
            findings.append(
                _finding(
                    "CATEGORY_MIX",
                    "FAIL",
                    "calendar entry targets an account in the wrong category",
                    file=entry.get("telegram_filename"),
                    tanda=tanda,
                    category_expected=expected_category,
                    account_actual=account,
                    category_actual=account_info["category"],
                    va_actual=account_info["va"],
                )
            )
        source_path = Path(entry.get("source_path", ""))
        if str(source_path.resolve()) not in output_paths_by_tanda[tanda]:
            findings.append(
                _finding(
                    "TANDA_MIX",
                    "FAIL",
                    "calendar entry's source output belongs to another tanda",
                    file=entry.get("telegram_filename"),
                    tanda=tanda,
                    account_actual=account,
                    va_actual=account_info["va"],
                )
            )
            continue
        if not source_path.is_file():
            findings.append(_finding("FILE_MISSING", "FAIL", "calendar source file is missing", file=str(source_path), tanda=tanda))
        by_tanda[tanda].append(entry)
        stem = re.sub(r"__c\d+$", "", source_path.stem, flags=re.IGNORECASE)
        parts = stem.split("__")
        origin = f"{parts[1]}__{parts[2]}" if len(parts) >= 3 else stem
        origins_by_tanda_account[(tanda, account)].append(origin)
        logical_name = entry.get("telegram_filename")
        if logical_name in seen_names:
            findings.append(_finding("FILE_DUPLICATE", "FAIL", "duplicate calendar delivery name", file=logical_name, tanda=tanda))
        seen_names.add(logical_name)

    for tanda, tanda_info in manifest["matrix"]["tandas"].items():
        account_count = sum(
            1 for account in manifest["matrix"]["accounts"]
            if account["category"] == tanda_info["category"]
        )
        origins = {
            _audit_origin(Path(output["output"]).name)
            for output in outputs_by_tanda[tanda]
        }
        expected_count = len(origins) * account_count
        if len(by_tanda[tanda]) != expected_count:
            findings.append(
                _finding(
                    "FILE_MISSING",
                    "FAIL",
                    f"{tanda} has {len(by_tanda[tanda])} distributed files; expected {expected_count}",
                    tanda=tanda,
                )
            )
        for account in manifest["matrix"]["accounts"]:
            if account["category"] != tanda_info["category"]:
                continue
            delivered = origins_by_tanda_account[(tanda, account["username"])]
            if len(delivered) != len(set(delivered)) or set(delivered) != origins:
                findings.append(
                    _finding(
                        "FILE_MISSING",
                        "FAIL",
                        f"{tanda} did not deliver each origin exactly once to {account['username']}",
                        tanda=tanda,
                        account_actual=account["username"],
                    )
                )

    return findings


def _audit_origin(filename):
    stem = re.sub(r"__c\d+$", "", Path(filename).stem, flags=re.IGNORECASE)
    parts = stem.split("__")
    return f"{parts[1]}__{parts[2]}" if len(parts) >= 3 else stem


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
    seen_paths = Counter((e["username"], e["video_path"]) for e in video_events)
    for (username, path), count in seen_paths.items():
        if count != 1:
            findings.append(_finding("TELEGRAM_DUPLICATE_SEND", "FAIL", "telegram sent an origin to one account more than once", file=path, account_actual=username, count=count, run=label))

    for event in video_events:
        path = Path(event["video_path"])
        username = event["username"]
        account = manifest["accounts_by_username"].get(username, {})
        tanda = path.parent.name
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
