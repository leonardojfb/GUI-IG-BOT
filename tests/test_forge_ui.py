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
