from types import SimpleNamespace
from unittest.mock import Mock

import gui_premium_v7


def test_forge_conversion_action_confirms_then_uses_selected_batch(monkeypatch, tmp_path):
    preview = {"video_count": 12}
    db = SimpleNamespace(
        preview_completed_forge_trial_conversion=Mock(return_value=preview),
        convert_completed_forge_tanda_to_trial=Mock(return_value={
            "video_count": 12, "converted_logs": 12, "backup_path": "backup.db",
        }),
    )
    refresh = Mock()
    app = SimpleNamespace(
        db=db,
        forge_convert_tanda_var=SimpleNamespace(get=lambda: "Batch"),
        _refresh_forge_convert_tandas=refresh,
    )
    monkeypatch.setattr(gui_premium_v7, "_BASE_DIR", str(tmp_path))
    monkeypatch.setattr(gui_premium_v7.messagebox, "askyesno", Mock(return_value=True))
    showinfo = Mock()
    monkeypatch.setattr(gui_premium_v7.messagebox, "showinfo", showinfo)

    gui_premium_v7.InstagramAutoPro.forge_convert_completed_to_trial(app)

    root = tmp_path / "videos_finales"
    db.preview_completed_forge_trial_conversion.assert_called_once_with("Batch", root)
    db.convert_completed_forge_tanda_to_trial.assert_called_once_with(
        "Batch", root, tmp_path / "backups"
    )
    refresh.assert_called_once()
    showinfo.assert_called_once()


def test_forge_conversion_action_cancels_without_database_change(monkeypatch, tmp_path):
    db = SimpleNamespace(
        preview_completed_forge_trial_conversion=Mock(return_value={"video_count": 2}),
        convert_completed_forge_tanda_to_trial=Mock(),
    )
    app = SimpleNamespace(db=db, forge_convert_tanda_var=SimpleNamespace(get=lambda: "Batch"))
    monkeypatch.setattr(gui_premium_v7, "_BASE_DIR", str(tmp_path))
    monkeypatch.setattr(gui_premium_v7.messagebox, "askyesno", Mock(return_value=False))

    gui_premium_v7.InstagramAutoPro.forge_convert_completed_to_trial(app)

    db.convert_completed_forge_tanda_to_trial.assert_not_called()
