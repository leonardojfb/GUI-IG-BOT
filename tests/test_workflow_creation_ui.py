from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_calendar_uses_visible_presets_and_identity_choices():
    source = (ROOT / "gui_premium_v7.py").read_text(encoding="utf-8")

    assert "Plantilla de frecuencia" in source
    assert "Selecciona las cuentas" in source
    assert "self.calendar_identity_vars" in source
    assert "Ajustes avanzados" in source
    assert "def _calendar_apply_preset" in source
    assert "Editor modular de workflows" in source


def test_web_workflow_creator_exposes_complete_manual_module_steps_without_defaults():
    source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert 'data-action="workflow-add-step"' in source
    assert 'data-step-field="module_type"' in source
    assert 'data-step-field="subtype"' in source
    assert 'Guardar como perfil' in source
    assert 'Cargar perfil' in source
    assert 'Limpiar formulario' in source
    for field in ("video_paths", "trial_mode", "effects", "fx_enabled", "mode", "daily_quota", "account_names", "caption_modes", "express", "reset_topics"):
        assert field in source
    assert "workflowBlockDefaults" not in source
    assert 'profile: "no_mirror"' not in source
    assert 'data-action="workflow-create-and-continue"' in source
    assert 'workflows/manual' in source


def test_manual_step_editor_has_layout_for_all_form_controls():
    source = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert ".workflow-step-grid" in source
    assert ".workflow-step-selectors" in source
    assert ".workflow-step textarea" in source
