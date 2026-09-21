"""Build immutable workflow recipes from the existing desktop form state."""
from __future__ import annotations

from copy import deepcopy


def _text(value, field: str, *, required: bool = True) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise ValueError(f"{field} es obligatorio")
    return result


def build_forge_workflow_recipe(
    *,
    video_paths: list[str],
    tanda_name: str,
    copies: int,
    days: str,
    trial_mode: str,
    effects: str,
    strength: str,
    fx_enabled: dict,
    forge_strength: float,
    overrides: dict | None,
    metadata_assignments: list[dict],
) -> dict:
    paths = [str(path).strip() for path in (video_paths or []) if str(path).strip()]
    if not paths:
        raise ValueError("Forge necesita al menos un video")
    try:
        copies = int(copies)
    except (TypeError, ValueError) as exc:
        raise ValueError("copias debe ser un numero") from exc
    if copies < 1:
        raise ValueError("copias debe ser mayor o igual a 1")
    days = _text(days, "dias")
    return {
        "recipe_version": 1,
        "producer": "forge",
        "video_paths": deepcopy(paths),
        "tanda_name": _text(tanda_name, "tanda_name"),
        "copies": copies,
        "days": days,
        "trial_mode": _text(trial_mode, "trial_mode"),
        "effects": _text(effects, "effects"),
        "strength": _text(strength, "strength"),
        "fx_enabled": deepcopy(dict(fx_enabled or {})),
        "forge_strength": float(forge_strength),
        "overrides": deepcopy(dict(overrides or {})) if overrides is not None else None,
        "metadata_assignments": deepcopy(list(metadata_assignments or [])),
    }


def build_logistica_workflow_recipe(
    *,
    mode: str = "por_tandas",
    tanda_name: str,
    tanda_name_2: str,
    category_dest: str,
    daily_quota: int,
    days: str,
    fillup: bool,
    account_names: list[str] | None = None,
    caption_modes: dict | None = None,
) -> dict:
    try:
        daily_quota = int(daily_quota)
    except (TypeError, ValueError) as exc:
        raise ValueError("daily_quota debe ser un numero") from exc
    if daily_quota < 1:
        raise ValueError("daily_quota debe ser mayor o igual a 1")
    mode = _text(mode, "mode")
    accounts = [str(name).strip() for name in (account_names or []) if str(name).strip()]
    if mode == "por_cuentas" and not accounts:
        raise ValueError("Logística por cuentas necesita al menos una cuenta")
    return {
        "recipe_version": 1,
        "producer": "logistica",
        "mode": mode,
        "tanda_name": _text(tanda_name, "tanda_name"),
        "tanda_name_2": _text(tanda_name_2, "tanda_name_2", required=False),
        "category_dest": _text(category_dest, "category_dest", required=mode != "por_cuentas"),
        "daily_quota": daily_quota,
        "days": _text(days, "days"),
        "fillup": bool(fillup),
        "account_names": deepcopy(accounts),
        "caption_modes": deepcopy(dict(caption_modes or {})),
    }


def build_telegram_workflow_recipe(
    *,
    account_names: list[str],
    date: str,
    express: bool,
    reset_topics: bool,
    schedule_config: dict | None = None,
) -> dict:
    accounts = [str(name).strip() for name in (account_names or []) if str(name).strip()]
    if not accounts:
        raise ValueError("Telegram necesita al menos una cuenta seleccionada")
    recipe = {
        "recipe_version": 1,
        "producer": "telegram",
        "account_names": deepcopy(accounts),
        "date": _text(date, "date"),
        "express": bool(express),
        "reset_topics": bool(reset_topics),
    }
    if schedule_config:
        recipe["schedule_config"] = deepcopy(dict(schedule_config))
    return recipe
