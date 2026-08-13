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

