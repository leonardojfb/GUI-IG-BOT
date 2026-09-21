import pytest

from workflow_step_recipes import (
    build_forge_workflow_recipe,
    build_logistica_workflow_recipe,
    build_telegram_workflow_recipe,
)


def test_forge_recipe_freezes_the_real_form_values_without_using_a_profile_name():
    recipe = build_forge_workflow_recipe(
        video_paths=["/inputs/a.mp4"],
        tanda_name="SPAM",
        copies=3,
        days="MAX",
        trial_mode="Normal",
        effects="Medio",
        strength="Custom",
        fx_enabled={"crop": True, "mirror": False},
        forge_strength=0.7,
        overrides={"crop": {"min": 2, "max": 8}},
        metadata_assignments=[{"model": "iPhone 15", "ios": "17.6"}],
    )

    assert recipe == {
        "recipe_version": 1,
        "producer": "forge",
        "video_paths": ["/inputs/a.mp4"],
        "tanda_name": "SPAM",
        "copies": 3,
        "days": "MAX",
        "trial_mode": "Normal",
        "effects": "Medio",
        "strength": "Custom",
        "fx_enabled": {"crop": True, "mirror": False},
        "forge_strength": 0.7,
        "overrides": {"crop": {"min": 2, "max": 8}},
        "metadata_assignments": [{"model": "iPhone 15", "ios": "17.6"}],
    }


def test_logistica_recipe_captures_the_same_inputs_used_by_the_form():
    recipe = build_logistica_workflow_recipe(
        tanda_name="SPAM",
        tanda_name_2="SPAM-2",
        category_dest="CUENTAS SPAM",
        daily_quota=4,
        days="7",
        fillup=True,
    )

    assert recipe["producer"] == "logistica"
    assert recipe["tanda_name"] == "SPAM"
    assert recipe["tanda_name_2"] == "SPAM-2"
    assert recipe["category_dest"] == "CUENTAS SPAM"
    assert recipe["daily_quota"] == 4
    assert recipe["days"] == "7"
    assert recipe["fillup"] is True


def test_logistica_accounts_recipe_keeps_the_account_mode_configuration():
    recipe = build_logistica_workflow_recipe(
        mode="por_cuentas",
        tanda_name="SPAM",
        tanda_name_2="SPAM-2",
        category_dest="",
        daily_quota=3,
        days="7",
        fillup=False,
        account_names=["spam_01", "spam_02"],
        caption_modes={"SPAM": "individual"},
    )

    assert recipe["mode"] == "por_cuentas"
    assert recipe["account_names"] == ["spam_01", "spam_02"]
    assert recipe["caption_modes"] == {"SPAM": "individual"}


def test_telegram_recipe_requires_selected_accounts_and_preserves_delivery_options():
    recipe = build_telegram_workflow_recipe(
        account_names=["spam_01", "spam_02"],
        date="2026-09-20",
        express=True,
        reset_topics=False,
    )

    assert recipe == {
        "recipe_version": 1,
        "producer": "telegram",
        "account_names": ["spam_01", "spam_02"],
        "date": "2026-09-20",
        "express": True,
        "reset_topics": False,
    }

    with pytest.raises(ValueError, match="al menos una cuenta"):
        build_telegram_workflow_recipe(
            account_names=[], date="2026-09-20", express=False, reset_topics=False
        )


def test_telegram_recipe_can_capture_the_explicit_schedule_configuration():
    recipe = build_telegram_workflow_recipe(
        account_names=["spam_01"],
        date="2026-09-20",
        express=False,
        reset_topics=False,
        schedule_config={"spam_01": {"lunes": ["09:00", "18:00"]}},
    )

    assert recipe["schedule_config"] == {"spam_01": {"lunes": ["09:00", "18:00"]}}
