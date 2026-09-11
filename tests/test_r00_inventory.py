import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_DOC = REPO_ROOT / "docs" / "R00_LAUNCH_IMPORT_INVENTORY.md"


def _release_python_files():
    script = (REPO_ROOT / "build_release.ps1").read_text(encoding="utf-8")
    match = re.search(r"\$ReleaseFiles\s*=\s*@\((.*?)\)", script, re.S)
    assert match, "build_release.ps1 must define a $ReleaseFiles array"
    return sorted(
        name
        for name in re.findall(r'"([^"]+)"', match.group(1))
        if name.endswith(".py")
    )


def test_r00_inventory_lists_every_launcher_batch_file():
    doc = INVENTORY_DOC.read_text(encoding="utf-8")
    expected = []
    for path in REPO_ROOT.rglob("*"):
        relative = path.relative_to(REPO_ROOT)
        if path.suffix.lower() not in {".bat", ".cmd"}:
            continue
        if ".worktrees" in relative.parts or ".venv" in relative.parts:
            continue
        expected.append(str(relative).replace("\\", "/"))
    expected = sorted(expected)

    assert expected == [
        "Abrir GUI.bat",
        "Instalar GUI.bat",
        "launch_gui.bat",
        "preparar_logistica.bat",
    ]
    for name in expected:
        assert f"| `{name}` |" in doc


def test_r00_inventory_lists_every_release_python_import_surface():
    doc = INVENTORY_DOC.read_text(encoding="utf-8")
    for name in _release_python_files():
        assert f"| `{name}` |" in doc
