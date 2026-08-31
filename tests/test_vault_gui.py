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
    detail = _source("refresh_vault_asset_detail")

    assert "CTkScrollableFrame" not in frame
    assert "self.vault_tree" in frame
    assert "self.db.list_vault_assets" in table
    assert "output_count" in table
    assert "self.db.list_vault_asset_history" in detail


def test_biblioteca_exposes_import_roots_collections_and_asset_detail():
    source = GUI.read_text(encoding="utf-8")
    for token in (
        'title="Biblioteca"', "vault_create_root", "vault_assign_selected_asset",
        "refresh_vault_roots", "list_content_roots", "list_collection_assets",
    ):
        assert token in source


def test_biblioteca_filters_assets_by_selected_family_through_database_api():
    table = _source("refresh_vault_table")

    assert "root_id = self._selected_vault_root_id()" in table
    assert "self.db.list_root_assets(root_id)" in table


def test_biblioteca_makes_collections_creatable_and_assignable_without_file_moves():
    frame = _source("_build_vault_frame")
    create = _source("vault_create_collection")
    assign = _source("vault_assign_selected_assets_to_collection")

    assert "self.vault_collection_name_var" in frame
    assert "Nueva coleccion" in frame
    assert "Agregar a coleccion" in frame
    assert "self.db.create_vault_collection(name)" in create
    assert "self.db.add_asset_to_collection(collection_id, int(asset_id))" in assign
    assert "Selecciona una coleccion de destino." in assign
    assert "self.refresh_vault_asset_detail()" in assign


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
