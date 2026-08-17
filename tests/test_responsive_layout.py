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


def _calls_method(node, name):
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == name
        for child in ast.walk(node)
    )


def test_main_window_size_is_computed_from_screen_instead_of_hardcoded():
    init = _method("__init__")

    hardcoded_geometry = [
        child
        for child in ast.walk(init)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "geometry"
        and child.args
        and isinstance(child.args[0], ast.Constant)
        and child.args[0].value == "1400x860"
    ]

    assert not hardcoded_geometry
    assert _calls_method(init, "_apply_responsive_window")


def test_responsive_window_uses_screen_bounds_and_low_minimum():
    method = _method("_apply_responsive_window")
    source = GUI.read_text(encoding="utf-8")
    segment = ast.get_source_segment(source, method)

    assert "winfo_screenwidth" in segment
    assert "winfo_screenheight" in segment
    assert "minsize(MIN_WINDOW_W, MIN_WINDOW_H)" in segment


def test_content_frames_keep_normal_root_geometry():
    method = _method("_build_content_area")

    root_scrollable_calls = [
        child
        for child in ast.walk(method)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "CTkScrollableFrame"
    ]
    root_frame_calls = [
        child
        for child in ast.walk(method)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "CTkFrame"
    ]

    assert not root_scrollable_calls
    assert root_frame_calls


def test_tall_content_tabs_keep_their_own_scroll_area():
    source = GUI.read_text(encoding="utf-8")

    for method_name in (
        "_build_updates_frame",
        "_build_video_editor_frame",
        "_build_forge_frame",
    ):
        segment = ast.get_source_segment(source, _method(method_name))
        assert "CTkScrollableFrame" in segment



def test_large_toplevel_windows_use_responsive_geometry_helper():
    source = GUI.read_text(encoding="utf-8")
    assert "def _fit_toplevel(self, window, width, height):" in source

    for method_name in (
        "preview_distribution",
        "_acct_refresh_individual_captions",
    ):
        segment = ast.get_source_segment(source, _method(method_name))
        assert "geometry(\"950x700\")" not in segment
        assert "geometry(\"860x680\")" not in segment
        assert "_fit_toplevel(" in segment
