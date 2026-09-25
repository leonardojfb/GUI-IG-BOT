"""Deterministic source grouping for Forge Trial copies."""
import os
import re
import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path

_COPY_SUFFIX = re.compile(r"__c\d+$", re.IGNORECASE)


def source_key_from_filename(filename: str) -> str:
    """Return the original source key used for captions and distribution."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = re.sub(r"__TANDA_.+$", "", stem)
    stem = _COPY_SUFFIX.sub("", stem)
    parts = stem.split("__")
    if len(parts) >= 3:
        return parts[1]
    return stem


def forge_output_id_from_filename(filename: str) -> str:
    """Return the Forge output stem while preserving Edicion P1/P2 separators."""
    base = os.path.splitext(os.path.basename(filename))[0]
    if len(base.split("__")) >= 3:
        return base
    return base.replace(" ", "_").replace("__", "_")


def group_trial_sources(filenames: list[str]) -> list[tuple[str, list[str]]]:
    """Group Forge outputs in stable source-key order."""
    groups: dict[str, list[str]] = {}
    for filename in sorted(filenames):
        groups.setdefault(source_key_from_filename(filename), []).append(filename)
    return list(groups.items())


def _interleave_trial_files(filenames: list[str]) -> list[str]:
    """Order copies by source round: vid1c1, vid2c1, then vid1c2."""
    groups = group_trial_sources(filenames)
    if not groups:
        return []
    max_copies = max(len(copies) for _source_key, copies in groups)
    interleaved = []
    for copy_index in range(max_copies):
        for _source_key, copies in groups:
            if copy_index < len(copies):
                interleaved.append(copies[copy_index])
    return interleaved


def missing_trial_caption_sources(filenames: list[str], captions: dict[str, str]) -> list[str]:
    """Return source keys which have no non-empty persisted caption."""
    return [
        source_key for source_key, _copies in group_trial_sources(filenames)
        if not str(captions.get(source_key) or "").strip()
    ]


def selected_trial_usernames(accounts: list[dict]) -> list[str]:
    """Return active Trial usernames without considering their category."""
    return [str(account["username"]) for account in accounts if account.get("trials_active")]


def trial_calendar_root(base_dir) -> os.PathLike:
    """Keep the Trial calendar physically separate from normal content."""
    from pathlib import Path
    return Path(base_dir) / "CALENDARIO_TRIALS"


@dataclass(frozen=True)
class TrialPlan:
    assigned: dict[str, list[str]]
    shortfalls: dict[str, int]
    tanda_stats: dict[str, dict]


def build_trial_account_plan(assignments, files_by_tanda, videos_per_day, days):
    """Allocate each Forge output once across accounts that selected its tanda."""
    max_mode = str(days).strip().upper() == "MAX"
    per_account = None if max_mode else int(videos_per_day) * int(days)
    remaining = {
        tanda: _interleave_trial_files(list(files_by_tanda.get(tanda, ())))
        for tanda in set(assignments.values()) if tanda
    }
    requested_by_tanda = {
        tanda: len(pool) if max_mode else per_account
        for tanda, pool in remaining.items()
    }
    assigned, shortfalls = {}, {}
    stats = {
        tanda: {"accounts": [], "available": len(pool), "requested": 0, "assigned": 0, "shortfall": 0}
        for tanda, pool in remaining.items()
    }
    for username, tanda in assignments.items():
        if not tanda:
            continue
        pool = remaining.setdefault(tanda, [])
        detail = stats.setdefault(tanda, {"accounts": [], "available": len(pool), "requested": 0, "assigned": 0, "shortfall": 0})
        detail["accounts"].append(username)
        requested = requested_by_tanda.get(tanda, 0)
        detail["requested"] += requested
        if max_mode:
            chosen, remaining[tanda] = pool[:requested], pool[requested:]
        else:
            chosen, remaining[tanda] = pool[:per_account], pool[per_account:]
        assigned[username] = chosen
        detail["assigned"] += len(chosen)
        missing = requested - len(chosen)
        if missing:
            shortfalls[username] = missing
            detail["shortfall"] += missing
    return TrialPlan(assigned=assigned, shortfalls=shortfalls, tanda_stats=stats)


def reused_trial_tanda_warnings(plan):
    warnings = []
    for tanda, detail in plan.tanda_stats.items():
        if len(detail["accounts"]) > 1:
            warnings.append(
                f"{tanda}: usada por {', '.join('@' + user for user in detail['accounts'])}. "
                f"Hay {detail['available']} videos unicos para {detail['requested']} requeridos; "
                f"se calendarizan {detail['assigned']} y faltan {detail['shortfall']}."
            )
    return warnings


def trial_preview_path(video_path):
    path = Path(video_path).resolve()
    try:
        identity = f"{path}|{path.stat().st_mtime_ns}"
    except OSError:
        identity = str(path)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    cache_dir = Path(tempfile.gettempdir()) / "metodo_ig_trial_previews"
    return cache_dir / f"{digest}.png"
