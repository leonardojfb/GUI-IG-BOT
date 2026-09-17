"""Convert an R08 planner preview into a guarded calendar manifest preview."""
from __future__ import annotations

from pathlib import Path

from calendar_manifest import build_entry_v2, preview_replace_entries_v2


_LANE_DEFAULTS = {
    "reel": ("instagram_reel", "normal"),
    "trial_reel": ("instagram_trial_reel", "trial"),
}


def preview_shared_manifest_apply(manifest_path, planner_preview: dict) -> dict:
    """Build, but never write, a guarded v2 replacement preview.

    The caller must explicitly pass the returned object to
    ``calendar_manifest.apply_manifest_preview`` after confirmation.
    """
    if not isinstance(planner_preview, dict) or planner_preview.get("status") not in {"ready", "partial"}:
        raise ValueError("El preview no aplicable: requiere status ready o partial")
    scope = dict(planner_preview.get("scope") or {})
    lane = str(scope.get("lane") or "").strip()
    if lane not in _LANE_DEFAULTS:
        raise ValueError("R08 solo aplica por ahora los carriles reel y trial_reel")
    manifest = Path(manifest_path)
    entries = []
    publication_target, delivery_kind = _LANE_DEFAULTS[lane]
    policy = {
        "version": 1,
        "planner": "shared_planner_v1",
        "reuse_policy": "same_account_same_lane_block",
        "seed": planner_preview.get("seed", 0),
    }
    for assignment in planner_preview.get("assignments") or []:
        if not isinstance(assignment, dict):
            raise ValueError("assignment invalida en el preview")
        if str(assignment.get("lane") or lane) != lane:
            raise ValueError("El assignment no coincide con el carril del preview")
        source_path = str(assignment.get("source_path") or "").strip()
        if not source_path:
            raise ValueError("El preview contiene una fuente sin source_path")
        if not Path(source_path).is_file():
            raise ValueError(f"La fuente del preview no existe: {source_path}")
        entries.append(build_entry_v2(
            username=assignment["username"],
            account_id=assignment.get("account_id"),
            delivery_kind=delivery_kind,
            day=assignment["day"],
            slot=assignment["slot"],
            tanda=assignment.get("tanda") or "",
            source_path=source_path,
            display_filename=assignment.get("display_filename") or Path(source_path).name,
            publication_target=publication_target,
            lane=lane,
            placement=assignment.get("placement") or scope.get("placement") or "feed",
            media_class=assignment.get("media_class") or "video",
            method=assignment.get("method") or scope.get("method") or "telegram",
            policy_snapshot=policy,
            schedule_snapshot={"seed": planner_preview.get("seed", 0)},
        ))
    usernames = {str(row["username"]) for row in entries}
    return preview_replace_entries_v2(manifest, entries, usernames, lane)
