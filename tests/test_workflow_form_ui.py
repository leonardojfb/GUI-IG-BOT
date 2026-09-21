from pathlib import Path


GUI = Path(__file__).resolve().parents[1] / "gui_premium_v7.py"


def test_real_forms_can_add_forge_logistica_and_telegram_steps_to_a_workflow():
    source = GUI.read_text(encoding="utf-8")

    assert source.count('text="Agregar a workflow"') >= 3
    assert "build_forge_workflow_recipe" in source
    assert "build_logistica_workflow_recipe" in source
    assert "build_telegram_workflow_recipe" in source
    assert "previous_output" in source
    assert "_queue_current_forge" in source
    assert "_queue_current_logistica" in source
    assert "_queue_current_telegram" in source
