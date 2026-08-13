from pathlib import Path


SOURCE = Path(__file__).parents[1] / "gui_premium_v7.py"


def _method_source(name: str) -> str:
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index(f"    def {name}(")
    next_start = source.find("\n    def ", start + 1)
    if next_start == -1:
        return source[start:]
    return source[start:next_start]


def test_logistica_caption_controls_are_available_in_both_distribution_tabs():
    tandas_tab = _method_source("_build_dist_tandas_tab")
    cuentas_tab = _method_source("_build_dist_cuentas_tab")

    assert "_build_logistica_caption_controls" in tandas_tab
    assert 'selector_attr="c_tandas"' in tandas_tab
    assert "_build_logistica_caption_controls" in cuentas_tab
    assert 'selector_attr="acct_dist_tanda"' in cuentas_tab


def test_logistica_caption_actions_target_the_requested_tanda_selector():
    assign = _method_source("assign_captions_to_selected_tanda")
    clear = _method_source("clear_captions_from_selected_tanda")

    assert 'selector_attr="c_tandas"' in assign
    assert 'selector_attr="c_tandas"' in clear
    assert "_get_logistica_caption_tanda_name(selector_attr)" in assign
    assert "_get_logistica_caption_tanda_name(selector_attr)" in clear


def test_por_cuentas_distribution_calendarizes_filenames_for_telegram_captions():
    run = _method_source("_acct_dist_run")

    assert "build_calendar_video_filename" in run


def test_por_cuentas_has_optional_individual_caption_controls():
    source = _method_source("_build_dist_cuentas_tab")

    assert "Captions individuales" in source
    assert "_acct_refresh_individual_captions" in source
