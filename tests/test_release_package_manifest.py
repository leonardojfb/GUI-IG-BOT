import ast
import re
from pathlib import Path

import updater


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_UPDATEABLE_FILES = {
    "Abrir GUI.bat",
    "Instalar GUI.bat",
    "launch_gui.bat",
    "launcher.py",
    "updater.py",
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


def test_builder_labels_application_and_bootstrap_manifests():
    script = (REPO_ROOT / "build_release.ps1").read_text(encoding="utf-8")

    assert '$PackageKind = if ($BootstrapUpdater) { "bootstrap" } else { "application" }' in script
    assert "package_kind = $PackageKind" in script
    assert '-NotePropertyName update_phase -NotePropertyValue "bootstrap"' in script
    assert '"MetodoIG-v{0}{1}.zip" -f $Version, $AssetSuffix' in script


def test_release_builder_never_embeds_client_update_config():
    script = (REPO_ROOT / "build_release.ps1").read_text(encoding="utf-8")

    assert "$IncludeClientConfig" not in script
    assert 'Join-Path $StagePath "update_config.json"' not in script


def test_current_updater_accepts_every_normal_release_file():
    assert _release_files_from_build_script() <= updater.DEFAULT_UPDATEABLE_FILES


def test_normal_release_and_updater_forbid_operational_data():
    script = (REPO_ROOT / "build_release.ps1").read_text(encoding="utf-8")
    forbidden = {"organizador.db", "dist_accounts_history.json"}

    assert forbidden.isdisjoint(_release_files_from_build_script())
    assert forbidden.isdisjoint(updater.DEFAULT_UPDATEABLE_FILES)
    assert "$IncludeRealDatabase" not in script
    assert "$IncludeClientHistory" not in script


def test_release_includes_manifest_migration_cli_but_bootstrap_does_not():
    assert "manifest_migration_cli.py" in _release_files_from_build_script()
    assert "manifest_migration_cli.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "manifest_migration_cli.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_shared_planner_but_bootstrap_does_not():
    assert "shared_planner.py" in _release_files_from_build_script()
    assert "shared_planner.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "shared_planner.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_shared_planner_sources_but_bootstrap_does_not():
    assert "shared_planner_sources.py" in _release_files_from_build_script()
    assert "shared_planner_sources.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "shared_planner_sources.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_r08_apply_and_reservations_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    for name in ("shared_planner_apply.py", "planner_reservations.py"):
        assert name in release_files
        assert name in updater.DEFAULT_UPDATEABLE_FILES
        assert name not in _bootstrap_release_files_from_build_script()


def test_release_includes_r09_durable_job_modules_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    for name in ("durable_jobs.py", "job_runner.py"):
        assert name in release_files
        assert name in updater.DEFAULT_UPDATEABLE_FILES
        assert name not in _bootstrap_release_files_from_build_script()


def test_release_includes_r10_producer_adapter_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    assert "producer_jobs.py" in release_files
    assert "producer_jobs.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "producer_jobs.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_r11_photo_forge_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    assert "photo_forge.py" in release_files
    assert "photo_forge.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "photo_forge.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_r12_local_web_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    assert "local_web.py" in release_files
    assert "local_web.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "local_web.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_r13_read_only_ios_export_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    assert "ios_remote_read.py" in release_files
    assert "ios_remote_read.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "ios_remote_read.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_r14_destination_forge_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    assert "destination_forge.py" in release_files
    assert "destination_forge.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "destination_forge.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_ios_remote_adapter_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    assert "ios_remote_adapter.py" in release_files
    assert "ios_remote_adapter.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "ios_remote_adapter.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_r15_telegram_ledger_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    assert "telegram_ledger.py" in release_files
    assert "telegram_ledger.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "telegram_ledger.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_r16_confirmation_ledger_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    assert "confirmation_ledger.py" in release_files
    assert "confirmation_ledger.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "confirmation_ledger.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_r17_crm_insights_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    assert "crm_insights.py" in release_files
    assert "crm_insights.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "crm_insights.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_r18_manual_calendar_export_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    assert "manual_calendar_export.py" in release_files
    assert "manual_calendar_export.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "manual_calendar_export.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_r19_platform_adapters_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    assert "platform_adapters.py" in release_files
    assert "platform_adapters.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "platform_adapters.py" not in _bootstrap_release_files_from_build_script()


def test_release_includes_r20_certification_but_bootstrap_does_not():
    release_files = _release_files_from_build_script()
    assert "release_certification.py" in release_files
    assert "release_certification.py" in updater.DEFAULT_UPDATEABLE_FILES
    assert "release_certification.py" not in _bootstrap_release_files_from_build_script()


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
