"""Deterministic source grouping for Forge Trial copies."""
import os
import re
import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path

_COPY_SUFFIX = re.compile(r"__c\d+$", re.IGNORECASE)


def source_key_from_filename(filename: str) -> str:
    """Return the Forge source key, removing only a final __cNN suffix."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    return _COPY_SUFFIX.sub("", stem)


def group_trial_sources(filenames: list[str]) -> list[tuple[str, list[str]]]:
    """Group Forge outputs in stable source-key order."""
    groups: dict[str, list[str]] = {}
    for filename in sorted(filenames):
        groups.setdefault(source_key_from_filename(filename), []).append(filename)
    return list(groups.items())


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
    per_account = int(videos_per_day) * int(days)
    remaining = {tanda: list(files_by_tanda.get(tanda, ())) for tanda in set(assignments.values()) if tanda}
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
        detail["requested"] += per_account
        chosen, remaining[tanda] = pool[:per_account], pool[per_account:]
        assigned[username] = chosen
        detail["assigned"] += len(chosen)
        missing = per_account - len(chosen)
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
