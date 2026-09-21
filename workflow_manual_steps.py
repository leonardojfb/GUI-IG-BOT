"""Explicit, manual workflow step contracts shared by UI and queue APIs."""
from __future__ import annotations

from typing import Any

from workflow_step_recipes import (
    build_forge_workflow_recipe,
    build_logistica_workflow_recipe,
    build_telegram_workflow_recipe,
)


MODULE_TYPES = ("forge", "logistica", "telegram")
SUBTYPES = {
    "forge": ("normal", "trials"),
    "logistica": ("por_tandas", "por_cuentas"),
    "telegram": ("send",),
}
CONTRACTS = {
    "forge": ("AssetInput", "TandaOutput"),
    "logistica": ("TandaOutput", "ManifestOutput"),
    "telegram": ("ManifestOutput", "TelegramOutput"),
}


def _validate_module_subtype(module_type: str, subtype: str) -> tuple[str, str]:
    module = str(module_type or "").strip().lower()
    variant = str(subtype or "").strip().lower()
    if module not in MODULE_TYPES:
        raise ValueError(f"modulo desconocido: {module or 'vacio'}")
    if variant not in SUBTYPES[module]:
        raise ValueError(f"subtipo invalido para {module}: {variant or 'vacio'}")
    return module, variant


def build_manual_step(module_type: str, subtype: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Build one explicit step from the fields of a traditional module form."""
    module, variant = _validate_module_subtype(module_type, subtype)
    values = dict(fields or {})

    if module == "forge":
        expected_mode = "Trials" if variant == "trials" else "Normal"
        supplied_mode = str(values.get("trial_mode") or "").strip()
        if supplied_mode != expected_mode:
            raise ValueError(f"Forge {variant} requiere trial_mode={expected_mode}")
        recipe = build_forge_workflow_recipe(
            video_paths=values.get("video_paths") or [],
            tanda_name=values.get("tanda_name"),
            copies=values.get("copies"),
            days=values.get("days"),
            trial_mode=supplied_mode,
            effects=values.get("effects"),
            strength=values.get("strength"),
            fx_enabled=values.get("fx_enabled") or {},
            forge_strength=values.get("forge_strength"),
            overrides=values.get("overrides"),
            metadata_assignments=values.get("metadata_assignments") or [],
        )
        recipe["forge_subtype"] = variant
    elif module == "logistica":
        recipe = build_logistica_workflow_recipe(
            mode=variant,
            tanda_name=values.get("tanda_name"),
            tanda_name_2=values.get("tanda_name_2"),
            category_dest=values.get("category_dest"),
            daily_quota=values.get("daily_quota"),
            days=values.get("days"),
            fillup=values.get("fillup", False),
            account_names=values.get("account_names") or [],
            caption_modes=values.get("caption_modes") or {},
        )
    else:
        recipe = build_telegram_workflow_recipe(
            account_names=values.get("account_names") or [],
            date=values.get("date"),
            express=values.get("express", False),
            reset_topics=values.get("reset_topics", False),
        )

    input_contract, output_contract = CONTRACTS[module]
    return {
        "module_type": module,
        "subtype": variant,
        "recipe": recipe,
        "input_contract": input_contract,
        "output_contract": output_contract,
    }


def validate_manual_step(step: dict[str, Any]) -> dict[str, Any]:
    """Validate a previously built step before persistence or queue insertion."""
    if not isinstance(step, dict):
        raise ValueError("step debe ser un objeto")
    module, subtype = _validate_module_subtype(step.get("module_type"), step.get("subtype"))
    recipe = step.get("recipe")
    if not isinstance(recipe, dict) or not recipe:
        raise ValueError("recipe debe ser un objeto no vacio")
    input_contract, output_contract = CONTRACTS[module]
    return {
        "module_type": module,
        "subtype": subtype,
        "recipe": dict(recipe),
        "input_contract": input_contract,
        "output_contract": output_contract,
        "input_binding": dict(step.get("input_binding") or {}),
    }
