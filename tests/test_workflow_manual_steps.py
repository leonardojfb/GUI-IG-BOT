import pytest

from workflow_manual_steps import build_manual_step


def test_manual_forge_requires_explicit_subtype_and_preserves_all_form_fields():
    step = build_manual_step("forge", "trials", {
        "video_paths": ["real.mp4"], "tanda_name": "SPAM", "copies": 2,
        "days": "7", "trial_mode": "Trials", "effects": "Custom",
        "strength": "Custom", "fx_enabled": {"mirror": False},
        "forge_strength": 0.7, "overrides": {"zoom": [1.0, 1.04]},
        "metadata_assignments": [{"source": "form"}],
    })

    assert step["subtype"] == "trials"
    assert step["recipe"]["trial_mode"] == "Trials"
    assert step["recipe"]["overrides"]["zoom"] == [1.0, 1.04]


def test_manual_logistica_has_distinct_por_tandas_and_por_cuentas_contracts():
    step = build_manual_step("logistica", "por_cuentas", {
        "tanda_name": "SPAM", "tanda_name_2": "", "category_dest": "",
        "daily_quota": 3, "days": "MAX", "fillup": False,
        "account_names": ["cuenta-real"], "caption_modes": {"SPAM": "general"},
    })

    assert step["input_contract"] == "TandaOutput"
    assert step["recipe"]["mode"] == "por_cuentas"


def test_manual_step_rejects_unknown_module_or_subtype():
    with pytest.raises(ValueError, match="subtipo"):
        build_manual_step("forge", "inventado", {})
