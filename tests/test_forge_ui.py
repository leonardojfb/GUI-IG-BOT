def test_forge_exposes_an_explicit_trials_mode_without_distribution():
    forge = _forge_source()

    assert 'values=["Normal", "Trials"]' in forge
    assert "forge_trial_mode_var" in forge
    assert "set_tanda_trial" in forge


def test_forge_does_not_expose_untagged_color_checkbox():
    forge = _forge_source()
    assert "Sin tags: SDR BT.709 ya verificado" not in forge
    assert "forge_untagged_sdr_var" not in forge
    assert "known_untagged_sdr" not in forge
    assert '"Fuentes sin color"' in forge
    assert "assume_unknown_sdr=True" in forge


from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


def test_forge_preview_shows_profile_import_error(monkeypatch):
    import builtins
    import gui_premium_v7

    original_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name == "forge_iphone_profile":
            raise ImportError("helper incompatible")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    showerror = Mock()
    monkeypatch.setattr(gui_premium_v7.messagebox, "showerror", showerror)
    process_button = Mock()
    app = SimpleNamespace(
        forge_video_paths=["source.mp4"],
        e_forge_copies=SimpleNamespace(get=lambda: 1),
        forge_profile_var=SimpleNamespace(get=lambda: "iPhone SDR"),
        btn_forge_process=process_button,
    )

    gui_premium_v7.InstagramAutoPro.forge_preview_metadata(app)

    showerror.assert_called_once_with("Preflight iPhone", "helper incompatible")
    process_button.configure.assert_not_called()


SOURCE = Path(__file__).parents[1] / "gui_premium_v7.py"


def _forge_source() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("    def _build_forge_frame(self):")
    end = source.index("\n\n# ", start)
    return source[start:end]


def test_forge_does_not_expose_or_execute_automatic_distribution():
    forge = _forge_source()

    assert "Categoría destino:" not in forge
    assert "Distribuir automáticamente al procesar" not in forge
    assert "Organizador.distribute_tanda" not in forge
    assert "distribuir automáticamente" not in forge.lower()
