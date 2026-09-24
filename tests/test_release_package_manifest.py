import ast
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_UPDATEABLE_FILES = {
    "Abrir GUI.bat",
    "Instalar GUI.bat",
    "launch_gui.bat",
    "launcher.py",
    "updater.py",
    "console_encoding.py",
    "organizador.db",
    "organizador.default.db",
    "version.json",
    "requirements.txt",
    "gui_premium_v7.py",
    "gui_unificada.py",
    "gui_organizador.py",
    "organizador_simple.py",
    "Organizador.py",
    "database.py",
    "organizadortg.py",
    "videos.py",
    "video_editor.py",
    "render_performance.py",
    "metadata_pool.py",
    "telegram_core.py",
    "cleaner.py",
    "vercuentas.py",
    "logo_elittisse.svg",
    "styles/colors.py",
    "styles/components.py",
    "styles/__init__.py",
    "dist_accounts_history.json",
}


def _release_files_from_build_script():
    script = (REPO_ROOT / "build_release.ps1").read_text(encoding="utf-8")
    match = re.search(r"\$ReleaseFiles\s*=\s*@\((.*?)\)", script, re.S)
    assert match, "build_release.ps1 must define a $ReleaseFiles array"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def _bootstrap_release_files_from_build_script():
    script = (REPO_ROOT / "build_release.ps1").read_text(encoding="utf-8")
    match = re.search(r"\$BootstrapReleaseFiles\s*=\s*@\((.*?)\)", script, re.S)
    assert match, "build_release.ps1 must define a $BootstrapReleaseFiles array"
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


def test_iphone_profile_module_is_allowed_by_builder_and_updater():
    import updater

    assert "forge_iphone_profile.py" in _release_files_from_build_script()
    assert "forge_iphone_profile.py" in updater.DEFAULT_UPDATEABLE_FILES


def test_release_packages_clean_pc_video_dependencies():
    release_files = _release_files_from_build_script()
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    installer = (REPO_ROOT / "Instalar GUI.bat").read_text(encoding="utf-8")

    assert "Pillow" in requirements
    assert "tools\\ffmpeg\\bin\\ffmpeg.exe" in installer
    assert "tools\\ffmpeg\\bin\\ffprobe.exe" in installer
    assert {
        "tools/ffmpeg/bin/ffmpeg.exe",
        "tools/ffmpeg/bin/ffprobe.exe",
    }.issubset(release_files)
    assert "ffmpeg_tools.py" not in release_files


def test_legacy_updater_can_apply_import_compatible_python_files():
    release_files = _bootstrap_release_files_from_build_script()
    legacy_python = [
        REPO_ROOT / file
        for file in release_files
        if file.endswith(".py") and file in LEGACY_UPDATEABLE_FILES
    ]

    missing = {}
    for path in legacy_python:
        required = _imported_local_modules(path)
        missing[path.name] = sorted(required - LEGACY_UPDATEABLE_FILES)

    missing = {file: modules for file, modules in missing.items() if modules}
    assert missing == {}


def test_bootstrap_package_only_contains_files_an_old_updater_can_copy():
    assert _bootstrap_release_files_from_build_script() == {"updater.py", "version.json"}


def test_legacy_updater_python_files_do_not_require_new_console_encoding_names():
    release_files = _release_files_from_build_script()
    legacy_python = [
        REPO_ROOT / file
        for file in release_files
        if file.endswith(".py") and file in LEGACY_UPDATEABLE_FILES and file != "console_encoding.py"
    ]

    offenders = {}
    for path in legacy_python:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "console_encoding":
                imports.extend(alias.name for alias in node.names if alias.name.startswith("ffmpeg_tool_"))
        if imports:
            offenders[path.name] = sorted(imports)

    assert offenders == {}
