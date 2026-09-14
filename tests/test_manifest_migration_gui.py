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
