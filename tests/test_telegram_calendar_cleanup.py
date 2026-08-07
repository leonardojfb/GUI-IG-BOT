from pathlib import Path
import os

import pytest

import organizadortg


def _windows_long_path(path):
    path = os.path.abspath(os.fspath(path))
    if os.name != "nt" or path.startswith("\\\\?\\"):
        return path
    if path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path


def _write_calendar_file(calendar_root: Path, day: str, account: str, filename: str):
    folder = calendar_root / day / account
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    path.write_bytes(b"video")
    return path


def test_delete_calendarizations_for_accounts_only_removes_exact_selected_accounts(tmp_path):
    calendar_root = tmp_path / "CALENDARIO_POSTEO"
    _write_calendar_file(calendar_root, "Dia_1", "evestarryh", "one.mp4")
    _write_calendar_file(calendar_root, "Dia_2", "evestarryh", "two.mov")
    _write_calendar_file(calendar_root, "Dia_1", "evestarryh trials", "trial.mp4")
    _write_calendar_file(calendar_root, "Dia_1", "other", "other.mp4")

    summary = organizadortg.delete_calendarizations_for_accounts(
        {"evestarryh"},
        calendar_root=str(calendar_root),
    )

    assert summary["accounts"] == 1
    assert summary["deleted_folders"] == 2
    assert summary["deleted_files"] == 2
    assert summary["failed"] == 0
    assert not (calendar_root / "Dia_1" / "evestarryh").exists()
    assert not (calendar_root / "Dia_2" / "evestarryh").exists()
    assert (calendar_root / "Dia_1" / "evestarryh trials").is_dir()
    assert (calendar_root / "Dia_1" / "other").is_dir()


def test_delete_calendarizations_for_accounts_ignores_non_day_folders(tmp_path):
    calendar_root = tmp_path / "CALENDARIO_POSTEO"
    _write_calendar_file(calendar_root, "Dia_1", "alpha", "one.mp4")
    _write_calendar_file(calendar_root, "backup", "alpha", "backup.mp4")

    summary = organizadortg.delete_calendarizations_for_accounts(
        ["alpha"],
        calendar_root=str(calendar_root),
    )

    assert summary["deleted_folders"] == 1
    assert not (calendar_root / "Dia_1" / "alpha").exists()
    assert (calendar_root / "backup" / "alpha").is_dir()


@pytest.mark.skipif(os.name != "nt", reason="Windows long-path regression test")
def test_delete_calendarizations_for_accounts_handles_long_windows_file_paths(tmp_path):
    calendar_root = tmp_path / "CALENDARIO_POSTEO"
    account = "TRIALS - " + ("evelyncutebbyh " * 4).strip()
    account_dir = calendar_root / ("Dia_1_" + "d" * 50) / account
    video_path = account_dir / ("video_" + "x" * 150 + ".mp4")
    assert len(str(video_path)) > 260

    os.makedirs(_windows_long_path(account_dir), exist_ok=True)
    with open(_windows_long_path(video_path), "wb") as fh:
        fh.write(b"video")

    summary = organizadortg.delete_calendarizations_for_accounts(
        [account],
        calendar_root=str(calendar_root),
    )

    assert summary["failed"] == 0
    assert summary["deleted_folders"] == 1
    assert summary["deleted_files"] == 1
    assert not os.path.exists(_windows_long_path(account_dir))


def test_gui_telegram_tab_exposes_selected_calendar_cleanup_button():
    source = Path("gui_premium_v7.py").read_text(encoding="utf-8")

    assert "Borrar calendarizaciones" in source
    assert "command=self.delete_selected_calendarizations" in source
