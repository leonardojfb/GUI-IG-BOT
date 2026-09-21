from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_modular_editor_opens_directly_on_workflows():
    source = (ROOT / "gui_premium_v7.py").read_text(encoding="utf-8")

    assert "#token={self._local_web_service.token}&view=workflows" in source


def test_local_web_reads_the_requested_initial_view_from_the_hash():
    source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "params.get(\"view\")" in source
    assert "loadView(routeFor[initialView] ? initialView : state.view)" in source


def test_workflow_creator_starts_without_fake_production_blocks():
    source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "workflowBlockDefaults" not in source
    assert "No hay pasos configurados" in source


def test_desktop_quick_calendar_exposes_a_clean_manual_template():
    source = (ROOT / "gui_premium_v7.py").read_text(encoding="utf-8")

    assert "Sin plantilla (configuración manual)" in source
