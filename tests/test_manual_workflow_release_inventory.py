from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_manual_workflow_runtime_modules_are_in_every_release_inventory():
    required = {"workflow_manual_steps.py", "workflow_profiles.py"}
    build = (ROOT / "build_release.ps1").read_text(encoding="utf-8")
    manifest = (ROOT / "release-manifest.json").read_text(encoding="utf-8")
    updater = (ROOT / "updater.py").read_text(encoding="utf-8")
    inventory = (ROOT / "docs" / "R00_LAUNCH_IMPORT_INVENTORY.md").read_text(encoding="utf-8")

    for name in required:
        assert f'"{name}"' in build
        assert f'"{name}"' in manifest
        assert f'"{name}"' in updater
        assert f"| `{name}` |" in inventory
