"""Deterministic source grouping for Forge Trial copies."""
import os
import re
import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict

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


def _interleave_trial_files(filenames, tanda, origin_by_file):
    """Send one copy per origin before the next round of copies."""
    groups = {}
    for filename in sorted(filenames):
        verified = origin_by_file.get((tanda, filename))
        key = ("verified", str(verified)) if verified else (
            "source", source_key_from_filename(filename)
        )
        groups.setdefault(key, []).append(filename)

    def copy_order(filename):
        match = re.search(r"__c(\d+)$", os.path.splitext(filename)[0], re.IGNORECASE)
        return (int(match.group(1)) if match else 0, filename.casefold())

    copies_by_origin = [sorted(copies, key=copy_order) for copies in groups.values()]
    return [
        copies[copy_index]
        for copy_index in range(max(map(len, copies_by_origin), default=0))
        for copies in copies_by_origin
        if copy_index < len(copies)
    ]


def missing_trial_caption_sources(filenames: list[str], captions: dict[str, str]) -> list[str]:
    """Return source keys which have no non-empty persisted caption."""
    return [
        source_key for source_key, _copies in group_trial_sources(filenames)
        if not str(captions.get(source_key) or "").strip()
    ]


def load_clean_captions(path=None):
    """Read the caption TXT formats shared by Trial and normal Telegram sends."""
    if not path or not os.path.exists(path):
        return []
    content = open(path, "r", encoding="utf-8", errors="ignore").read()
    pattern = r'\[\d{1,2}.*?\].*?:\s*(.*?)(?=\s*\[\d{1,2}|$)'
    blocks = re.findall(pattern, content, flags=re.DOTALL)
    captions = [b.strip() for b in blocks if b.strip()]
    if not captions:
        paragraphs = [block.strip() for block in re.split(r"\r?\n\s*\r?\n", content) if block.strip()]
        captions = []
        pending = []
        for paragraph in paragraphs:
            pending.append(paragraph)
            if re.search(r"#\w+", paragraph):
                captions.append("\n\n".join(pending))
                pending = []
        if pending:
            captions.append("\n\n".join(pending))
    return captions


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
    daily_repeats: dict[int, int] | None = None


def assign_trial_general_captions(plan: TrialPlan, assignments: dict[str, str],
                                  modes: dict[str, str], pools: dict[str, list[str]],
                                  videos_per_day: int) -> dict[tuple[str, str], str]:
    """Bind each General file to one caption in a shared per-tanda sequence."""
    scheduled = defaultdict(list)
    for username, files in plan.assigned.items():
        if modes.get(username) != "general":
            continue
        tanda = assignments[username]
        for index, filename in enumerate(files):
            day, slot = divmod(index, videos_per_day)
            scheduled[tanda].append((day, slot, username, filename))
    result = {}
    for tanda, rows in scheduled.items():
        pool = list(dict.fromkeys(pools.get(tanda) or []))
        if not pool:
            raise ValueError(f"La tanda TRIAL '{tanda}' no tiene captions en su TXT.")
        for index, (_day, _slot, username, filename) in enumerate(sorted(rows)):
            result[(username, filename)] = pool[index % len(pool)]
    return result


def build_trial_account_plan(assignments, files_by_tanda, videos_per_day, days,
                             *, origin_by_file=None, existing_entries=()):
    """Allocate copy rounds across origins; existing_entries is ignored for TRIAL order."""
    max_mode = str(days).strip().upper() == "MAX"
    per_day = int(videos_per_day)
    per_account = None if max_mode else per_day * int(days)
    origin_by_file = origin_by_file or {}
    remaining = {
        tanda: _interleave_trial_files(files_by_tanda.get(tanda, ()), tanda, origin_by_file)
        for tanda in set(assignments.values()) if tanda
    }
    max_quotas = {}
    if max_mode:
        for tanda, pool in remaining.items():
            users = [username for username, selected in assignments.items() if selected == tanda]
            base, extra = divmod(len(pool), len(users))
            for index, username in enumerate(users):
                max_quotas[username] = base + (index < extra)
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
        requested = max_quotas[username] if max_mode else per_account
        detail["requested"] += requested
        target = min(requested, len(pool))
        remaining[tanda] = pool[target:]
        assigned[username] = pool[:target]
        detail["assigned"] += target
        missing = requested - target
        if missing:
            shortfalls[username] = missing
            detail["shortfall"] += missing

    return TrialPlan(assigned=assigned, shortfalls=shortfalls,
                     tanda_stats=stats, daily_repeats={})


def reused_trial_tanda_warnings(plan):
    warnings = []
    for tanda, detail in plan.tanda_stats.items():
        if len(detail["accounts"]) > 1:
            if detail["shortfall"]:
                warnings.append(
                    f"{tanda}: usada por {', '.join('@' + user for user in detail['accounts'])}. "
                    f"Hay {detail['available']} videos unicos para {detail['requested']} requeridos; "
                    f"se calendarizan {detail['assigned']} y faltan {detail['shortfall']}."
                )
            else:
                warnings.append(
                    f"{tanda}: {detail['assigned']} videos repartidos entre "
                    f"{len(detail['accounts'])} cuentas sin repetir archivos."
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
