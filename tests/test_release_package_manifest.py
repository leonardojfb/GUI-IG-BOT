import ast
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _release_files_from_build_script():
    script = (REPO_ROOT / "build_release.ps1").read_text(encoding="utf-8")
    match = re.search(r"\$ReleaseFiles\s*=\s*@\((.*?)\)", script, re.S)
    assert match, "build_release.ps1 must define a $ReleaseFiles array"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def _imported_local_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])

    local_modules = set()
    for name in imported:
        candidate = REPO_ROOT / f"{name}.py"
        if candidate.exists():
            local_modules.add(candidate.name)
    return local_modules


def test_release_allowlist_includes_local_modules_imported_by_shipped_files():
    release_files = _release_files_from_build_script()
    shipped_python = [REPO_ROOT / file for file in release_files if file.endswith(".py")]

    missing = {}
    for path in shipped_python:
        required = _imported_local_modules(path)
        missing[path.name] = sorted(required - release_files)

    missing = {file: modules for file, modules in missing.items() if modules}
    assert missing == {}


def test_release_packages_clean_pc_video_dependencies():
    release_files = _release_files_from_build_script()
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    installer = (REPO_ROOT / "Instalar GUI.bat").read_text(encoding="utf-8")

    assert "Pillow" in requirements
    assert "tools\\ffmpeg\\bin\\ffmpeg.exe" in installer
    assert "tools\\ffmpeg\\bin\\ffprobe.exe" in installer
    assert {
        "ffmpeg_tools.py",
        "tools/ffmpeg/bin/ffmpeg.exe",
        "tools/ffmpeg/bin/ffprobe.exe",
    }.issubset(release_files)
