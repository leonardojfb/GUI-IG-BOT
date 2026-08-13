"""Deterministic source grouping for Forge Trial copies."""
import os
import re

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
