from gui_premium_v7 import _format_transform_summary


def test_format_transform_summary_outputs_table_values():
    formatted = _format_transform_summary(
        {"rotate_deg": 0.8, "crop_px": 2, "speed": 1.003, "trim_start_ms": 2}
    )

    assert formatted["rotation"] == "0.80 deg"
    assert formatted["crop"] == "2 px"
    assert formatted["speed"] == "x1.0030"
    assert formatted["trim"] == "2 ms / 0 ms"
