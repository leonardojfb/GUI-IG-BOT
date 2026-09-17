"""Read-only adapters that feed concrete data into the shared planner."""
from __future__ import annotations

import json
from pathlib import Path

from shared_planner import preview_shared_schedule


VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".avi"})


def load_candidate_usage_rows(db, candidates: list[dict]) -> list[dict]:
    """Attach normalized Vault usage context to candidates without writes."""
    result = []
    for candidate in candidates:
        enriched = dict(candidate)
        paths = _candidate_paths(candidate)
        usages = []
        if paths:
            placeholders = ",".join("?" for _ in paths)
            cur = db.conn.cursor()
            cur.execute(
                f"""
                SELECT vu.usage_kind, vu.external_ref, vu.details_json
                FROM vault_asset_usages vu
                JOIN vault_locations vl ON vl.asset_id = vu.asset_id
                WHERE vl.path IN ({placeholders})
                ORDER BY vu.id
                """,
                paths,
            )
            for row in cur.fetchall():
                details = _parse_details(row["details_json"])
                usages.append(
                    {
                        "username": str(details.get("username") or ""),
                        "lane": _lane_from_details(details),
                        "usage_kind": str(row["usage_kind"] or ""),
                        "external_ref": str(row["external_ref"] or ""),
                    }
                )
        enriched["used_in"] = usages
        result.append(enriched)
    return result


def preview_schedule_from_sources(
    db,
    videos_root,
    tanda_names,
    *,
    usernames=None,
    **planner_options,
) -> dict:
    """Compose read-only account/source adapters with the shared preview."""
    accounts = load_planner_accounts(db, usernames=usernames)
    inventory = collect_tanda_candidates(videos_root, tanda_names)
    preview = preview_shared_schedule(
        accounts=accounts,
        candidates=inventory["candidates"],
        **planner_options,
    )
    preview["inventory"] = {
        key: inventory[key]
        for key in ("missing_tandas", "empty_tandas", "skipped_files")
    }
    return preview


def load_planner_accounts(db, usernames=None) -> list[dict]:
    """Return normalized account records without writing through ``db``."""
    requested = None if usernames is None else {
        _required_label(name, "username").casefold() for name in usernames
    }
    result = []
    seen = set()
    for row in db.get_all_accounts():
        username = _required_label(row.get("username"), "username")
        key = username.casefold()
        if key in seen:
            raise ValueError(f"username duplicado en base de datos: {username}")
        seen.add(key)
        if requested is not None and key not in requested:
            continue
        result.append(
            {
                "account_id": row.get("id"),
                "username": username,
                "assigned_va": str(row.get("assigned_va") or ""),
                "account_type": str(row.get("account_type") or ""),
            }
        )
    return result


def collect_tanda_candidates(videos_root, tanda_names) -> dict:
    """Scan selected tanda folders and return concrete planner candidates.

    The scan is read-only and reports missing folders, empty folders, and files
    skipped because their extension is not a supported video type.
    """
    root = Path(videos_root).resolve()
    candidates = []
    missing_tandas = []
    empty_tandas = []
    skipped_files = 0
    seen_tandas = set()
    for raw_name in tanda_names:
        tanda = _required_label(raw_name, "tanda")
        if tanda in seen_tandas:
            raise ValueError(f"tanda duplicada: {tanda}")
        seen_tandas.add(tanda)
        folder = root / tanda
        if not folder.is_dir():
            missing_tandas.append(tanda)
            continue
        files = sorted((item for item in folder.iterdir() if item.is_file()), key=lambda item: item.name.casefold())
        supported = []
        for item in files:
            if item.suffix.casefold() in VIDEO_EXTENSIONS:
                supported.append(item)
            else:
                skipped_files += 1
        if not supported:
            empty_tandas.append(tanda)
            continue
        for item in supported:
            candidates.append(
                {
                    "source_id": f"{tanda}:{item.name}",
                    "source_path": str(item),
                    "display_filename": item.name,
                    "tanda": tanda,
                    "media_class": "video",
                }
            )
    return {
        "candidates": candidates,
        "missing_tandas": missing_tandas,
        "empty_tandas": empty_tandas,
        "skipped_files": skipped_files,
    }


def _required_label(value, field: str) -> str:
    label = str(value or "").strip()
    if not label:
        raise ValueError(f"{field} no puede estar vacio")
    return label


def _candidate_paths(candidate: dict) -> list[str]:
    raw = str(candidate.get("source_path") or candidate.get("path") or "").strip()
    if not raw:
        return []
    paths = [raw]
    resolved = str(Path(raw).resolve())
    if resolved not in paths:
        paths.append(resolved)
    return paths


def _parse_details(raw) -> dict:
    if isinstance(raw, dict):
        return dict(raw)
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _lane_from_details(details: dict) -> str:
    lane = str(details.get("lane") or "").strip()
    if lane:
        return lane
    return {
        "instagram_trial_reel": "trial_reel",
        "instagram_reel": "reel",
        "instagram_story": "story",
        "instagram_post": "post",
        "facebook_reel": "reel",
    }.get(str(details.get("publication_target") or "").strip(), "")
