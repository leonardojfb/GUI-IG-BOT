import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui_premium_v7.py"


def _build_sidebar_function():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_build_sidebar":
            return node
    raise AssertionError("_build_sidebar not found")


def test_sidebar_navigation_uses_scrollable_container():
    sidebar = _build_sidebar_function()
    assigns_scrollable_nav = False
    navitem_parents = set()

    for node in ast.walk(sidebar):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "CTkScrollableFrame"
        ):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr == "sidebar_nav":
                    assigns_scrollable_nav = True

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "NavItem"
            and node.args
        ):
            parent = node.args[0]
            if isinstance(parent, ast.Attribute):
                navitem_parents.add(parent.attr)

    assert assigns_scrollable_nav
    assert navitem_parents == {"sidebar_nav"}
