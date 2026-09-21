from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_exposes_add_to_workflow_and_explicit_telegram_mode():
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "Agregar a workflow" in app
    assert "queue_only" in app
    assert "send_on_run" in app


def test_web_renders_ordered_queue_controls_and_execution_action():
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "renderWorkflowQueue" in app
    assert "workflow.queue" in app
    assert "Ejecutar workflow" in app
