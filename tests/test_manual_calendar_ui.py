from pathlib import Path


GUI_SOURCE = Path("gui_premium_v7.py")


def _gui_source():
    return GUI_SOURCE.read_text(encoding="utf-8")


def test_accounts_ui_contains_shared_story_domain_and_individual_override_controls():
    source = _gui_source()

    assert "Links de historias" in source
    assert "Aplicar a todas" in source
    assert "Editar enlace individual" in source
    assert "_save_story_link_base_url" in source
    assert "_save_story_link_override" in source
