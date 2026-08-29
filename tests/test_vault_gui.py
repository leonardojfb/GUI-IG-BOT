import ast
from pathlib import Path


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


def _source(name):
    source = GUI.read_text(encoding="utf-8")
    return ast.get_source_segment(source, _method(name))


def test_sidebar_and_content_register_vault_frame():
    sidebar = _source("_build_sidebar")
    content = _source("_build_content_area")

    assert '"Boveda", "Boveda"' in sidebar
    assert '"Boveda"' in content
    assert "self._build_vault_frame()" in content


def test_vault_frame_lists_assets_and_history_without_root_scroll():
    frame = _source("_build_vault_frame")
    table = _source("refresh_vault_table")
    history = _source("refresh_vault_history")

    assert "CTkScrollableFrame" not in frame
    assert "self.vault_tree" in frame
    assert "self.db.list_vault_assets" in table
    assert "output_count" in table
    assert "self.db.list_vault_asset_history" in history


def test_forge_uses_vault_selection_controls():
    forge = _source("_build_forge_frame")
    add = _source("forge_add_videos")
    picker = _source("forge_select_from_vault")
    process = _source("forge_process")

    assert "self.forge_vault_assets = []" in forge
    assert "forge_select_from_vault" in forge
    assert "upsert_vault_asset" in add
    assert "self._set_forge_vault_assets" in add
    assert "self.db.list_vault_assets" in picker
    assert "vault_assets" in process


def test_forge_preview_surfaces_exact_vault_capacity():
    forge = _source("_build_forge_frame")
    preview = _source("forge_preview_metadata")

    assert '"Capacidad"' in forge
    assert "forge_variant_capacity" in preview
    assert "available" in preview
    assert "No quedan variantes nuevas" in preview
