import ast
from pathlib import Path

import gui_premium_v7


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui_premium_v7.py"


def _tree():
    return ast.parse(GUI.read_text(encoding="utf-8"))


def _method(name):
    for cls in ast.walk(_tree()):
        if isinstance(cls, ast.ClassDef) and cls.name == "InstagramAutoPro":
            for node in cls.body:
                if isinstance(node, ast.FunctionDef) and node.name == name:
                    return node
    raise AssertionError(f"{name} not found")


def test_manifest_migration_preview_text_summarizes_safe_review():
    text = gui_premium_v7._manifest_migration_preview_text(
        {
            "base_version": 1,
            "target_version": 2,
            "summary": {"migrated": 3, "total": 3},
            "merged_entries": [
                {"username": "alice", "lane": "reel"},
                {"username": "bob", "lane": "trial_reel"},
                {"username": "alice", "lane": "story"},
            ],
        }
    )

    assert "Manifest v1 -> v2" in text
    assert "Entradas a migrar: 3" in text
    assert "reel: 1" in text
    assert "trial_reel: 1" in text
    assert "story: 1" in text
    assert "alice: 2" in text


def test_updates_frame_exposes_manifest_migration_actions():
    source = GUI.read_text(encoding="utf-8")
    segment = ast.get_source_segment(source, _method("_build_updates_frame"))

    assert "Manifest v2" in segment
    assert "_preview_manifest_migration" in segment
    assert "_apply_manifest_migration" in segment


def test_manifest_migration_gui_methods_use_preview_before_apply():
    source = GUI.read_text(encoding="utf-8")
    apply_segment = ast.get_source_segment(source, _method("_apply_manifest_migration"))

    assert "preview_migrate_manifest_v1_to_v2" in apply_segment
    assert "apply_manifest_preview" in apply_segment
    assert "messagebox.askyesno" in apply_segment


def test_manifest_journal_report_text_summarizes_recovery_state():
    text = gui_premium_v7._manifest_journal_report_text(
        {
            "status": "pending",
            "journal_exists": True,
            "journal_readable": True,
            "journal": {"operation": "replace_entries_v2", "entry_count": 4},
            "manifest": {"readable": True, "version": 2, "entries_count": 12},
            "sqlite": {"checked": True, "integrity_ok": True, "integrity_check": "ok"},
        }
    )

    assert "Journal: pendiente" in text
    assert "Operacion: replace_entries_v2" in text
    assert "Entradas journal: 4" in text
    assert "Manifest: legible, v2, 12 entrada(s)" in text
    assert "SQLite: integrity_check ok" in text


def test_updates_frame_exposes_manifest_journal_recovery_actions():
    source = GUI.read_text(encoding="utf-8")
    frame_segment = ast.get_source_segment(source, _method("_build_updates_frame"))
    inspect_segment = ast.get_source_segment(source, _method("_inspect_manifest_journal"))
    clear_segment = ast.get_source_segment(source, _method("_clear_manifest_journal"))

    assert "Revisar journal" in frame_segment
    assert "Limpiar journal" in frame_segment
    assert "_inspect_manifest_journal" in frame_segment
    assert "_clear_manifest_journal" in frame_segment
    assert "inspect_manifest_journal" in inspect_segment
    assert "clear_manifest_journal" in clear_segment
    assert "messagebox.askyesno" in clear_segment


def test_manifest_journal_clear_gui_uses_database_integrity_guard():
    source = GUI.read_text(encoding="utf-8")
    clear_segment = ast.get_source_segment(source, _method("_clear_manifest_journal"))
    db_segment = ast.get_source_segment(source, _method("_manifest_migration_db_path"))

    assert "db_path" in clear_segment
    assert "organizador.db" in db_segment
    assert "confirm=True" in clear_segment
