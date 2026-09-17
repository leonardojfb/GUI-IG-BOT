"""Typed, local-only CRM identity and metric summaries."""
from __future__ import annotations

import csv
import os
import tempfile
from hashlib import sha256
from pathlib import Path


def build_identity(username, *, platform, account_id, va=""):
    username = _required(username, "username")
    platform = _required(platform, "platform").lower()
    account_id = _required(account_id, "account_id")
    if any(part in username.lower() for part in ("cookie", "token", "password")):
        raise ValueError("username contiene un secreto")
    return {"type": "social_account", "platform": platform, "account_id": account_id, "username": username.casefold(), "va": str(va or "").strip()}


def summarize_metrics(rows):
    totals = {"posts": 0, "likes": 0, "comments": 0, "shares": 0}
    for row in rows or []:
        for key in totals:
            totals[key] += _number(row.get(key, 0))
    totals["engagement"] = totals["likes"] + totals["comments"] + totals["shares"]
    totals["engagement_rate"] = round(totals["engagement"] / totals["posts"], 4) if totals["posts"] else 0.0
    return totals


def score_virality(metrics, *, thresholds=None):
    values = dict(metrics or {})
    thresholds = dict(thresholds or {"high": 10.0, "medium": 4.0})
    rate = float(values.get("engagement_rate", 0.0) or 0.0)
    if rate >= float(thresholds["high"]):
        label = "high"
    elif rate >= float(thresholds["medium"]):
        label = "medium"
    else:
        label = "low"
    return {"label": label, "engagement_rate": rate, "thresholds": thresholds}


def build_infrastructure_event(account_id, *, device_id="", network_id="", observed_at=""):
    return {"account_id": _required(account_id, "account_id"), "device_ref": _pseudonym(device_id, "device"), "network_ref": _pseudonym(network_id, "network"), "observed_at": str(observed_at or "")}


def export_metrics_csv(path, rows):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    safe_rows = [{str(key): value for key, value in row.items() if not _sensitive_key(key)} for row in (rows or [])]
    fields = sorted({key for row in safe_rows for key in row})
    temp_name = ""
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(safe_rows)
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return {"path": str(target), "rows": len(safe_rows), "fields": fields}


def _number(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _sensitive_key(key):
    return any(part in str(key).lower() for part in ("cookie", "token", "password", "secret", "session"))


def _pseudonym(value, prefix):
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    return f"{prefix}:{sha256(normalized.encode('utf-8')).hexdigest()[:16]}"


def _required(value, field):
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} no puede estar vacio")
    return normalized
